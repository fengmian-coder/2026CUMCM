"""Generate the first natural-day interval after the 2025 Q2 simulation."""

from dataclasses import asdict
import json

import numpy as np

from data_loader import DT_HOURS
from q2_data import load_q2_data
from q2_forecast import ForecastConfig, next_day_forecast
from q2_optimize import OptimizationConfig, ROOT, scenarios_for_day, solve_day


def main():
    data = load_q2_data()
    forecast_cfg = ForecastConfig()
    target_date, next_load, next_pv = next_day_forecast(data, forecast_cfg)
    saved_forecast = np.load(ROOT / "outputs" / "q2" / "rolling_forecasts.npz")
    load_hat = np.vstack((saved_forecast["load_kw"], next_load))
    pv_hat = np.vstack((saved_forecast["pv_kw"], next_pv))
    dates = data.dates + (target_date,)
    cfg = OptimizationConfig(cvar_weight=0.05)
    scenario_load, scenario_pv = scenarios_for_day(
        365, dates, data.load_kw, data.pv_kw, load_hat, pv_hat, cfg
    )
    schedules = np.load(ROOT / "outputs" / "q2" / "q2_schedules.npz")
    initial_energy = float(schedules["energy"][-1, -1])
    solution = solve_day(
        data.price_yuan_per_kwh, initial_energy,
        scenario_load, scenario_pv, cfg,
    )
    out = ROOT / "outputs" / "q2"
    np.savez_compressed(
        out / "q2_extension_2026-01-01.npz",
        purchase=solution["purchase"], charge=solution["charge"],
        discharge=solution["discharge"], energy=solution["energy"],
        forecast_load_kw=next_load, forecast_pv_kw=next_pv,
    )
    report = {
        "date": target_date.isoformat(),
        "purpose": "supply the result2.xlsx final 00:00-00:10+1 column",
        "information_boundary": "uses observations through 2025-12-31 only",
        "optimization_config": asdict(cfg),
        "forecast_config": asdict(forecast_cfg),
        "initial_energy_kwh": initial_energy,
        "first_interval": {
            "forecast_load_kw": float(next_load[0]),
            "forecast_pv_kw": float(next_pv[0]),
            "purchase_kwh": float(solution["purchase"][0]),
            "charge_kwh": float(solution["charge"][0]),
            "discharge_kwh": float(solution["discharge"][0]),
            "end_energy_kwh": float(solution["energy"][1]),
        },
    }
    (out / "q2_extension_2026-01-01.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
