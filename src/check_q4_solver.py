"""Independent small-instance checks for scenario price extension."""
import numpy as np
from q4_solver import solve,evaluate,VALUE,LAMBDA,grid_cost
from q3_solver import solve as oldsolve
rng=np.random.default_rng(3);L=rng.uniform(400,800,(5,12));P=rng.uniform(0,300,(5,12));p=np.linspace(.3,1.2,12)
old=oldsolve(p,6000,L,P);new=solve(np.tile(p,(5,1)),6000,L,P)
assert abs(old['solver_objective']-new['solver_objective'])<1e-6
ps=rng.uniform(.1,1.5,(5,12));s=solve(ps,6000,L,P)
b=np.maximum(L+s['charge']-P-s['purchase']-s['discharge'],0);loss=(5*ps*b).sum(axis=1)
cvar=min(v+np.maximum(loss-v,0).mean()/.1 for v in loss)
manual=float(np.mean(ps@s['purchase'])+loss.mean()+LAMBDA*cvar-VALUE*s['energy'][-1])
assert abs(manual-s['solver_objective'])<1e-6
adjust=solve(ps,6000,L,P,s['purchase'])
assert evaluate(adjust,ps,L,P,s['purchase'])['objective']<=evaluate(s,ps,L,P,s['purchase'])['objective']+1e-6
print('PASS constant-price equivalence, independent objective reconstruction, adjustment feasibility')
