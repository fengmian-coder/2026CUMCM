"""Canonical Q2 dispatch: plans start 00:10; reporting uses natural days."""
import csv
import json
from dataclasses import asdict
from pathlib import Path
import numpy as np
from q2_data import load_q2_data, natural_interval_labels
from q2_forecast import save_forecasts

ROOT = Path(__file__).resolve().parents[1]
MODE = 'shifted_0010'

def natural(values, start=31, end=365):
    """Execution-date view; first slot was locked by yesterday's decision."""
    return np.concatenate((values[start-1:end-1,-1,None], values[start:end,:143]),axis=1)

def natural_energy(values, start=31, end=365):
    return np.concatenate((values[start-1:end-1,143,None],values[start:end,:144]),axis=1)

def totals(g,b,p):
    return dict(plan_cost_yuan=float(np.sum(g*p)),emergency_cost_yuan=float(np.sum(b*5*p)),
                total_cost_yuan=float(np.sum((g+5*b)*p)),plan_purchase_kwh=float(g.sum()),
                emergency_purchase_kwh=float(b.sum()))

def run(cfg, start_day=31, end_day=365, output_dir=ROOT/'outputs/q2', save_detail=True):
    from q2_optimize import solve_day, scenarios_for_day
    if start_day < 1:
        raise ValueError('Natural reporting requires a preceding plan; use start_day >= 1 (formal:31)')
    data=load_q2_data(); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    canonical=ROOT/'outputs/q2'; ff=canonical/'rolling_forecasts.npz'
    if not ff.exists(): save_forecasts(canonical)
    with np.load(ff) as f:
        if 'time_axis' not in f or str(f['time_axis']) != MODE:
            raise ValueError('Run q2_forecast.py to refresh forecasts to shifted_0010')
        lh,ph=f['load_kw'],f['pv_kw']
    price=np.roll(data.price_yuan_per_kwh,-1)
    e0=6000.; solutions=[]
    for d in range(end_day):
        sl,sp=scenarios_for_day(d,data.dates,data.source_load_kw,data.source_pv_kw,lh,ph,cfg)
        s=solve_day(price,e0,sl,sp,cfg)
        short=data.source_load_kw[d]/6+s['charge']-s['purchase']-data.source_pv_kw[d]/6-s['discharge']
        s['emergency']=np.maximum(short,0);s['surplus']=np.maximum(-short,0)
        solutions.append(s);e0=float(s['energy'][-1])
    a={k:np.asarray([s[k] for s in solutions]) for k in ('purchase','charge','discharge','energy','emergency','surplus')}
    n={k:natural(v,start_day,end_day) for k,v in a.items() if k!='energy'}
    ne=natural_energy(a['energy'],start_day,end_day)
    state=a['energy'][:,1:]-a['energy'][:,:-1]-.9*a['charge']+a['discharge']/.9
    balance=a['purchase']+data.source_pv_kw[:end_day]/6+a['discharge']+a['emergency']-data.source_load_kw[:end_day]/6-a['charge']-a['surplus']
    summary={**totals(n['purchase'],n['emergency'],data.price_yuan_per_kwh),
             'time_axis':MODE,'config':asdict(cfg),'output_period':[str(data.dates[start_day]),str(data.dates[end_day-1])],
             'reporting_window':'natural 00:00-24:00','days':end_day-start_day,
             'plan_window_totals':totals(a['purchase'][start_day:],a['emergency'][start_day:],price),
             'emergency_days':int((n['emergency'].sum(axis=1)>1e-7).sum()),
             'surplus_kwh':float(n['surplus'].sum()),'charge_kwh':float(n['charge'].sum()),'discharge_kwh':float(n['discharge'].sum()),
             'max_balance_error':float(np.abs(balance).max()),'max_state_error':float(np.abs(state).max()),
             'simultaneous_slots':int(((a['charge']>1e-7)&(a['discharge']>1e-7)).sum()),
             'energy_min_kwh':float(a['energy'].min()),'energy_max_kwh':float(a['energy'].max()),
             'initial_energy_kwh':6000.,'final_energy_kwh':float(ne[-1,-1]),'final_plan_energy_0010_kwh':float(a['energy'][-1,-1])}
    assert summary['max_balance_error']<1e-7 and summary['max_state_error']<1e-7
    assert summary['simultaneous_slots']==0
    (out/'q2_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if save_detail:
        np.savez_compressed(out/'q2_schedules.npz',**a,time_axis=MODE)
        np.savez_compressed(out/'natural_reporting.npz',**n,energy=ne)
        daily=[];labels=natural_interval_labels()
        nl,npv=natural(lh,start_day,end_day),natural(ph,start_day,end_day)
        with (out/'q2_schedule.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(['日期','时段序号','自然日时段','电价(元/kWh)','预测负载功率(kW)','预测光伏功率(kW)','实际负载功率(kW)','实际光伏功率(kW)','计划购电量(kWh)','计划充电量(kWh)','计划放电量(kWh)','紧急购电量(kWh)','剩余电量(kWh)','期初储电量(kWh)','期末储电量(kWh)'])
            for i,d in enumerate(range(start_day,end_day)):
                row={'date':str(data.dates[d]),**totals(n['purchase'][i],n['emergency'][i],data.price_yuan_per_kwh),
                     'initial_energy_kwh':float(ne[i,0]),'final_energy_kwh':float(ne[i,-1]),
                     'optimization_initial_energy_0010_kwh':float(a['energy'][d,0]),
                     'charge_kwh':float(n['charge'][i].sum()),'discharge_kwh':float(n['discharge'][i].sum()),
                     'surplus_kwh':float(n['surplus'][i].sum())}
                daily.append(row)
                for t in range(144):
                    w.writerow([str(data.dates[d]),t+1,labels[t],data.price_yuan_per_kwh[t],nl[i,t],npv[i,t],data.load_kw[d,t],data.pv_kw[d,t],*[n[k][i,t] for k in ('purchase','charge','discharge','emergency','surplus')],ne[i,t],ne[i,t+1]])
        (out/'q2_daily_summary.json').write_text(json.dumps(daily,ensure_ascii=False,indent=2),encoding='utf-8')
        # Direct plan rows: never join tomorrow's new decision.
        (out/'result2_plan_rows.json').write_text(json.dumps({'time_axis':MODE,'dates':[str(v) for v in data.dates[start_day:end_day]],
             'purchase':a['purchase'][start_day:].tolist(),'prices':price.tolist()},ensure_ascii=False),encoding='utf-8')
    return summary
