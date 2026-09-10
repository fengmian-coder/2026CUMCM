"""Finite-horizon dynamic programming solver for question 1.

The battery state is discretized, and each transition chooses the next state.
Results are compared with the continuous MILP optimum and saved for the paper's
model-comparison section.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from data_loader import PROJECT_ROOT, read_attachment1


T = 144
ETA_C = 0.9
ETA_D = 0.9
E_MIN = 1200.0
E_MAX = 10800.0
E_INITIAL = 6000.0
Q_MAX = 5000.0 / 6.0
TOL = 1e-8


@dataclass
class DPSolution:
    step_kwh: float
    total_cost: float
    total_purchase: float
    purchase: np.ndarray
    charge: np.ndarray
    discharge: np.ndarray
    curtailment: np.ndarray
    energy: np.ndarray


def _state_grid(step_kwh: float) -> np.ndarray:
    count = round((E_MAX - E_MIN) / step_kwh)
    if abs(E_MIN + count * step_kwh - E_MAX) > TOL:
        raise ValueError("State step must divide the 9600 kWh usable energy range")
    states = E_MIN + np.arange(count + 1, dtype=float) * step_kwh
    if np.min(np.abs(states - E_INITIAL)) > TOL:
        raise ValueError("State grid must contain the 6000 kWh initial/final state")
    return states


def solve_dp(step_kwh: float) -> DPSolution:
    data = read_attachment1()
    price, load, pv = data.price_yuan_per_kwh, data.load_kwh, data.pv_kwh
    states = _state_grid(step_kwh)
    n_states = len(states)
    initial_index = int(np.argmin(np.abs(states - E_INITIAL)))

    # Terminal condition: only E(24:00)=6000 kWh is feasible.
    value_next = np.full(n_states, np.inf)
    value_next[initial_index] = 0.0
    policy = np.full((T, n_states), -1, dtype=np.int32)

    max_up_steps = int(np.floor((ETA_C * Q_MAX + TOL) / step_kwh))
    max_down_steps = int(np.floor((Q_MAX / ETA_D + TOL) / step_kwh))

    for t in range(T - 1, -1, -1):
        value = np.full(n_states, np.inf)
        for i, current in enumerate(states):
            lo = max(0, i - max_down_steps)
            hi = min(n_states, i + max_up_steps + 1)
            candidates = states[lo:hi]
            delta = candidates - current
            charge = np.maximum(delta, 0.0) / ETA_C
            discharge = np.maximum(-delta, 0.0) * ETA_D
            residual = load[t] + charge - pv[t] - discharge
            purchase = np.maximum(residual, 0.0)
            curtailment = np.maximum(-residual, 0.0)

            # W<=G is required: battery energy cannot be dumped and called PV curtailment.
            feasible = curtailment <= pv[t] + TOL
            total = price[t] * purchase + value_next[lo:hi]
            total = np.where(feasible, total, np.inf)
            local = int(np.argmin(total))
            if np.isfinite(total[local]):
                value[i] = total[local]
                policy[t, i] = lo + local
        value_next = value

    if not np.isfinite(value_next[initial_index]):
        raise RuntimeError(f"No feasible DP path for step {step_kwh} kWh")

    energy = np.empty(T + 1)
    purchase = np.empty(T)
    charge = np.empty(T)
    discharge = np.empty(T)
    curtailment = np.empty(T)
    energy[0] = E_INITIAL
    state_index = initial_index
    for t in range(T):
        next_index = int(policy[t, state_index])
        if next_index < 0:
            raise RuntimeError("Broken DP policy during forward recovery")
        energy[t + 1] = states[next_index]
        delta = energy[t + 1] - energy[t]
        charge[t] = max(delta, 0.0) / ETA_C
        discharge[t] = max(-delta, 0.0) * ETA_D
        residual = load[t] + charge[t] - pv[t] - discharge[t]
        purchase[t] = max(residual, 0.0)
        curtailment[t] = max(-residual, 0.0)
        state_index = next_index

    return DPSolution(
        step_kwh=step_kwh,
        total_cost=float(price @ purchase),
        total_purchase=float(purchase.sum()),
        purchase=purchase,
        charge=charge,
        discharge=discharge,
        curtailment=curtailment,
        energy=energy,
    )


def validate_solution(solution: DPSolution):
    data = read_attachment1()
    balance = (
        solution.purchase
        + data.pv_kwh
        + solution.discharge
        - data.load_kwh
        - solution.charge
        - solution.curtailment
    )
    state = (
        solution.energy[1:]
        - solution.energy[:-1]
        - ETA_C * solution.charge
        + solution.discharge / ETA_D
    )
    checks = {
        "max_balance_error_kwh": float(np.abs(balance).max()),
        "max_state_error_kwh": float(np.abs(state).max()),
        "energy_min_kwh": float(solution.energy.min()),
        "energy_max_kwh": float(solution.energy.max()),
        "energy_initial_kwh": float(solution.energy[0]),
        "energy_final_kwh": float(solution.energy[-1]),
        "max_charge_kwh": float(solution.charge.max()),
        "max_discharge_kwh": float(solution.discharge.max()),
        "simultaneous_slots": int(
            np.sum((solution.charge > TOL) & (solution.discharge > TOL))
        ),
        "curtailment_exceeds_pv_slots": int(
            np.sum(solution.curtailment > data.pv_kwh + TOL)
        ),
    }
    if checks["max_balance_error_kwh"] > 1e-6:
        raise AssertionError(checks)
    if checks["max_state_error_kwh"] > 1e-6:
        raise AssertionError(checks)
    if checks["energy_min_kwh"] < E_MIN - 1e-6 or checks["energy_max_kwh"] > E_MAX + 1e-6:
        raise AssertionError(checks)
    if abs(checks["energy_final_kwh"] - E_INITIAL) > 1e-6:
        raise AssertionError(checks)
    if checks["max_charge_kwh"] > Q_MAX + 1e-6 or checks["max_discharge_kwh"] > Q_MAX + 1e-6:
        raise AssertionError(checks)
    if checks["simultaneous_slots"] or checks["curtailment_exceeds_pv_slots"]:
        raise AssertionError(checks)
    return checks


def save_schedule(path: Path, solution: DPSolution):
    data = read_attachment1()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "时段序号",
                "时间段",
                "电价(元/kWh)",
                "负载电量(kWh)",
                "光伏电量(kWh)",
                "购电量(kWh)",
                "充电量(kWh)",
                "放电量(kWh)",
                "弃光量(kWh)",
                "期初储电量(kWh)",
                "期末储电量(kWh)",
                "购电费用(元)",
            ]
        )
        for t in range(T):
            writer.writerow(
                [
                    t + 1,
                    data.interval_labels[t],
                    data.price_yuan_per_kwh[t],
                    data.load_kwh[t],
                    data.pv_kwh[t],
                    solution.purchase[t],
                    solution.charge[t],
                    solution.discharge[t],
                    solution.curtailment[t],
                    solution.energy[t],
                    solution.energy[t + 1],
                    data.price_yuan_per_kwh[t] * solution.purchase[t],
                ]
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--steps", nargs="+", type=float, default=[200, 100, 50, 20, 10, 5]
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs" / "q1_dp"
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    solutions = []
    comparison = []
    for step in args.steps:
        solution = solve_dp(step)
        checks = validate_solution(solution)
        solutions.append(solution)
        comparison.append(
            {
                "state_step_kwh": step,
                "state_count": len(_state_grid(step)),
                "total_cost_yuan": solution.total_cost,
                "total_purchase_kwh": solution.total_purchase,
                "total_charge_kwh": float(solution.charge.sum()),
                "total_discharge_kwh": float(solution.discharge.sum()),
                "total_curtailment_kwh": float(solution.curtailment.sum()),
                **checks,
            }
        )
        print(
            f"step={step:g} kWh, cost={solution.total_cost:.6f}, "
            f"purchase={solution.total_purchase:.6f}"
        )

    # Continuous optimum from the independently verified MILP implementation.
    try:
        from verify_q1 import solve as solve_milp

        milp = solve_milp()
        milp_cost = milp["optimal_cost"]
        milp_purchase = milp["optimal_purchase"]
        for row in comparison:
            row["cost_gap_vs_milp_yuan"] = row["total_cost_yuan"] - milp_cost
            row["relative_cost_gap_vs_milp"] = row["total_cost_yuan"] / milp_cost - 1
    except (ImportError, ModuleNotFoundError):
        milp_cost = None
        milp_purchase = None

    comparison_file = args.output_dir / "dp_convergence.csv"
    with comparison_file.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    finest = solutions[int(np.argmin([s.step_kwh for s in solutions]))]
    save_schedule(args.output_dir / "dp_schedule_finest_grid.csv", finest)
    summary = {
        "method": "finite-horizon dynamic programming with battery-state discretization",
        "finest_state_step_kwh": finest.step_kwh,
        "finest_total_cost_yuan": finest.total_cost,
        "finest_total_purchase_kwh": finest.total_purchase,
        "milp_total_cost_yuan": milp_cost,
        "milp_total_purchase_kwh": milp_purchase,
        "finest_cost_gap_vs_milp_yuan": None if milp_cost is None else finest.total_cost - milp_cost,
        "time_interpretation": "Excel timestamps are right endpoints; 00:10 means 00:00-00:10",
        "efficiency": {"charge": ETA_C, "discharge": ETA_D},
        "state_bounds_kwh": [E_MIN, E_MAX],
        "initial_and_final_energy_kwh": E_INITIAL,
    }
    (args.output_dir / "dp_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
