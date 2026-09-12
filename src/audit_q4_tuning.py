"""Check past-only parameter selection and future-value perturbation."""
from tune_q4_price import build,TUNED,OUT,threadpool_limits
import numpy as np,json
f=np.load(OUT/'price_forecasts.npz');target=np.load(TUNED/'price_forecasts.npz')
changed=f['actual'].copy();changed[91:]*=1.7
with threadpool_limits(limits=4):new,records=build(changed,f['pred'],end_day=92)
err=float(abs(new[:92]-target['pred'][:92]).max());assert err<1e-10
for r in json.loads((TUNED/'parameter_validation.json').read_text(encoding='utf-8')):
    assert r['validation_end']<r['date']
    assert len(r['fourier_candidates'])==8 and len(r['tree_candidates'])==12
report=dict(future_cutoff='2025-04-02',max_prediction_difference=err,monthly_validation_before_decision=True,first_round_M0_predictions_unchanged=bool(np.array_equal(target['pred'][:,0],f['pred'][:,0])))
(TUNED/'information_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
