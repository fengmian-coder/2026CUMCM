"""Fixed-policy, price ablation, perfect-price and sampling evidence suite."""
import run_q4 as engine
import numpy as np,json
BASE=engine.OUT
if __name__=='__main__':
    data=engine.load_q2_data();z=np.load(BASE/'price_forecasts.npz');price=z['pred'];actual=z['actual']
    q=np.load(engine.ROOT/'outputs/q2/rolling_forecasts.npz');lh=q['load_kw'];ph=q['pv_kw']
    with np.load(BASE/'delayed_pv_forecasts.npz') as f:F={k:f[k] for k in f.files}
    tariff=np.broadcast_to(np.roll(data.price_yuan_per_kwh,-1),(365,144)).copy()
    cases=[('fixed_m0',price,actual,30,20260912,0),
           ('fixed_tariff',np.repeat(tariff[:,None,:],3,axis=1),tariff,30,20260912,0),
           ('perfect_price',np.repeat(actual[:,None,:],3,axis=1),actual,30,20260912,0),
           ('seed_20260913',price,actual,30,20260913,None),
           ('seed_20260914',price,actual,30,20260914,None),
           ('scenarios_50',price,actual,50,20260912,None),
           ('scenarios_100',price,actual,100,20260912,None)]
    reports=[]
    for name,p,a,count,seed,fixed in cases:
        engine.OUT=BASE/'evidence'/name
        for mode in [2,3]:
            saved=engine.OUT/f'q{mode}/summary.json'
            if saved.exists():report=json.loads(saved.read_text(encoding='utf-8'))
            else:report=engine.run(mode,data,F,lh,ph,p,a,count,seed,fixed)
            reports.append(dict(case=name,**report))
            (BASE/'evidence/summary.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Evidence suite complete',flush=True)
