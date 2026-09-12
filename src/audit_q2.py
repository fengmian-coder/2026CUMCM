"""Independent numerical audit of saved Question 2 results."""

from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from data_loader import DT_HOURS
from q2_data import load_q2_data
ETA_C = 0.9
ETA_D = 0.9
E_MIN = 1200.0
E_MAX = 10800.0
Q_MAX = 5000.0 * DT_HOURS


def main():
    data = load_q2_data()
    out = ROOT / "outputs" / "q2"
    saved = np.load(out / "q2_schedules.npz")
    purchase, charge, discharge = saved["purchase"], saved["charge"], saved["discharge"]
    energy, emergency, surplus = saved["energy"], saved["emergency"], saved["surplus"]
    assert purchase.shape == charge.shape == discharge.shape == emergency.shape == surplus.shape == (365, 144)
    assert energy.shape == (365, 145)

    load, pv = data.source_load_kw * DT_HOURS, data.source_pv_kw * DT_HOURS
    balance = purchase + pv + discharge + emergency - load - charge - surplus
    state = energy[:,1:] - energy[:,:-1] - ETA_C*charge + discharge/ETA_D
    continuity = energy[:-1,-1] - energy[1:,0]
    first_boundary = {
        "load_kw": float(data.load_kw[0,0]), "source_0010_load_kw": float(data.source_load_kw[0,0]),
        "pv_kw": float(data.pv_kw[0,0]), "source_0010_pv_kw": float(data.source_pv_kw[0,0]),
    }
    predecessor_load = np.max(np.abs(data.load_kw[1:,0] - data.source_load_kw[:-1,-1]))
    predecessor_pv = np.max(np.abs(data.pv_kw[1:,0] - data.source_pv_kw[:-1,-1]))
    same_day_load = np.max(np.abs(data.load_kw[:,1:] - data.source_load_kw[:,:-1]))
    same_day_pv = np.max(np.abs(data.pv_kw[:,1:] - data.source_pv_kw[:,:-1]))
    natural = np.load(out / "natural_reporting.npz")
    evaluation = slice(31,365)
    price = data.price_yuan_per_kwh
    plan_cost = float(np.sum(natural["purchase"] * price))
    emergency_cost = float(np.sum(natural["emergency"] * 5*price))
    report = {
        "dimensions": {"days":365,"intervals_per_day":144,"energy_boundaries_per_day":145},
        "left_endpoint_mapping": {
            "initial_boundary": "First Jan 1 interval idle; 6000 kWh at 00:00 and 00:10; no imputed midnight input used in forecasting",
            "predecessor_load_max_abs_error": float(predecessor_load),
            "predecessor_pv_max_abs_error": float(predecessor_pv),
            "same_day_load_max_abs_error": float(same_day_load),
            "same_day_pv_max_abs_error": float(same_day_pv),
        },
        "constraints": {
            "max_balance_error": float(np.max(np.abs(balance))),
            "max_state_error": float(np.max(np.abs(state))),
            "max_cross_day_continuity_error": float(np.max(np.abs(continuity))),
            "energy_min": float(energy.min()), "energy_max": float(energy.max()),
            "max_charge": float(charge.max()), "max_discharge": float(discharge.max()),
            "simultaneous_slots": int(np.sum((charge>1e-7)&(discharge>1e-7))),
            "negative_purchase_slots": int(np.sum(purchase < -1e-9)),
            "negative_emergency_slots": int(np.sum(emergency < -1e-9)),
        },
        "evaluation_totals": {
            "period":["2025-02-01","2025-12-31"], "plan_cost_yuan":plan_cost,
            "emergency_cost_yuan":emergency_cost,"total_cost_yuan":plan_cost+emergency_cost,
            "emergency_purchase_kwh":float(natural["emergency"].sum()),
            "surplus_kwh":float(natural["surplus"].sum()),
        },
    }
    assert report["left_endpoint_mapping"]["predecessor_load_max_abs_error"] == 0
    assert report["left_endpoint_mapping"]["predecessor_pv_max_abs_error"] == 0
    assert report["left_endpoint_mapping"]["same_day_load_max_abs_error"] == 0
    assert report["left_endpoint_mapping"]["same_day_pv_max_abs_error"] == 0
    assert report["constraints"]["max_balance_error"] < 1e-8
    assert report["constraints"]["max_state_error"] < 1e-8
    assert report["constraints"]["max_cross_day_continuity_error"] < 1e-8
    assert report["constraints"]["energy_min"] >= E_MIN-1e-8
    assert report["constraints"]["energy_max"] <= E_MAX+1e-8
    assert report["constraints"]["max_charge"] <= Q_MAX+1e-8
    assert report["constraints"]["max_discharge"] <= Q_MAX+1e-8
    assert report["constraints"]["simultaneous_slots"] == 0
    (out / "q2_audit_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
