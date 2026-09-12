"""Limited evening-policy experiment; keep official main outputs untouched."""
from q3_run import Config,run,ROOT
import numpy as np
import json

if __name__=='__main__':
    cases=[('opt_evening_01',Config(hours=(6,12,18),evening_threshold=.01)),
           ('opt_evening_05',Config(hours=(6,12,18),evening_threshold=.05)),
           ('opt_evening_cash',Config(hours=(6,12,18),evening_cash_gate=True))]
    for name,cfg in cases:run(cfg,name)
    rows=[]
    for name in ['updates_061218']+[n for n,c in cases]:
        with np.load(ROOT/'outputs/q3'/name/'natural.npz') as a:
            # February through June: 150 days. July through December: 184 days.
            cost=(a['grid_fee']+a['emergency_fee']).sum(axis=1)
            rows.append(dict(case=name,selection_cost=float(cost[:150].sum()),
                validation_cost=float(cost[150:].sum()),total_cost=float(cost.sum()),
                validation_emergency_kwh=float(a['emergency'][150:].sum()),
                split_energy=float(a['energy'][150,0]),final_energy=float(a['energy'][-1,-1])))
    selected=min(rows,key=lambda r:r['selection_cost'])['case']
    report=dict(selection_period='2025-02-01 through 2025-06-30',
        validation_period='2025-07-01 through 2025-12-31',selected_on_first_period=selected,rows=rows,
        limitation='Retrospective temporal split, not an untouched test: aggregate full-year baseline was already inspected. Each policy has its own continuous SOC history.')
    (ROOT/'outputs/q3/optimization_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
