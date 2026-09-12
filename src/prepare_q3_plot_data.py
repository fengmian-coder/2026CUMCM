"""Derive plotting data from saved simulations without changing model outputs."""
from pathlib import Path
import json
import numpy as np
from datetime import date, timedelta
R=Path(__file__).resolve().parents[1]
O=R/'outputs/q3'
a=np.load(O/'main/natural.npz'); b=np.load(O/'updates_061218/natural.npz')
dates=[str(date(2025,2,1)+timedelta(days=i)) for i in range(len(a['purchase']))]
cost=lambda x:(x['grid_fee']+x['emergency_fee']).sum(axis=1)
delta=cost(b)-cost(a)
adjust=np.abs(a['purchase']-a['baseline']).sum(axis=1)
order=np.argsort(adjust,kind='stable'); typical=int(order[len(order)//2])
data=dict(dates=dates, soc=(a['energy'][:,:-1]/12000*100).tolist(),emergency=a['emergency'].tolist(),
          adjustment=(a['purchase']-a['baseline']).tolist(),daily_difference=delta.tolist(),
          cumulative_difference=np.cumsum(delta).tolist(),typical_index=typical,
          typical={k:a[k][typical].tolist() for k in ['baseline','purchase','charge','discharge','energy']},
          monthly=[])
for m in range(2,13):
    mask=np.array([int(d[5:7])==m for d in dates])
    data['monthly'].append(dict(month=m,grid_difference=float((b['grid_fee'][mask]-a['grid_fee'][mask]).sum()),
        emergency_difference=float((b['emergency_fee'][mask]-a['emergency_fee'][mask]).sum())))
summ=lambda name:json.loads((O/name/'summary.json').read_text(encoding='utf-8'))['natural_totals']['total_cost_yuan']
assert abs(sum(delta)-(summ('updates_061218')-summ('main')))<1e-6
(O/'plot_data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
print('Representative day:',dates[typical],'; daily adjustment magnitude median rank; data checked')
