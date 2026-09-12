"""LP with MILP fallback, explicit settlement, and emergency-cost CVaR."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tmp/q2_trial_deps'))
import numpy as np
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, vstack, hstack, csr_matrix

ETA=.9; QMAX=5000/6; VALUE=.6895775; ALPHA=.9; LAMBDA=.05

def grid_cost(g,p,base=None,refund=True):
    if base is None:return float(p@g)
    if refund:return float(p@(g+.5*np.abs(g-base)))
    return float(p@(base+.5*np.maximum(base-g,0)+1.5*np.maximum(g-base,0)))

def evaluate(solution,p,load,pv,base=None,refund=True):
    b=np.maximum(load+solution['charge']-pv-solution['purchase']-solution['discharge'],0)
    ps=np.broadcast_to(p,load.shape)
    losses=(b*5*ps).sum(axis=1)
    z=float(np.quantile(losses,ALPHA,method='higher'))
    # Minimize empirical CVaR over loss breakpoints to avoid quantile convention issues.
    cvar=min(float(v+np.maximum(losses-v,0).mean()/(1-ALPHA)) for v in np.unique(losses))
    cash=grid_cost(solution['purchase'],ps.mean(axis=0),base,refund)+float(losses.mean())
    return dict(objective=cash+LAMBDA*cvar-VALUE*float(solution['energy'][-1]),cash=cash,cvar=cvar)

def solve(p,e0,load,pv,base=None,refund=True):
    S,T=load.shape
    ps=np.broadcast_to(p,load.shape).copy();p=ps.mean(axis=0)
    assert np.all(ps>=0)
    g=np.arange(T);c=g+T;d=g+2*T;e=np.arange(3*T,4*T+1)
    b=np.arange(4*T+1,4*T+1+S*T).reshape(S,T);z=int(b[-1,-1]+1);v=np.arange(z+1,z+1+S)
    n=int(v[-1]+1);up=down=None
    if base is not None:up=np.arange(n,n+T);down=np.arange(n+T,n+2*T);n+=2*T
    obj=np.zeros(n);obj[g]=p;obj[b.ravel()]=(5*ps/S).ravel();obj[e[-1]]=-VALUE;obj[z]=LAMBDA;obj[v]=LAMBDA/((1-ALPHA)*S)
    constant=0.
    if base is not None:
        if refund:obj[up]=.5*p;obj[down]=.5*p
        else:obj[g]=0;obj[up]=1.5*p;obj[down]=.5*p;constant=float(base@p)
    rr=[];cc=[];vv=[]
    def add(rows,cols,values):
        rr.extend(np.atleast_1d(rows).tolist());cc.extend(np.atleast_1d(cols).tolist());vv.extend(np.broadcast_to(values,np.shape(np.atleast_1d(rows))).tolist())
    t=np.arange(T)
    add(t,e[1:],1);add(t,e[:-1],-1);add(t,c,-ETA);add(t,d,1/ETA);add(T,e[0],1)
    rhs=np.r_[np.zeros(T),e0]
    if base is not None:
        add(t+T+1,g,1);add(t+T+1,up,-1);add(t+T+1,down,1);rhs=np.r_[rhs,base]
    eq=coo_matrix((vv,(rr,cc)),shape=(len(rhs),n)).tocsr()
    rr=[];cc=[];vv=[];rows=np.arange(S*T)
    add(rows,np.tile(g,S),-1);add(rows,np.tile(c,S),1);add(rows,np.tile(d,S),-1);add(rows,b.ravel(),-1)
    add(np.repeat(S*T+np.arange(S),T),b.ravel(),(5*ps).ravel());add(S*T+np.arange(S),np.full(S,z),-1);add(S*T+np.arange(S),v,-1)
    ub=coo_matrix((vv,(rr,cc)),shape=(S*T+S,n)).tocsr();br=np.r_[(pv-load).ravel(),np.zeros(S)]
    lo=np.zeros(n);hi=np.full(n,np.inf);lo[e]=1200;hi[e]=10800;hi[c]=QMAX;hi[d]=QMAX
    res=linprog(obj,A_ub=ub,b_ub=br,A_eq=eq,b_eq=rhs,bounds=list(zip(lo,hi)),method='highs')
    if not res.success:raise RuntimeError(res.message)
    x=res.x;used_milp=False
    if np.any((x[c]>1e-7)&(x[d]>1e-7)):
        used_milp=True
        eq=hstack((eq,csr_matrix((eq.shape[0],T)))).tocsr();ub=hstack((ub,csr_matrix((ub.shape[0],T)))).tocsr()
        r=np.r_[t,t,T+t,T+t];col=np.r_[c,n+t,d,n+t];val=np.r_[np.ones(T),np.full(T,-QMAX),np.ones(T),np.full(T,QMAX)]
        mutex=coo_matrix((val,(r,col)),shape=(2*T,n+T)).tocsr()
        mat=vstack((eq,ub,mutex)).tocsr()
        lower=np.r_[rhs,np.full(len(br)+2*T,-np.inf)];upper=np.r_[rhs,br,np.zeros(T),np.full(T,QMAX)]
        res=milp(np.r_[obj,np.zeros(T)],integrality=np.r_[np.zeros(n),np.ones(T)],bounds=Bounds(np.r_[lo,np.zeros(T)],np.r_[hi,np.ones(T)]),constraints=LinearConstraint(mat,lower,upper),options={'mip_rel_gap':1e-8})
        if not res.success:raise RuntimeError(res.message)
        x=res.x
    result=dict(purchase=x[g],charge=x[c],discharge=x[d],energy=x[e],used_milp=used_milp,solver_objective=float(res.fun+constant))
    ev=evaluate(result,ps,load,pv,base,refund)
    assert abs(ev['objective']-result['solver_objective'])<1e-5
    return result
