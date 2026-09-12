"""Strict baseline comparison for the saved Q2 rolling forecasts."""

from pathlib import Path
import csv
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from data_loader import DT_HOURS
from q2_data import load_q2_data


def metrics(actual, pred):
    error = pred - actual
    actual_energy = DT_HOURS * actual.sum(axis=1)
    pred_energy = DT_HOURS * pred.sum(axis=1)
    return {
        "mae_kw": float(np.mean(np.abs(error))),
        "rmse_kw": float(np.sqrt(np.mean(error**2))),
        "daily_energy_mape": float(np.mean(np.abs(pred_energy-actual_energy)/np.maximum(actual_energy,1e-12))),
    }


def main():
    data = load_q2_data()
    f = np.load(ROOT / "outputs" / "q2" / "rolling_forecasts.npz")
    sl = slice(31,365)
    rows=[]
    for target, actual, primary in [
        ("负载",data.load_kw,f["load_kw"]), ("光伏",data.pv_kw,f["pv_kw"])
    ]:
        candidates = {
            "前一日曲线": np.vstack((actual[0],actual[:-1])),
            "上一同星期日曲线": np.vstack((actual[:7],actual[:-7])),
            "修订版主模型": primary,
        }
        for name,pred in candidates.items():
            rows.append({"target":target,"model":name,**metrics(actual[sl],pred[sl])})
    out=ROOT/"outputs"/"q2"
    with (out/"forecast_model_comparison.csv").open("w",newline="",encoding="utf-8-sig") as f0:
        writer=csv.DictWriter(f0,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    (out/"forecast_model_comparison.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
