"""Q4 formal policy: fixed yearly M0 and correlated source/load/price scenarios."""
from pathlib import Path
import sys,json,csv
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/q4_deps'))
import numpy as np
from q2_data import load_q2_data,natural_interval_labels
from q2_dispatch import natural,natural_energy
from q3_forecast import build,HOURS
from q4_solver import solve,evaluate,VALUE
OUT=ROOT/'outputs/q4';OUT.mkdir(parents=True,exist_ok=True)

def simulate_day(d,m,e0,mode,data,F,lh,ph,price,actual,events,scenario_count=30,random_seed=20260912,update_hours=(6,12)):
    def scenarios(ri):
        start=HOURS[ri]*6
        if d==0:sample=np.array([0])
        else:
            pool=np.arange(max(0,d-60),d);w=.5**((d-pool)/30)
            w*=np.array([3 if data.dates[j].weekday()==data.dates[d].weekday() else 1 for j in pool]);w/=w.sum()
            sample=np.random.default_rng(random_seed+d+ri*10000).choice(pool,scenario_count,p=w)
        pred=ph[d,start:] if mode==2 else F['pred'][d,ri,start:]
        if d==0:return lh[d:d+1,start:]/6,pred[None]/6,price[d,m,start:][None]
        if mode==2:past=ph[sample,start:]
        else:
            kind=F['kind'][d,ri];weight=F['weight'][d,ri]
            past=F['Q'][sample,start:] if kind==0 else F['A'][sample,ri,start:] if kind==1 else np.maximum(F['Fbase'][sample,ri,start:]+(1-weight)*F['Fslope'][sample,ri,start:],0)
        L=np.maximum(lh[d,start:]+data.source_load_kw[sample,start:]-lh[sample,start:],0)/6
        P=np.maximum(pred+data.source_pv_kw[sample,start:]-past,0)/6
        ps=np.maximum(price[d,m,start:]+actual[sample,start:]-price[sample,m,start:],0)
        return L,P,ps
    L,P,ps=scenarios(0);cur=solve(ps,e0,L,P);base=cur['purchase'].copy();used=int(cur['used_milp'])
    for ri,h in enumerate(HOURS[1:],1):
        if mode==2:break
        if h not in update_hours:continue
        start=h*6;L,P,ps=scenarios(ri)
        before={k:cur[k][start:].copy() for k in ['purchase','charge','discharge','energy']}
        keep=evaluate(before,ps,L,P,base[start:]);new=solve(ps,cur['energy'][start],L,P,base[start:]);used+=int(new['used_milp'])
        after=evaluate(new,ps,L,P,base[start:]);gain=keep['objective']-after['objective'];assert gain>=-1e-5
        accepted=gain>max(.001*max(keep['cash'],1),1e-7)
        if accepted:
            for k in ['purchase','charge','discharge','energy']:cur[k][start:]=new[k]
        events.append(dict(date=str(data.dates[d]),model=int(m),hour=h,accepted=bool(accepted),expected_gain=float(gain),expected_cash_gain=float(keep['cash']-after['cash'])))
    short=data.source_load_kw[d]/6+cur['charge']-cur['purchase']-data.source_pv_kw[d]/6-cur['discharge']
    cur['emergency']=np.maximum(short,0);cur['surplus']=np.maximum(-short,0);cur['baseline']=base
    cur['base_fee']=actual[d]*base
    cur['grid_fee']=actual[d]*(cur['purchase']+(.5*np.abs(cur['purchase']-base) if mode==3 else 0))
    cur['emergency_fee']=5*actual[d]*cur['emergency'];cur['milp_count']=used
    return cur

