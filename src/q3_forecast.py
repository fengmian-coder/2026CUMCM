"""Causal Q/A/F forecasts on Q3's shifted 10-minute plan grid."""
from pathlib import Path
from datetime import datetime, date
import csv
import json
import numpy as np
from openpyxl import load_workbook
from q2_data import load_q2_data
from data_loader import read_attachment1

ROOT=Path(__file__).resolve().parents[1]
HOURS=(0,6,12,18)
WEIGHTS=np.arange(101,dtype=float)/100

def attachment3(dates):
    wb=load_workbook(ROOT/'materials/附件3.xlsx',read_only=True,data_only=True)
    rows=list(wb.active.values);wb.close()
    assert len(rows)==1461 and tuple(rows[0][2:])==tuple(f'预报{i}小时' for i in range(1,25))
    result=np.full((365,4,24),np.nan); seen=set(); current=None
    for row in rows[1:]:
        if row[0] not in (None,''):
            v=row[0]
            current=v.date() if isinstance(v,datetime) else v if isinstance(v,date) else datetime.strptime(str(v),'%Y-%m-%d').date()
        d=(current-dates[0]).days
        v=row[1];hour=v.hour if hasattr(v,'hour') else int(str(v).split(':')[0])
        r=HOURS.index(hour);assert (d,r) not in seen
        seen.add((d,r));result[d,r]=row[2:26]
    assert len(seen)==1460 and np.isfinite(result).all() and (result>=0).all()
    return result

def candidate_arrays(data, q, a3):
    # Q is frozen at 00:00. A is direct linear interpolation; F preserves Q shape.
    A=np.zeros((365,4,144));Fbase=np.zeros_like(A);Fslope=np.zeros_like(A)
    cold0=float(read_attachment1().pv_kw[0])
    for d in range(365):
        for ri,h in enumerate(HOURS):
            start=h*6
            obs=float(data.source_pv_kw[d,start-1]) if h else float(data.source_pv_kw[d-1,-1]) if d else cold0
            q0=float(q[d,start-1]) if h else float(q[d-1,-1]) if d else cold0
            nodes=np.arange(h,25,dtype=float)
            qnodes=np.r_[q0,q[d,np.arange((h+1)*6-1,144,6)]]
            anodes=np.r_[obs,a3[d,ri,:24-h]]
            times=np.arange(start+1,145)/6
            interp_a=np.interp(times,nodes,anodes)
            correction0=np.interp(times,nodes,np.r_[obs-q0,np.zeros(24-h)])
            correction1=np.interp(times,nodes,np.r_[0.,anodes[1:]-qnodes[1:]])
            A[d,ri,start:]=interp_a
            Fbase[d,ri,start:]=q[d,start:]+correction0
            Fslope[d,ri,start:]=correction1
    return A,Fbase,Fslope

def build(window=28, data=None, q=None, a3=None):
    data=load_q2_data() if data is None else data
    if q is None:
        with np.load(ROOT/'outputs/q2/rolling_forecasts.npz') as f:
            assert str(f['time_axis'])=='shifted_0010'
            q=f['pv_kw']
    a3=attachment3(data.dates) if a3 is None else a3
    A,fb,fs=candidate_arrays(data,q,a3)
    pred=np.zeros_like(A); kinds=np.zeros((365,4),dtype=int);weight=np.ones((365,4))
    records=[]
    for d in range(365):
        for ri,h in enumerate(HOURS):
            start=h*6;hist=slice(max(0,d-window),d);target=data.source_pv_kw[hist,start:]
            if d==0:
                pred[d,ri,start:]=q[d,start:]
                records.append(dict(date=str(data.dates[d]),hour=h,history_count=0,source='Q',weight=1.,mae_Q=None,mae_A=None,mae_F=None,rmse_Q=None,rmse_A=None,rmse_F=None))
                continue
            fused=np.maximum(fb[hist,ri,start:][None,:,:]+(1-WEIGHTS[:,None,None])*fs[hist,ri,start:][None,:,:],0)
            err=fused-target[None,:,:]; fm=np.mean(np.abs(err),axis=(1,2));fr=np.sqrt(np.mean(err**2,axis=(1,2)))
            best=int(np.lexsort((WEIGHTS,fr,fm))[0]);w=float(WEIGHTS[best])
            qm=float(np.abs(q[hist,start:]-target).mean());qr=float(np.sqrt(np.mean((q[hist,start:]-target)**2)))
            am=float(np.abs(A[hist,ri,start:]-target).mean());ar=float(np.sqrt(np.mean((A[hist,ri,start:]-target)**2)))
            maes=[qm,am,float(fm[best])];rmses=[qr,ar,float(fr[best])]
            low=min(maes);eligible=[i for i in range(3) if maes[i]<=low*1.02+1e-12]
            # MAE within 2%: lower RMSE; exact numerical ties prefer F.
            chosen=min(eligible,key=lambda i:(rmses[i],0 if i==2 else i+1))
            kinds[d,ri]=chosen;weight[d,ri]=w
            pred[d,ri,start:]=q[d,start:] if chosen==0 else A[d,ri,start:] if chosen==1 else np.maximum(fb[d,ri,start:]+(1-w)*fs[d,ri,start:],0)
            records.append(dict(date=str(data.dates[d]),hour=h,history_count=min(d,window),source=('Q','A','F')[chosen],weight=w,
                                mae_Q=maes[0],mae_A=maes[1],mae_F=maes[2],rmse_Q=rmses[0],rmse_A=rmses[1],rmse_F=rmses[2]))
    return dict(pred=pred,kind=kinds,weight=weight,A=A,Fbase=fb,Fslope=fs,Q=q),records

def save(window=28):
    out=ROOT/'outputs/q3';out.mkdir(parents=True,exist_ok=True)
    arrays,records=build(window)
    np.savez_compressed(out/f'forecasts_w{window}.npz',**arrays)
    with (out/f'forecast_selection_w{window}.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    data=load_q2_data();report={}
    for ri,h in enumerate(HOURS):
        start=h*6;t=data.source_pv_kw[31:,start:];selected=arrays['pred'][31:,ri,start:]
        metrics={}
        for name,p in [('Q',arrays['Q'][31:,start:]),('A',arrays['A'][31:,ri,start:]),('selected',selected)]:
            e=p-t;metrics[name]={'mae_kw':float(np.abs(e).mean()),'rmse_kw':float(np.sqrt(np.mean(e**2)))}
        metrics['selection_counts']={name:int((arrays['kind'][31:,ri]==i).sum()) for i,name in enumerate(('Q','A','F'))}
        report[str(h)]=metrics
    (out/f'forecast_metrics_w{window}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Forecasts',window,report,flush=True)
    return arrays

if __name__=='__main__':save()
