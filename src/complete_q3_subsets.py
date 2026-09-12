"""Complete original Q3's eight forecast-time subsets; preserve formal workbook."""
from q3_run import run,Config,ROOT
import json
import numpy as np
O=ROOT/'outputs/q3'
cases=[('only_0',()),('updates_06',(6,)),('updates_12',(12,)),('updates_18',(18,)),
       ('updates_0612',(6,12)),('updates_0618',(6,18)),('updates_1218',(12,18)),('updates_061218',(6,12,18))]
if __name__=='__main__':
    rows=[]
    for name,hours in cases:
        f=O/name/'summary.json'
        s=json.loads(f.read_text(encoding='utf-8')) if f.exists() else run(Config(hours=hours),name)
        assert tuple(s['config']['hours'])==hours and s['config']['window']==28 and s['config']['threshold']==.001 and s['config']['scenarios']==30 and s['config']['refund']
        with np.load(O/name/'natural.npz') as z:
            costs=(z['grid_fee']+z['emergency_fee']).sum(axis=1)
            monthly=[]
            from datetime import date,timedelta
            dates=[date(2025,2,1)+timedelta(days=i) for i in range(len(costs))]
            for m in range(2,13):monthly.append(float(costs[[dt.month==m for dt in dates]].sum()))
        rows.append(dict(hours=[0,*hours],**s,monthly_costs=monthly))
        (O/'all_subsets.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('All eight subsets complete',flush=True)
