"""Check how the daily terminal-energy value affects the Q2 policy."""

from pathlib import Path
import csv
import json

from q2_optimize import OptimizationConfig, ROOT, run


def main():
    values = (0.0, 0.60, 0.6895775, 0.75, 0.8860275, 1.00)
    folder = ROOT / "outputs" / "q2" / "terminal_sensitivity"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for value in values:
        name = f"terminal_{value:.7f}".replace(".", "p")
        cfg = OptimizationConfig(cvar_weight=0.05, terminal_energy_value=value)
        summary = run(
            cfg, start_day=31, end_day=365,
            output_dir=folder / name, save_detail=False,
        )
        rows.append({"terminal_energy_value_yuan_per_kwh": value, **summary})
        print(value, summary["total_cost_yuan"], summary["final_energy_kwh"])

    fields = [
        "terminal_energy_value_yuan_per_kwh", "plan_cost_yuan",
        "emergency_cost_yuan", "total_cost_yuan", "emergency_purchase_kwh",
        "surplus_kwh", "charge_kwh", "discharge_kwh", "energy_min_kwh",
        "energy_max_kwh", "final_energy_kwh", "simultaneous_slots",
    ]
    with (folder / "terminal_sensitivity.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (folder / "terminal_sensitivity.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