def run(mode,data,F,lh,ph,price,actual,scenario_count=30,random_seed=20260912,fixed_model=0,update_hours=(6,12)):
    target=OUT/f'q{mode}';target.mkdir(parents=True,exist_ok=True);days=[];paired=[];records=[];events=[];e0=6000.;chosen=0
    for d in range(365):
        if fixed_model is not None:
            chosen=fixed_model
            if d==0:records.append(dict(date=str(data.dates[d]),selected=chosen,selection_policy='fixed_year',history_count=0,paired_mean_score=None))
            if data.dates[d].day==1:print('Q4',mode,data.dates[d],'fixed model',chosen,flush=True)
        elif data.dates[d].day==1:
            # Exclude yesterday's plan: its last interval ends today at 00:10.
            history=paired[max(0,d-29):max(0,d-1)]
            means=np.mean(history,axis=0) if len(history)>=28 else None
            best=int(np.argmin(means)) if means is not None else 0
            chosen=best if means is not None and means[0]-means[best]>=.005*max(abs(means[0]),1) else 0
            if fixed_model is not None:chosen=fixed_model
            records.append(dict(date=str(data.dates[d]),selected=chosen,history_count=len(history),paired_mean_score=means.tolist() if means is not None else None))
            print('Q4',mode,data.dates[d],'model',chosen,flush=True)
        candidates=[];trial_events=[]
        for m in (range(3) if fixed_model is None else [fixed_model]):
            ev=[];s=simulate_day(d,m,e0,mode,data,F,lh,ph,price,actual,ev,scenario_count,random_seed,update_hours);candidates.append(s);trial_events.append(ev)
        # Common current SOC; subtract final value to avoid rewarding battery depletion.
        paired.append([float((s['grid_fee']+s['emergency_fee']).sum()-VALUE*s['energy'][-1]) for s in candidates])
        selected_index=chosen if fixed_model is None else 0
        s=candidates[selected_index];days.append(s);events.extend(trial_events[selected_index]);e0=float(s['energy'][-1])
    keys=['purchase','charge','discharge','energy','emergency','surplus','baseline','base_fee','grid_fee','emergency_fee']
    a={k:np.array([s[k] for s in days]) for k in keys};n={k:natural(v) for k,v in a.items() if k!='energy'};n['energy']=natural_energy(a['energy'])
    balance=a['purchase']+data.source_pv_kw/6+a['discharge']+a['emergency']-data.source_load_kw/6-a['charge']-a['surplus']
    state=a['energy'][:,1:]-a['energy'][:,:-1]-.9*a['charge']+a['discharge']/.9
    audit=dict(balance=float(abs(balance).max()),state=float(abs(state).max()),continuity=float(abs(a['energy'][:-1,-1]-a['energy'][1:,0]).max()),simultaneous=int(((a['charge']>1e-7)&(a['discharge']>1e-7)).sum()),energy_min=float(a['energy'].min()),energy_max=float(a['energy'].max()),max_charge=float(a['charge'].max()),max_discharge=float(a['discharge'].max()))
    assert max(audit[k] for k in ['balance','state','continuity'])<1e-7 and audit['simultaneous']==0
    assert audit['energy_min']>=1200-1e-7 and audit['energy_max']<=10800+1e-7
    assert max(audit['max_charge'],audit['max_discharge'])<=5000/6+1e-7
    def totals(v):return dict(grid_fee=float(v['grid_fee'].sum()),emergency_fee=float(v['emergency_fee'].sum()),total_cost=float((v['grid_fee']+v['emergency_fee']).sum()),emergency_kwh=float(v['emergency'].sum()),purchase_kwh=float(v['purchase'].sum()))
    summary=dict(mode=mode,scenario_count=scenario_count,random_seed=random_seed,fixed_model=fixed_model,natural_period=['2025-02-01 00:00','2026-01-01 00:00'],natural=totals(n),plan=totals({k:v[31:] for k,v in a.items()}),audit=audit,final_midnight_energy=float(n['energy'][-1,-1]),final_0010_energy=float(a['energy'][-1,-1]),milp_count=sum(s['milp_count'] for s in days))
    summary.update(selection_policy='fixed_year' if fixed_model is not None else 'monthly_legacy',update_hours=list(update_hours) if mode==3 else [])
    np.savez_compressed(target/'schedules.npz',**a);np.savez_compressed(target/'natural.npz',**n)
    for file,obj in [('summary.json',summary),('model_selection.json',records),('adjustment_events.json',events),('paired_scores.json',paired)]:
        (target/file).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    book=dict(dates=[str(dt) for dt in data.dates[31:]],baseline=a['baseline'][31:].tolist(),final=a['purchase'][31:].tolist(),prices=actual[31:].tolist(),grid_fee=a['grid_fee'][31:].tolist(),charge=n['charge'].tolist(),discharge=n['discharge'].tolist(),energy=n['energy'].tolist(),emergency=n['emergency'].tolist())
    (target/'workbook_data.json').write_text(json.dumps(book,ensure_ascii=False),encoding='utf-8')
    print('DONE',summary,flush=True)
    return summary

if __name__=='__main__':
    data=load_q2_data(); f=np.load(OUT/'price_forecasts.npz');price=f['pred'];actual=f['actual']
    q=np.load(ROOT/'outputs/q2/rolling_forecasts.npz');lh=q['load_kw'];ph=q['pv_kw']
    F,rec=build(delayed_observations=True);np.savez_compressed(OUT/'delayed_pv_forecasts.npz',**F)
    (OUT/'delayed_pv_selection.json').write_text(json.dumps(rec,ensure_ascii=False),encoding='utf-8')
    reports=[run(m,data,F,lh,ph,price,actual) for m in [2,3]]
    (OUT/'summary.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
