"""Reproduce archived monthly/four-time tuning; never write current formal output."""
import run_q4 as engine
import numpy as np,json
if __name__=='__main__':
    original=engine.OUT/'archive_monthly_four_time';engine.OUT=original/'tuned'
    f=np.load(engine.OUT/'price_forecasts.npz');q=np.load(engine.ROOT/'outputs/q2/rolling_forecasts.npz')
    with np.load(original/'delayed_pv_forecasts.npz') as z:F={k:z[k] for k in z.files}
    reports=[engine.run(m,engine.load_q2_data(),F,q['load_kw'],q['pv_kw'],f['pred'],f['actual'],fixed_model=None,update_hours=(6,12,18)) for m in [2,3]]
    (engine.OUT/'summary.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
