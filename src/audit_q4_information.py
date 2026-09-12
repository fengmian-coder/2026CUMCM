"""Future-data perturbation audit, including a date where all three models run."""
from q4_price import build,OUT,ROOT
import numpy as np,json
from q3_forecast import build as pvbuild,attachment3
from q2_data import load_q2_data
from copy import deepcopy
f=np.load(OUT/'price_forecasts.npz');changed=f['actual'].copy();changed[61:]*=1.7
forecast,_=build(changed,end_day=62)
price_error=float(abs(forecast[:62]-f['pred'][:62]).max());assert price_error<1e-10
data=load_q2_data();mutated=deepcopy(data);mutated.source_pv_kw[61:]*=1.7
q=np.load(ROOT/'outputs/q2/rolling_forecasts.npz')['pv_kw'];a3=attachment3(data.dates)
orig=np.load(OUT/'delayed_pv_forecasts.npz')
new,_=pvbuild(data=mutated,q=q,a3=a3,delayed_observations=True)
pv_error=float(abs(new['pred'][:62]-orig['pred'][:62]).max());assert pv_error<1e-10
report=dict(price_prediction_error_before_and_on_perturbed_day=price_error,pv_prediction_error_before_and_on_perturbed_day=pv_error,cutoff='2025-03-03',method='Multiply all actual values from cutoff onward by 1.7; forecasts on or before cutoff must not change.')
(OUT/'information_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)
