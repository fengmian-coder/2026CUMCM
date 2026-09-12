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
    sys.path.append(str(ROOT / "tmp" / "pydeps"))
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


def run(cfg=OptimizationConfig(), start_day=0, end_day=365,
        output_dir=ROOT / "outputs" / "q2", save_detail=True):
    data = load_q2_data()
    # Forecasts do not depend on optimization parameters.  Keep one canonical
    # copy so sensitivity cases cannot silently regenerate different inputs.
    forecast_file = ROOT / "outputs" / "q2" / "rolling_forecasts.npz"
    if not forecast_file.exists():
        save_forecasts(forecast_file.parent)
    forecasts = np.load(forecast_file)
    load_hat, pv_hat = forecasts["load_kw"], forecasts["pv_kw"]
    labels = natural_interval_labels()
    output_dir.mkdir(parents=True, exist_ok=True)

    energy0 = 6000.0
    all_rows = []
    daily_rows = []
    schedules = []
    for d in range(0, end_day):
        scenario_load, scenario_pv = scenarios_for_day(
            d, data.dates, data.load_kw, data.pv_kw, load_hat, pv_hat, cfg
        )
        solution = solve_day(data.price_yuan_per_kwh, energy0, scenario_load, scenario_pv, cfg)
        g, c, u, e = (solution[k] for k in ("purchase", "charge", "discharge", "energy"))
        real_load, real_pv = data.load_kwh[d], data.pv_kwh[d]
        shortage = real_load + c - g - real_pv - u
        emergency = np.maximum(shortage, 0.0)
        surplus = np.maximum(-shortage, 0.0)
        plan_cost = float(data.price_yuan_per_kwh @ g)
        emergency_cost = float((5.0 * data.price_yuan_per_kwh) @ emergency)
        balance_error = g + real_pv + u + emergency - real_load - c - surplus
        state_error = e[1:] - e[:-1] - ETA_C*c + u/ETA_D
        schedules.append({"purchase":g,"charge":c,"discharge":u,"energy":e,
                          "emergency":emergency,"surplus":surplus})
        if d >= start_day:
            for t in range(T):
                all_rows.append([
                    data.dates[d].isoformat(), t+1, labels[t], data.price_yuan_per_kwh[t],
                    load_hat[d,t], pv_hat[d,t], data.load_kw[d,t], data.pv_kw[d,t],
                    g[t], c[t], u[t], emergency[t], surplus[t], e[t], e[t+1],
                ])
            daily_rows.append({
                "date": data.dates[d].isoformat(), "initial_energy_kwh": float(e[0]),
                "final_energy_kwh": float(e[-1]), "plan_purchase_kwh": float(g.sum()),
                "plan_cost_yuan": plan_cost, "emergency_purchase_kwh": float(emergency.sum()),
                "emergency_cost_yuan": emergency_cost, "actual_total_cost_yuan": plan_cost+emergency_cost,
                "surplus_kwh": float(surplus.sum()), "charge_kwh": float(c.sum()),
                "discharge_kwh": float(u.sum()), "max_balance_error": float(np.max(np.abs(balance_error))),
                "max_state_error": float(np.max(np.abs(state_error))),
                "simultaneous_slots": solution["simultaneous"],
            })
        energy0 = float(e[-1])

    if save_detail:
        schedule_path = output_dir / "q2_schedule.csv"
        with schedule_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["日期","时段序号","自然日时段","电价(元/kWh)","预测负载功率(kW)",
                             "预测光伏功率(kW)","实际负载功率(kW)","实际光伏功率(kW)",
                             "计划购电量(kWh)","计划充电量(kWh)","计划放电量(kWh)",
                             "紧急购电量(kWh)","剩余电量(kWh)","期初储电量(kWh)","期末储电量(kWh)"])
            writer.writerows(all_rows)
        (output_dir / "q2_daily_summary.json").write_text(
            json.dumps(daily_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    summary = {
        "config": asdict(cfg), "output_period": [daily_rows[0]["date"], daily_rows[-1]["date"]],
        "days": len(daily_rows), "plan_cost_yuan": sum(x["plan_cost_yuan"] for x in daily_rows),
        "emergency_cost_yuan": sum(x["emergency_cost_yuan"] for x in daily_rows),
        "total_cost_yuan": sum(x["actual_total_cost_yuan"] for x in daily_rows),
        "emergency_purchase_kwh": sum(x["emergency_purchase_kwh"] for x in daily_rows),
        "emergency_days": sum(x["emergency_purchase_kwh"] > 1e-7 for x in daily_rows),
        "surplus_kwh": sum(x["surplus_kwh"] for x in daily_rows),
        "charge_kwh": sum(x["charge_kwh"] for x in daily_rows),
        "discharge_kwh": sum(x["discharge_kwh"] for x in daily_rows),
        "max_balance_error": max(x["max_balance_error"] for x in daily_rows),
        "max_state_error": max(x["max_state_error"] for x in daily_rows),
        "simultaneous_slots": sum(x["simultaneous_slots"] for x in daily_rows),
        "energy_min_kwh": min(float(s["energy"].min()) for s in schedules),
        "energy_max_kwh": max(float(s["energy"].max()) for s in schedules),
        "initial_energy_kwh": float(schedules[0]["energy"][0]),
        "final_energy_kwh": float(schedules[-1]["energy"][-1]),
    }
    (output_dir / "q2_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if save_detail:
        np.savez_compressed(output_dir / "q2_schedules.npz",
            purchase=np.asarray([s["purchase"] for s in schedules]),
            charge=np.asarray([s["charge"] for s in schedules]),
            discharge=np.asarray([s["discharge"] for s in schedules]),
            energy=np.asarray([s["energy"] for s in schedules]),
            emergency=np.asarray([s["emergency"] for s in schedules]),
            surplus=np.asarray([s["surplus"] for s in schedules]))
    return summary


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
