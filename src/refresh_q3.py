"""Run Q3 main case and independently simulated comparisons."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tmp/q2_trial_deps'))
import json
from dataclasses import replace
from q3_forecast import save
from q3_run import Config,run

if __name__=='__main__':
    for window in (28,14,42):save(window)
    cases=[('main',Config()),('only_0',Config(hours=())),('updates_06',Config(hours=(6,))),
           ('updates_0612',Config(hours=(6,12))),('no_refund',Config(refund=False)),
           ('window14',Config(window=14)),('window42',Config(window=42)),
           ('threshold0',Config(threshold=0)),('threshold005',Config(threshold=.005))]
    reports=[]
    for name,cfg in cases:reports.append(run(cfg,name,save_detail=True))
    (ROOT/'outputs/q3/comparison.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
