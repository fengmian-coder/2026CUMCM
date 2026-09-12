"""Export exact scenario envelopes used by the Question 2 plotting script."""

from pathlib import Path
import json

import numpy as np

from data_loader import DT_HOURS
from q2_data import load_q2_data


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "q2" / "q2_figure_data.json"


def scenarios_for_day(d, dates, actual_load, actual_pv, load_hat, pv_hat):
    """Mirror q2_optimize.scenarios_for_day without importing the solver."""
    scenario_count = 30
    if d == 0:
        return load_hat[d:d + 1] * DT_HOURS, pv_hat[d:d + 1] * DT_HOURS
    start = max(0, d - 60)
    pool = np.arange(start, d)
    ages = d - pool
    weights = 0.5 ** (ages / 30.0)
    weights *= np.where(
        [dates[j].weekday() == dates[d].weekday() for j in pool], 3.0, 1.0
    )
    weights /= weights.sum()
    rng = np.random.default_rng(20260912 + d)
    sampled = rng.choice(pool, scenario_count, replace=True, p=weights)
    load = np.maximum(load_hat[d] + actual_load[sampled] - load_hat[sampled], 0.0)
    pv = np.maximum(pv_hat[d] + actual_pv[sampled] - pv_hat[sampled], 0.0)
    return load * DT_HOURS, pv * DT_HOURS


def main() -> None:
    data = load_q2_data()
    forecasts = np.load(ROOT / "outputs" / "q2" / "rolling_forecasts.npz")
    schedules = np.load(ROOT / "outputs" / "q2" / "q2_schedules.npz")
    load_hat = forecasts["load_kw"]
    pv_hat = forecasts["pv_kw"]
    selected = {"2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"}
    panels = []
    for d, current_date in enumerate(data.dates):
        date_text = current_date.isoformat()
        if date_text not in selected:
            continue
        scenario_load, scenario_pv = scenarios_for_day(
            d, data.dates, data.load_kw, data.pv_kw, load_hat, pv_hat
        )
        scenario_net_kw = (scenario_load - scenario_pv) / DT_HOURS
        panels.append({
            "date": date_text,
            "forecast_net_kw": (load_hat[d] - pv_hat[d]).tolist(),
            "actual_net_kw": (data.load_kw[d] - data.pv_kw[d]).tolist(),
            "scenario_p10_net_kw": np.quantile(scenario_net_kw, 0.10, axis=0).tolist(),
            "scenario_p90_net_kw": np.quantile(scenario_net_kw, 0.90, axis=0).tolist(),
            "planned_grid_kw": (schedules["purchase"][d] / DT_HOURS).tolist(),
        })
    OUT.write_text(
        json.dumps({"scenario_count": 30, "panels": panels},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(OUT)


if __name__ == "__main__":
    main()
