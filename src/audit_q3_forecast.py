"""Perturb future samples and future forecast issues to verify causal selection."""
from pathlib import Path
from dataclasses import replace
import json
import numpy as np
from q2_data import load_q2_data
from q3_forecast import attachment3,build

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    data=load_q2_data();a3=attachment3(data.dates)
    with np.load(ROOT/'outputs/q2/rolling_forecasts.npz') as f:q=f['pv_kw']
    d=171;ri=2;start=72
    source=data.source_pv_kw.copy();source[d,start:]+=10000;source[d+1:]+=20000
    a3[d,ri+1:]+=5000;a3[d+1:]+=5000
    changed=replace(data,source_pv_kw=source)
    test,_=build(28,changed,q,a3)
    original=np.load(ROOT/'outputs/q3/forecasts_w28.npz')
    for k in ('pred','kind','weight'):
        np.testing.assert_array_equal(test[k][:d],original[k][:d])
        np.testing.assert_array_equal(test[k][d,:ri+1],original[k][d,:ri+1])
    report={'perturbation_start':'2025-06-21 12:10','future_actuals_and_later_issues_changed':True,
            'all_earlier_predictions_and_selections_unchanged':True,
            'current_noon_prediction_and_selection_unchanged':True,
            'note':'Q2 base forecasts are frozen inputs; their causality is separately audited in Q2'}
    (ROOT/'outputs/q3/forecast_causality_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
