"""First-run causal M0/M1/M2 price forecasts. Fixed M1/M2 settings, no tuning claim."""
from pathlib import Path
import sys,os,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/q4_deps'))
os.environ['OMP_NUM_THREADS']='4'
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye,hstack,vstack,csr_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.tsa.arima.model import ARIMA
from openpyxl import load_workbook
from q2_data import load_q2_data
OUT=ROOT/'outputs/q4';OUT.mkdir(parents=True,exist_ok=True)

def prices():
    w=load_workbook(ROOT/'materials/附件4.xlsx',read_only=True,data_only=True)
    rows=list(w.active.values);w.close();data=load_q2_data()
    assert len(rows)==366 and len(rows[0])==145
    assert all(r[0].date()==data.dates[i] for i,r in enumerate(rows[1:]))
    assert all(rows[0][j+1].hour*60+rows[0][j+1].minute==(j+1)*10 for j in range(143))
    assert rows[0][-1]=='0:00+1'
    a=np.array([r[1:] for r in rows[1:]],float)
    assert np.isfinite(a).all() and a.min()>0
    return a

def fourier(t):
    # Avoid redundant weekend + weekday dummy variables and unseen month coefficients.
    return np.column_stack([np.ones(len(t))]+[f(2*np.pi*j*t/per) for per,n in [(144,6),(1008,3)] for j in range(1,n+1) for f in [np.sin,np.cos]])

def features(a,d):
    k=np.arange(144);dt=load_dates[d]
    return np.column_stack([k,np.sin(2*np.pi*k/144),np.cos(2*np.pi*k/144),
        np.full(144,dt.weekday()),np.full(144,dt.month),np.full(144,np.sin(2*np.pi*dt.timetuple().tm_yday/365)),
        np.full(144,np.cos(2*np.pi*dt.timetuple().tm_yday/365))]+[a[d-lag] for lag in [1,2,7,14,28]])

load_dates=load_q2_data().dates
def build(a=None,end_day=365):
    a=prices() if a is None else a; pred=np.zeros((365,3,144));logs=[]
    cold=np.roll(load_q2_data().price_yuan_per_kwh,-1)
    weights=np.array([.4,.3,.2,.1]); beta=None;rho=0.;tree=None
    for d in range(end_day):
        if load_dates[d].day==1:
            hist=np.arange(28,d)
            if len(hist)>=14:
                X=np.stack([a[hist-l] for l in [7,14,21,28]],axis=-1).reshape(-1,4);y=a[hist].ravel();n=len(y)
                fit=linprog(np.r_[np.zeros(4),np.ones(n)/n],A_ub=vstack([hstack([csr_matrix(X),-eye(n)]),hstack([-csr_matrix(X),-eye(n)])]),b_ub=np.r_[y,-y],A_eq=csr_matrix(np.r_[np.ones(4),np.zeros(n)][None]),b_eq=[1.],bounds=(0,None),method='highs')
                assert fit.success;weights=fit.x[:4]
            if d>=28:
                t=np.arange(d*144);X=fourier(t);beta=np.linalg.lstsq(X,a[:d].ravel(),rcond=None)[0]
                resid=a[:d].ravel()-X@beta
                ar=ARIMA(resid,order=(1,0,0),trend='n').fit()
                rho=float(ar.arparams[0])
            if d>=42:
                tree=HistGradientBoostingRegressor(learning_rate=.07,max_iter=140,max_leaf_nodes=31,min_samples_leaf=40,l2_regularization=1.,random_state=42,early_stopping=False)
                tree.fit(np.concatenate([features(a,j) for j in range(28,d)]),a[28:d].ravel())
            logs.append(dict(date=str(load_dates[d]),weights=weights.tolist(),ar1=rho,m1_ready=beta is not None,m2_ready=tree is not None,training_end=str(load_dates[d-1]) if d else None))
            print('price month',load_dates[d],flush=True)
        ix=[j for j in range(4) if d-7*(j+1)>=0]
        m0=sum(weights[j]*a[d-7*(j+1)] for j in ix)/sum(weights[j] for j in ix) if ix else cold.copy()
        pred[d,0]=m0
        t=np.arange(d*144,(d+1)*144)
        pred[d,1]=np.maximum(fourier(t)@beta+(a[d-1,-1]-(fourier(np.array([d*144-1]))@beta).item())*rho**np.arange(1,145),0) if beta is not None else m0
        pred[d,2]=np.maximum(tree.predict(features(a,d)),0) if tree is not None else m0
    return pred,logs

if __name__=='__main__':
    a=prices();pred,logs=build(a)
    np.savez_compressed(OUT/'price_forecasts.npz',actual=a,pred=pred)
    (OUT/'price_training.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Price forecasts saved',flush=True)
