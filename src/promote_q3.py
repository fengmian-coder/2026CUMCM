"""Promote the verified 06/12 policy; preserve the former four-time evidence."""
from pathlib import Path
import json,shutil
R=Path(__file__).resolve().parents[1];O=R/'outputs/q3'
def summary(name):return json.loads((O/name/'summary.json').read_text(encoding='utf-8'))
if __name__=='__main__':
    old=summary('main')
    if old['config']['hours']==[6,12,18]:
        assert not (O/'updates_061218').exists()
        shutil.copytree(O/'main',O/'updates_061218')
        old['case']='updates_061218'
        (O/'updates_061218/summary.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
        archive=O/'archive_four_time';archive.mkdir(exist_ok=True)
        for name in ['comparison.json','optimization_comparison.json','optimization_notes.md','第三问建模与求解过程.docx']:
            shutil.copy2(O/name,archive/name)
        shutil.copy2(R/'materials/result3.xlsx',archive/'result3.xlsx')
        for name in ['no_refund','window14','window42','threshold0','threshold005']:
            shutil.copytree(O/name,archive/name)
    s=summary('updates_0612');assert s['config']['hours']==[6,12]
    shutil.copytree(O/'updates_0612',O/'main',dirs_exist_ok=True)
    s['case']='main'
    (O/'main/summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Promoted verified 06/12 policy; four-time results archived.')
