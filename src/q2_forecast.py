"""Strict expanding-window forecasts for Question 2.

Each forecast for day d uses source rows < d, whose final sample is d 00:00.
All 144 targets run from d 00:10 through d+1 00:00 (left endpoints).  Attachment 1's
single supplied profile is used solely as the cold-start prior on 2025-01-01;
from 2025-01-02 onward the models use Attachment 2 history only.
"""

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
import json

import numpy as np

from data_loader import DT_HOURS, read_attachment1
from q2_data import Q2Data, load_q2_data


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ForecastConfig:
    similar_days: int = 6
    recency_penalty: float = 0.08
    similarity_temperature: float = 0.25
    load_fourier_order: int = 2
    load_ridge: float = 2.0
    pv_fourier_order: int = 3
    pv_ridge: float = 2.0
    pv_shape_days: int = 14
    pv_shape_decay: float = 0.15
    minimum_regression_days: int = 14


def _date_features(dates: list[date], order: int) -> np.ndarray:
    rows = []
    for d in dates:
        doy = d.timetuple().tm_yday
        row = [1.0, (doy - 183.0) / 183.0]
        for h in range(1, order + 1):
            angle = 2 * np.pi * h * doy / 365.25
            row.extend((np.sin(angle), np.cos(angle)))
        rows.append(row)
    return np.asarray(rows, dtype=float)


def _ridge_predict(X: np.ndarray, Y: np.ndarray, x: np.ndarray, alpha: float) -> np.ndarray:
    Xs = X.copy()
    xs = x.copy()
    if X.shape[1] > 1:
        mean = X[:, 1:].mean(axis=0)
        scale = X[:, 1:].std(axis=0)
        scale[scale < 1e-12] = 1.0
        Xs[:, 1:] = (X[:, 1:] - mean) / scale
        xs[1:] = (x[1:] - mean) / scale
    penalty = np.eye(X.shape[1]) * alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(Xs.T @ Xs + penalty, Xs.T @ Y)
    return xs @ beta


def _load_base(history: np.ndarray, dates: tuple[date, ...], d: int, cfg: ForecastConfig,
               cold_prior: np.ndarray) -> np.ndarray:
    if d == 0:
        return cold_prior.copy()
    candidates = [j for j in range(1, d) if dates[j].weekday() == dates[d].weekday()]
    if not candidates:
        return history[max(0, d - 7):d].mean(axis=0)
    target_lag = history[d - 1]
    denom = max(float(np.mean(np.abs(target_lag))), 1e-12)
    scores = []
    for j in candidates:
        distance = float(np.sqrt(np.mean((target_lag - history[j - 1]) ** 2)) / denom)
        scores.append((distance + cfg.recency_penalty * (d - j) / 7.0, j))
    selected = sorted(scores)[:min(cfg.similar_days, len(scores))]
    q = np.asarray([v[0] for v in selected])
    weights = np.exp(-(q - q.min()) / cfg.similarity_temperature)
    weights /= weights.sum()
    return np.sum(np.asarray([history[j] for _, j in selected]) * weights[:, None], axis=0)


def _pv_forecast(history: np.ndarray, dates: tuple[date, ...], d: int, cfg: ForecastConfig,
                 cold_prior: np.ndarray) -> np.ndarray:
    if d == 0:
        return cold_prior.copy()
    totals = DT_HOURS * history[:d].sum(axis=1)
    if d >= cfg.minimum_regression_days:
        X0 = _date_features(list(dates[:d]), cfg.pv_fourier_order)
        X = np.column_stack((X0, np.r_[totals[0], totals[:-1]]))
        x0 = _date_features([dates[d]], cfg.pv_fourier_order)[0]
        x = np.r_[x0, totals[-1]]
        total_hat = float(_ridge_predict(X, totals, x, cfg.pv_ridge))
    else:
        recent = totals[max(0, d - 7):]
        weights = np.exp(-0.25 * np.arange(len(recent) - 1, -1, -1))
        total_hat = float(weights @ recent / weights.sum())
    total_hat = max(total_hat, 0.0)
    recent = history[max(0, d - cfg.pv_shape_days):d]
    recent_totals = recent.sum(axis=1)
    valid = recent_totals > 1e-12
    if np.any(valid):
        shapes = recent[valid] / recent_totals[valid, None]
        ages = np.arange(len(recent))[valid]
        weights = np.exp(-cfg.pv_shape_decay * (len(recent) - 1 - ages))
        shape = np.sum(shapes * weights[:, None], axis=0) / weights.sum()
    else:
        denom = cold_prior.sum()
        shape = cold_prior / denom if denom > 0 else np.zeros(144)
    forecast = total_hat / DT_HOURS * shape
    # A point that has remained zero throughout the recent window is treated as night.
    forecast[np.all(recent == 0, axis=0)] = 0.0
    return np.maximum(forecast, 0.0)


