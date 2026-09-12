"""Full-period parameter checks for the Q2 stochastic program."""

from pathlib import Path
import csv
import json

from q2_optimize import OptimizationConfig, ROOT, run


def main():
    cases = [
        ("risk_0", dict(cvar_weight=0.0)),
        ("risk_005", dict(cvar_weight=0.05)),
        ("risk_010", dict(cvar_weight=0.10)),
        ("risk_020", dict(cvar_weight=0.20)),
        ("scenarios_20", dict(scenario_count=20, cvar_weight=0.10)),
        ("scenarios_50", dict(scenario_count=50, cvar_weight=0.10)),
    ]
    folder = ROOT / "outputs" / "q2" / "sensitivity"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, changes in cases:
        cfg = OptimizationConfig(**changes)
        summary = run(cfg, start_day=31, end_day=365,
                      output_dir=folder / name, save_detail=False)
        rows.append({"case": name, **summary})
        print(name, summary["total_cost_yuan"], summary["emergency_purchase_kwh"])
    with (folder / "sensitivity_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["case","plan_cost_yuan","emergency_cost_yuan","total_cost_yuan",
                  "emergency_purchase_kwh","emergency_days","energy_min_kwh",
                  "energy_max_kwh","final_energy_kwh","simultaneous_slots"]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    (folder / "sensitivity_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
