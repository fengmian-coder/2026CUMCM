"""Monthly past-only validation of richer Fourier bases and HGB settings."""
from q4_price import ROOT,OUT,features,load_dates
import json
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
TUNED=OUT/'tuned';TUNED.mkdir(exist_ok=True)

def basis(t,kd,kw):
    return np.column_stack([np.ones(len(t))]+[f(2*np.pi*j*t/per) for per,n in [(144,kd),(1008,kw)] for j in range(1,n+1) for f in [np.sin,np.cos]])

def fit_fourier(a,end,kd,kw):
    X=basis(np.arange(end*144),kd,kw);b=np.linalg.lstsq(X,a[:end].ravel(),rcond=None)[0]
    e=a[:end].ravel()-X@b
    # Conditional least-squares ARIMA(1,0,0), zero intercept; stationarity enforced.
    rho=float(np.clip(e[:-1]@e[1:]/max(e[:-1]@e[:-1],1e-12),-.999,.999))
    return b,rho

def predict_fourier(a,day,kd,kw,b,rho):
    last=a[day-1,-1]-(basis(np.array([day*144-1]),kd,kw)@b).item()
    return np.maximum(basis(np.arange(day*144,(day+1)*144),kd,kw)@b+last*rho**np.arange(1,145),0)

def build(a,original,end_day=365):
    pred=original.copy();records=[]
    tree_grid=[dict(learning_rate=lr,max_iter=n,max_leaf_nodes=leaves,min_samples_leaf=40,l2_regularization=1.,loss='squared_error') for lr,n in [(.03,200),(.07,140),(.07,300),(.1,140)] for leaves in [15,31,63]]
    grid=[(kd,kw) for kd in [3,6,12,24] for kw in [1,3]]
    X=np.concatenate([features(a,d) for d in range(28,end_day)]) if end_day>28 else None
    for d in range(end_day):
        if load_dates[d].day!=1 or d<56:continue
        train_end=d-14;stop=next((j for j in range(d+1,end_day) if load_dates[j].day==1),end_day)
        f_scores=[];tree_scores=[]
        for kd,kw in grid:
            b,rho=fit_fourier(a,train_end,kd,kw)
            v=np.array([predict_fourier(a,j,kd,kw,b,rho) for j in range(train_end,d)])
            error=v-a[train_end:d];f_scores.append(dict(kd=kd,kw=kw,mae=float(abs(error).mean()),rmse=float(np.sqrt((error**2).mean()))))
        best=min(f_scores,key=lambda r:(r['mae'],r['rmse'],r['kd'],r['kw']));kd,kw=best['kd'],best['kw'];b,rho=fit_fourier(a,d,kd,kw)
        for j in range(d,stop):pred[j,1]=predict_fourier(a,j,kd,kw,b,rho)
        for cfg in tree_grid:
            model=HistGradientBoostingRegressor(**cfg,random_state=42,early_stopping=False)
            model.fit(X[:(train_end-28)*144],a[28:train_end].ravel())
            v=model.predict(X[(train_end-28)*144:(d-28)*144]).reshape(14,144);error=v-a[train_end:d]
            tree_scores.append(dict(config=cfg,mae=float(abs(error).mean()),rmse=float(np.sqrt((error**2).mean()))))
        best_tree=min(tree_scores,key=lambda r:(r['mae'],r['rmse']))
        model=HistGradientBoostingRegressor(**best_tree['config'],random_state=42,early_stopping=False)
        model.fit(X[:(d-28)*144],a[28:d].ravel())
        pred[d:stop,2]=np.maximum(model.predict(X[(d-28)*144:(stop-28)*144]).reshape(stop-d,144),0)
        record=dict(date=str(load_dates[d]),train_before=str(load_dates[train_end]),validation_end=str(load_dates[d-1]),fourier=best,ar1=rho,tree=best_tree,fourier_candidates=f_scores,tree_candidates=tree_scores)
        records.append(record);print('TUNED',load_dates[d],best,best_tree,flush=True)
    return pred,records

if __name__=='__main__':
    f=np.load(OUT/'price_forecasts.npz');a=f['actual']
    with threadpool_limits(limits=4):pred,records=build(a,f['pred'])
    np.savez_compressed(TUNED/'price_forecasts.npz',actual=a,pred=pred)
    (TUNED/'parameter_validation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    metrics={f'M{i}':dict(mae=float(abs(pred[31:,i]-a[31:]).mean()),rmse=float(np.sqrt(((pred[31:,i]-a[31:])**2).mean()))) for i in range(3)}
    (TUNED/'price_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8');print(metrics)
