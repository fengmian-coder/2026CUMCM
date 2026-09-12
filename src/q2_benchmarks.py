"""Comparable no-storage and perfect-information references for Question 2."""

from dataclasses import asdict
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
try:
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
except ModuleNotFoundError:
    sys.path.append(str(ROOT / "tmp" / "pydeps"))
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix

from data_loader import DT_HOURS
from q2_data import load_q2_data
from q2_optimize import OptimizationConfig, scenarios_for_day, solve_day


T = 144


def solve_no_storage_day(price, scenario_load, scenario_pv, cfg):
    """Use the same scenario/CVaR structure while fixing storage at zero."""
    s_count = scenario_load.shape[0]
    i_g = np.arange(T)
    b0 = T
    i_b = np.arange(b0, b0 + s_count*T).reshape(s_count, T)
    i_zeta = b0 + s_count*T
    i_v = np.arange(i_zeta + 1, i_zeta + 1 + s_count)
    n = i_v[-1] + 1

    objective = np.zeros(n)
    objective[i_g] = price
    objective[i_b.ravel()] = np.tile(5.0 * price / s_count, s_count)
    objective[i_zeta] = cfg.cvar_weight
    objective[i_v] = cfg.cvar_weight / ((1.0 - cfg.cvar_alpha) * s_count)

    aub = lil_matrix((s_count*T + s_count, n))
    bub = np.zeros(s_count*T + s_count)
    for s in range(s_count):
        for t in range(T):
            row = s*T + t
            aub[row, i_g[t]] = -1.0
            aub[row, i_b[s, t]] = -1.0
            bub[row] = scenario_pv[s, t] - scenario_load[s, t]
        row = s_count*T + s
        aub[row, i_b[s]] = 5.0 * price
        aub[row, i_zeta] = -1.0
        aub[row, i_v[s]] = -1.0

    result = linprog(
        objective, A_ub=aub.tocsr(), b_ub=bub,
        bounds=[(0.0, None)] * n, method="highs",
    )
    if not result.success:
        raise RuntimeError(result.message)
    return result.x[i_g]


def aggregate_settlement(price, plans, actual_load_kwh, actual_pv_kwh):
    shortage = actual_load_kwh - plans - actual_pv_kwh
    emergency = np.maximum(shortage, 0.0)
    surplus = np.maximum(-shortage, 0.0)
    plan_cost = float(np.sum(plans * price[None, :]))
    emergency_cost = float(np.sum(emergency * (5.0 * price)[None, :]))
    return {
        "plan_cost_yuan": plan_cost,
        "emergency_cost_yuan": emergency_cost,
        "total_cost_yuan": plan_cost + emergency_cost,
        "emergency_purchase_kwh": float(emergency.sum()),
        "surplus_kwh": float(surplus.sum()),
    }


def main():
    cfg = OptimizationConfig(cvar_weight=0.05)
    data = load_q2_data()
    forecasts = np.load(ROOT / "outputs" / "q2" / "rolling_forecasts.npz")
    load_hat, pv_hat = forecasts["load_kw"], forecasts["pv_kw"]

    no_storage = []
    oracle = []
    oracle_energy0 = 6000.0
    for d in range(365):
        scenario_load, scenario_pv = scenarios_for_day(
            d, data.dates, data.load_kw, data.pv_kw, load_hat, pv_hat, cfg
        )
        no_storage.append(
            solve_no_storage_day(data.price_yuan_per_kwh, scenario_load, scenario_pv, cfg)
        )
        actual_load = data.load_kwh[d:d+1]
        actual_pv = data.pv_kwh[d:d+1]
        solved = solve_day(
            data.price_yuan_per_kwh, oracle_energy0, actual_load, actual_pv, cfg
        )
        oracle.append(solved)
        oracle_energy0 = float(solved["energy"][-1])

    start = 31
    no_storage_plans = np.asarray(no_storage)[start:]
    result_no_storage = aggregate_settlement(
        data.price_yuan_per_kwh, no_storage_plans,
        data.load_kwh[start:], data.pv_kwh[start:],
    )

    oracle_slice = oracle[start:]
    g = np.asarray([x["purchase"] for x in oracle_slice])
    c = np.asarray([x["charge"] for x in oracle_slice])
    u = np.asarray([x["discharge"] for x in oracle_slice])
    e = np.asarray([x["energy"] for x in oracle_slice])
    shortage = data.load_kwh[start:] + c - g - data.pv_kwh[start:] - u
    emergency = np.maximum(shortage, 0.0)
    surplus = np.maximum(-shortage, 0.0)
    oracle_plan_cost = float(np.sum(g * data.price_yuan_per_kwh[None, :]))
    oracle_emergency_cost = float(
        np.sum(emergency * (5.0 * data.price_yuan_per_kwh)[None, :])
    )
    result_oracle = {
        "plan_cost_yuan": oracle_plan_cost,
        "emergency_cost_yuan": oracle_emergency_cost,
        "total_cost_yuan": oracle_plan_cost + oracle_emergency_cost,
        "emergency_purchase_kwh": float(emergency.sum()),
        "surplus_kwh": float(surplus.sum()),
        "charge_kwh": float(c.sum()),
        "discharge_kwh": float(u.sum()),
        "final_energy_kwh": float(e[-1, -1]),
    }

    actual = json.loads((ROOT / "outputs" / "q2" / "q2_summary.json").read_text("utf-8"))
    report = {
        "config": asdict(cfg),
        "period": [data.dates[start].isoformat(), data.dates[-1].isoformat()],
        "no_storage_same_information": result_no_storage,
        "proposed_stochastic_storage": {
            key: actual[key] for key in (
                "plan_cost_yuan", "emergency_cost_yuan", "total_cost_yuan",
                "emergency_purchase_kwh", "surplus_kwh", "charge_kwh",
                "discharge_kwh", "final_energy_kwh",
            )
        },
        "perfect_information_storage_reference": result_oracle,
    }
    actual_total = report["proposed_stochastic_storage"]["total_cost_yuan"]
    no_storage_total = result_no_storage["total_cost_yuan"]
    oracle_total = result_oracle["total_cost_yuan"]
    report["derived"] = {
        "saving_vs_no_storage_yuan": no_storage_total - actual_total,
        "saving_vs_no_storage_fraction": (no_storage_total - actual_total) / no_storage_total,
        "forecast_uncertainty_cost_gap_yuan": actual_total - oracle_total,
    }
    output = ROOT / "outputs" / "q2" / "benchmark_summary.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
