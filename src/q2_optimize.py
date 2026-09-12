"""Day-ahead stochastic optimization and ex-post settlement for Question 2."""

from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import csv
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
try:
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
except ModuleNotFoundError:
    sys.path.insert(0, str(ROOT / "tmp" / "q2_trial_deps"))
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix

from data_loader import DT_HOURS
from q2_data import load_q2_data, natural_interval_labels
from q2_forecast import save_forecasts


T = 144
ETA_C = 0.9
ETA_D = 0.9
E_MIN = 1200.0
E_MAX = 10800.0
Q_MAX = 5000.0 * DT_HOURS


@dataclass(frozen=True)
class OptimizationConfig:
    scenario_count: int = 30
    residual_window_days: int = 60
    residual_half_life_days: float = 30.0
    same_weekday_multiplier: float = 3.0
    cvar_alpha: float = 0.90
    cvar_weight: float = 0.10
    # One stored kWh can yield ETA_D kWh next day.  The continuation value is
    # therefore anchored to ETA_D times the unrounded mean tariff.
    terminal_energy_value: float = 0.6895775
    random_seed: int = 20260912


def scenarios_for_day(d, dates, actual_load, actual_pv, load_hat, pv_hat,
                      cfg: OptimizationConfig):
    if d == 0:
        return load_hat[d:d+1] * DT_HOURS, pv_hat[d:d+1] * DT_HOURS
    start = max(0, d - cfg.residual_window_days)
    pool = np.arange(start, d)
    ages = d - pool
    weights = 0.5 ** (ages / cfg.residual_half_life_days)
    weights *= np.where(
        [dates[j].weekday() == dates[d].weekday() for j in pool],
        cfg.same_weekday_multiplier, 1.0,
    )
    weights /= weights.sum()
    rng = np.random.default_rng(cfg.random_seed + d)
    sampled = rng.choice(pool, cfg.scenario_count, replace=True, p=weights)
    load = np.maximum(load_hat[d] + actual_load[sampled] - load_hat[sampled], 0.0)
    pv = np.maximum(pv_hat[d] + actual_pv[sampled] - pv_hat[sampled], 0.0)
    return load * DT_HOURS, pv * DT_HOURS


def solve_day(price, initial_energy, scenario_load, scenario_pv,
              cfg: OptimizationConfig):
    s_count = scenario_load.shape[0]
    i_g = np.arange(0, T)
    i_c = np.arange(T, 2*T)
    i_d = np.arange(2*T, 3*T)
    i_e = np.arange(3*T, 4*T + 1)
    b0 = 4*T + 1
    i_b = np.arange(b0, b0 + s_count*T).reshape(s_count, T)
    i_zeta = b0 + s_count*T
    i_v = np.arange(i_zeta + 1, i_zeta + 1 + s_count)
    n = i_v[-1] + 1

    objective = np.zeros(n)
    objective[i_g] = price
    objective[i_b.ravel()] = np.tile(5.0 * price / s_count, s_count)
    objective[i_e[-1]] = -cfg.terminal_energy_value
    objective[i_zeta] = cfg.cvar_weight
    objective[i_v] = cfg.cvar_weight / ((1.0 - cfg.cvar_alpha) * s_count)

    aeq = lil_matrix((T + 1, n))
    beq = np.zeros(T + 1)
    for t in range(T):
        aeq[t, i_e[t+1]] = 1.0
        aeq[t, i_e[t]] = -1.0
        aeq[t, i_c[t]] = -ETA_C
        aeq[t, i_d[t]] = 1.0 / ETA_D
    aeq[T, i_e[0]] = 1.0
    beq[T] = initial_energy

    aub = lil_matrix((s_count*T + s_count, n))
    bub = np.zeros(s_count*T + s_count)
    for s in range(s_count):
        for t in range(T):
            row = s*T + t
            # G + PV + D + B >= L + C
            aub[row, i_g[t]] = -1.0
            aub[row, i_c[t]] = 1.0
            aub[row, i_d[t]] = -1.0
            aub[row, i_b[s,t]] = -1.0
            bub[row] = scenario_pv[s,t] - scenario_load[s,t]
        row = s_count*T + s
        aub[row, i_b[s]] = 5.0 * price
        aub[row, i_zeta] = -1.0
        aub[row, i_v[s]] = -1.0

    bounds = [(0.0, None)] * n
    for i in i_c: bounds[i] = (0.0, Q_MAX)
    for i in i_d: bounds[i] = (0.0, Q_MAX)
    for i in i_e: bounds[i] = (E_MIN, E_MAX)
    bounds[i_zeta] = (0.0, None)
    result = linprog(
        objective, A_ub=aub.tocsr(), b_ub=bub,
        A_eq=aeq.tocsr(), b_eq=beq, bounds=bounds, method="highs",
    )
    if not result.success:
        raise RuntimeError(result.message)
    x = result.x
    charge, discharge = x[i_c], x[i_d]
    simultaneous = int(np.sum((charge > 1e-7) & (discharge > 1e-7)))
    return {
        "purchase": x[i_g], "charge": charge, "discharge": discharge,
        "energy": x[i_e], "scenario_emergency": x[i_b],
        "zeta": float(x[i_zeta]), "objective": float(result.fun),
        "simultaneous": simultaneous,
    }


def run(cfg=OptimizationConfig(cvar_weight=0.05), start_day=31, end_day=365,
        output_dir=ROOT / "outputs" / "q2", save_detail=True):
    from q2_dispatch import run as shifted_run
    return shifted_run(cfg, start_day, end_day, output_dir, save_detail)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-day", type=int, default=365)
    parser.add_argument("--start-day", type=int, default=31)
    parser.add_argument("--scenario-count", type=int, default=30)
    parser.add_argument("--risk-weight", type=float, default=0.05)
    parser.add_argument("--cvar-alpha", type=float, default=0.90)
    parser.add_argument("--terminal-value", type=float, default=0.6895775)
    args = parser.parse_args()
    cfg = OptimizationConfig(
        scenario_count=args.scenario_count, cvar_weight=args.risk_weight,
        cvar_alpha=args.cvar_alpha, terminal_energy_value=args.terminal_value,
    )
    print(json.dumps(run(cfg, args.start_day, args.end_day), ensure_ascii=False, indent=2))