def rolling_forecasts(data: Q2Data, cfg: ForecastConfig = ForecastConfig()):
    q1 = read_attachment1()
    cold_load = np.roll(q1.load_kw, -1)
    cold_pv = np.roll(q1.pv_kw, -1)
    n, t = data.source_load_kw.shape
    load_base = np.empty((n, t))
    load_hat = np.empty((n, t))
    pv_hat = np.empty((n, t))
    for d in range(n):
        base = _load_base(data.source_load_kw, data.dates, d, cfg, cold_load)
        load_base[d] = base
        if d >= cfg.minimum_regression_days:
            X = _date_features(list(data.dates[:d]), cfg.load_fourier_order)
            x = _date_features([data.dates[d]], cfg.load_fourier_order)[0]
            correction = _ridge_predict(X, data.source_load_kw[:d] - load_base[:d], x, cfg.load_ridge)
        else:
            correction = np.zeros(t)
        load_hat[d] = np.maximum(base + correction, 0.0)
        pv_hat[d] = _pv_forecast(data.source_pv_kw, data.dates, d, cfg, cold_pv)
    return load_hat, pv_hat


def next_day_forecast(data: Q2Data, cfg: ForecastConfig = ForecastConfig()):
    """Forecast the day immediately after the last observation without leakage."""
    q1 = read_attachment1()
    target = data.dates[-1] + timedelta(days=1)
    dates = data.dates + (target,)
    n, t = data.load_kw.shape
    load_base = np.empty((n + 1, t))
    for d in range(n + 1):
        load_base[d] = _load_base(data.load_kw, dates, d, cfg, q1.load_kw)
    X = _date_features(list(dates[:n]), cfg.load_fourier_order)
    x = _date_features([target], cfg.load_fourier_order)[0]
    correction = _ridge_predict(
        X, data.load_kw - load_base[:n], x, cfg.load_ridge
    )
    load_hat = np.maximum(load_base[n] + correction, 0.0)
    pv_hat = _pv_forecast(data.pv_kw, dates, n, cfg, q1.pv_kw)
    return target, load_hat, pv_hat


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = pred - actual
    daily_actual = DT_HOURS * actual.sum(axis=1)
    daily_pred = DT_HOURS * pred.sum(axis=1)
    return {
        "mae_kw": float(np.mean(np.abs(err))),
        "rmse_kw": float(np.sqrt(np.mean(err ** 2))),
        "daily_energy_mape": float(np.mean(np.abs(daily_pred - daily_actual) / np.maximum(daily_actual, 1e-12))),
    }


def save_forecasts(output_dir: Path = ROOT / "outputs" / "q2"):
    data = load_q2_data()
    cfg = ForecastConfig()
    load_hat, pv_hat = rolling_forecasts(data, cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_dir / "rolling_forecasts.npz", load_kw=load_hat, pv_kw=pv_hat, time_axis="shifted_0010")
    evaluation = slice(31, 365)
    summary = {
        "information_boundary": "forecast d covers 00:10 through next 00:00 samples; history includes observations through d 00:00",
        "cold_start": "Attachment 1 profile used only for 2025-01-01 prior",
        "config": asdict(cfg),
        "evaluation_period": ["2025-02-01", "2025-12-31"],
        "load": _metrics(data.source_load_kw[evaluation], load_hat[evaluation]),
        "pv": _metrics(data.source_pv_kw[evaluation], pv_hat[evaluation]),
    }
    (output_dir / "forecast_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(save_forecasts(), ensure_ascii=False, indent=2))
