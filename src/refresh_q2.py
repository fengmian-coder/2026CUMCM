"""Recompute all canonical shifted Q2 data and analytical references."""
from pathlib import Path
import sys
import runpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/q2_trial_deps'))
if __name__=='__main__':
    for name in ('q2_forecast','q2_forecast_compare','q2_optimize','audit_q2',
                 'q2_sensitivity','q2_terminal_sensitivity','q2_benchmarks','export_q2_figure_data'):
        print('RUN',name,flush=True)
        sys.argv=[name+'.py']
        runpy.run_path(str(ROOT/'src'/f'{name}.py'),run_name='__main__')
