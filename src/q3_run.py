"""Continuous Q3 rolling backtest with locked first interval at every update."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/q2_trial_deps'))
import json
import csv
from dataclasses import dataclass,asdict
import numpy as np
from q2_data import load_q2_data,natural_interval_labels
from q2_dispatch import natural,natural_energy
from q3_forecast import HOURS,save
from q3_solver import solve,evaluate,grid_cost

@dataclass(frozen=True)
class Config:
    hours:tuple=(6,12,18)
    window:int=28
    threshold:float=.001
    refund:bool=True
    scenarios:int=30
    evening_threshold:float|None=None
    evening_cash_gate:bool=False

def scenarios(d,ri,data,lh,F,cfg):
    start=HOURS[ri]*6
    if d==0:return lh[d:d+1,start:]/6,F['pred'][d:d+1,ri,start:]/6
    pool=np.arange(max(0,d-60),d)
    weights=.5**((d-pool)/30.)
    weights*=np.where([data.dates[j].weekday()==data.dates[d].weekday() for j in pool],3.,1.)
    weights/=weights.sum()
    sample=np.random.default_rng(20260912+d+ri*10000).choice(pool,cfg.scenarios,p=weights,replace=True)
    kind=int(F['kind'][d,ri]);w=F['weight'][d,ri]
    past=F['Q'][sample,start:] if kind==0 else F['A'][sample,ri,start:] if kind==1 else np.maximum(F['Fbase'][sample,ri,start:]+(1-w)*F['Fslope'][sample,ri,start:],0)
    L=np.maximum(lh[d,start:]+data.source_load_kw[sample,start:]-lh[sample,start:],0)
    P=np.maximum(F['pred'][d,ri,start:]+data.source_pv_kw[sample,start:]-past,0)
    return L/6,P/6

def run(cfg=Config(),name='main',save_detail=True):
    data=load_q2_data();out=ROOT/'outputs/q3'/name;out.mkdir(parents=True,exist_ok=True)
    file=ROOT/'outputs/q3'/f'forecasts_w{cfg.window}.npz'
    if not file.exists():save(cfg.window)
    with np.load(file) as f:F={k:f[k] for k in f.files}
    with np.load(ROOT/'outputs/q2/rolling_forecasts.npz') as f:lh=f['load_kw']
    p=np.roll(data.price_yuan_per_kwh,-1);e0=6000.;days=[];events=[];milp_count=0
    for d in range(365):
        L,P=scenarios(d,0,data,lh,F,cfg)
        current=solve(p,e0,L,P)
        milp_count+=current['used_milp'];base=current['purchase'].copy()
        baseline_c=current['charge'].copy();baseline_d=current['discharge'].copy()
        for ri,h in enumerate(HOURS[1:],1):
            if h not in cfg.hours:continue
            start=h*6
            before={k:current[k][start:].copy() for k in ('purchase','charge','discharge','energy')}
            L,P=scenarios(d,ri,data,lh,F,cfg)
            keep=evaluate(before,p[start:],L,P,base[start:],cfg.refund)
            adjustment=solve(p[start:],float(current['energy'][start]),L,P,base[start:],cfg.refund)
            milp_count+=adjustment['used_milp']
            after=evaluate(adjustment,p[start:],L,P,base[start:],cfg.refund)
            gain=keep['objective']-after['objective'];denom=max(keep['cash'],1.)
            assert gain>=-1e-5
            threshold=cfg.evening_threshold if h==18 and cfg.evening_threshold is not None else cfg.threshold
            accept=gain>max(threshold*denom,1e-7)
            if h==18 and cfg.evening_cash_gate:
                accept=accept and keep['cash']-after['cash']>1e-7
            if accept:
                for k in ('purchase','charge','discharge','energy'):current[k][start:]=adjustment[k]
            events.append(dict(date=str(data.dates[d]),hour=h,source=('Q','A','F')[int(F['kind'][d,ri])],
                               weight=float(F['weight'][d,ri]),accepted=bool(accept),keep_objective=keep['objective'],
                               adjust_objective=after['objective'],keep_cash=keep['cash'],expected_gain=gain,
                               relative_gain=gain/denom,initial_energy_kwh=float(before['energy'][0]),
                               expected_cash_gain=keep['cash']-after['cash'],
                               expected_cvar_gain=keep['cvar']-after['cvar'],
                               terminal_energy_change=float(adjustment['energy'][-1]-before['energy'][-1])))
        short=data.source_load_kw[d]/6+current['charge']-current['purchase']-data.source_pv_kw[d]/6-current['discharge']
        current['emergency']=np.maximum(short,0);current['surplus']=np.maximum(-short,0)
        current['baseline']=base;current['baseline_charge']=baseline_c;current['baseline_discharge']=baseline_d
        current['base_fee']=p*base
        current['grid_fee']=p*(current['purchase']+.5*np.abs(current['purchase']-base)) if cfg.refund else p*(base+.5*np.maximum(base-current['purchase'],0)+1.5*np.maximum(current['purchase']-base,0))
        current['adjustment_fee']=current['grid_fee']-current['base_fee']
        current['emergency_fee']=5*p*current['emergency'];days.append(current);e0=float(current['energy'][-1])
        if d%90==0:print(name,str(data.dates[d]),flush=True)
    keys=('baseline','purchase','charge','discharge','energy','emergency','surplus','base_fee','grid_fee','adjustment_fee','emergency_fee','baseline_charge','baseline_discharge')
    a={k:np.asarray([s[k] for s in days]) for k in keys}
    n={k:natural(v) for k,v in a.items() if k!='energy'};n['energy']=natural_energy(a['energy'])
    balance=a['purchase']+data.source_pv_kw/6+a['discharge']+a['emergency']-data.source_load_kw/6-a['charge']-a['surplus']
    state=a['energy'][:,1:]-a['energy'][:,:-1]-.9*a['charge']+a['discharge']/.9
    audit=dict(balance_residual_kwh=float(np.abs(balance).max()),state_residual_kwh=float(np.abs(state).max()),
               continuity_residual_kwh=float(np.abs(a['energy'][:-1,-1]-a['energy'][1:,0]).max()),
               min_energy=float(a['energy'].min()),max_energy=float(a['energy'].max()),max_charge=float(a['charge'].max()),max_discharge=float(a['discharge'].max()),
               simultaneous_slots=int(((a['charge']>1e-7)&(a['discharge']>1e-7)).sum()),milp_fallback_count=milp_count)
    assert audit['balance_residual_kwh']<1e-7 and audit['state_residual_kwh']<1e-7 and audit['continuity_residual_kwh']<1e-7
    assert audit['min_energy']>=1200-1e-7 and audit['max_energy']<=10800+1e-7 and audit['simultaneous_slots']==0
    assert audit['max_charge']<=5000/6+1e-7 and audit['max_discharge']<=5000/6+1e-7
    def summary_of(v):
        return dict(base_plan_fee_yuan=float(v['base_fee'].sum()),adjustment_fee_yuan=float(v['adjustment_fee'].sum()),
                    settled_grid_fee_yuan=float(v['grid_fee'].sum()),emergency_fee_yuan=float(v['emergency_fee'].sum()),
                    total_cost_yuan=float((v['grid_fee']+v['emergency_fee']).sum()),
                    emergency_kwh=float(v['emergency'].sum()),purchase_kwh=float(v['purchase'].sum()),charge_kwh=float(v['charge'].sum()),discharge_kwh=float(v['discharge'].sum()),surplus_kwh=float(v['surplus'].sum()))
    summary=dict(case=name,config=asdict(cfg),natural_period=['2025-02-01 00:00','2026-01-01 00:00'],
                 plan_period=['2025-02-01 00:10','2026-01-01 00:10'],natural_totals=summary_of(n),
                 plan_totals=summary_of({k:v[31:] for k,v in a.items()}),audit=audit,
                 final_midnight_energy=float(n['energy'][-1,-1]),final_0010_energy=float(a['energy'][-1,-1]),
                 adjustment_counts={str(h):sum(e['accepted'] for e in events if e['hour']==h and e['date']>='2025-02-01') for h in cfg.hours})
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if save_detail:
        np.savez_compressed(out/'schedules.npz',**a);np.savez_compressed(out/'natural.npz',**n)
        if events:
            with (out/'adjustment_events.csv').open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=list(events[0]));w.writeheader();w.writerows(events)
        with (out/'execution.csv').open('w',newline='',encoding='utf-8-sig') as f:
            cols=['date','interval','actual_load_kw','actual_pv_kw',*list(n.keys()-{'energy'}),'initial_energy','final_energy']
            # Stable ordering independent of Python hash seed.
            cols=['date','interval','actual_load_kw','actual_pv_kw']+[k for k in keys if k!='energy']+['initial_energy','final_energy']
            w=csv.writer(f);w.writerow(cols)
            for i,d in enumerate(range(31,365)):
                for t,label in enumerate(natural_interval_labels()):
                    w.writerow([str(data.dates[d]),label,data.load_kw[d,t],data.pv_kw[d,t],*[n[k][i,t] for k in keys if k!='energy'],n['energy'][i,t],n['energy'][i,t+1]])
        (out/'workbook_data.json').write_text(json.dumps(dict(dates=[str(d) for d in data.dates[31:]],prices=p.tolist(),
             baseline=a['baseline'][31:].tolist(),final=a['purchase'][31:].tolist(),grid_fee=a['grid_fee'][31:].tolist(),
             charge=n['charge'].tolist(),discharge=n['discharge'].tolist(),energy=n['energy'].tolist(),emergency=n['emergency'].tolist()),ensure_ascii=False),encoding='utf-8')
    print('DONE',name,summary['natural_totals'],summary['adjustment_counts'],flush=True)
    return summary

if __name__=='__main__':run()
