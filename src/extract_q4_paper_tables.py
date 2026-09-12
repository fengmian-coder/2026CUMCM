"""Extract specified-date tables from formal Q4 arrays, without rounding."""
from pathlib import Path
from datetime import date
import numpy as np,csv,json
R=Path(__file__).resolve().parents[1]/'outputs/q4';O=R/'paper_tables';O.mkdir(exist_ok=True)
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21'];clock=lambda t:f'{t//6}:{t%6*10:02d}'
for mode in [2,3]:
    with np.load(R/f'q{mode}/schedules.npz') as f:a={k:f[k] for k in f.files}
    with np.load(R/f'q{mode}/natural.npz') as f:n={k:f[k] for k in f.files}
    purchase=[];storage=[];emergency=[];daily=[]
    for day in dates:
        d=(date.fromisoformat(day)-date(2025,1,1)).days;i=d-31
        for h in [10,12,14,16,18,20]:
            t=h*6;purchase.append([day,f'{clock(t)}-{clock(t+1)}',float(n['baseline'][i,t]),float(n['purchase'][i,t])])
            assert n['purchase'][i,t]==a['purchase'][d,t-1]
        for j in range(6):storage.append([day,f'{clock(j*24)}-{clock((j+1)*24)}',float(n['charge'][i,j*24:(j+1)*24].sum()),float(n['discharge'][i,j*24:(j+1)*24].sum())])
        daily.append([day,float(n['purchase'][i].sum()),float(n['grid_fee'][i].sum()),float(n['emergency_fee'][i].sum()),float((n['grid_fee'][i]+n['emergency_fee'][i]).sum()),float(n['energy'][i,0]),float(n['energy'][i,-1]),float(a['purchase'][d].sum()),float(a['grid_fee'][d].sum())])
        t=0;count=0
        while t<144:
            if n['emergency'][i,t]<=1e-7:t+=1;continue
            start=t
            while t<144 and n['emergency'][i,t]>1e-7:t+=1
            emergency.append([day,f'{clock(start)}-{clock(t)}',float(n['emergency'][i,start:t].sum())]);count+=1
        if not count:emergency.append([day,'无紧急购电',0.])
        assert abs(sum(r[2] for r in emergency if r[0]==day)-n['emergency'][i].sum())<1e-7
    sections=[('指定时段购电',['日期','时段','零点计划购电量 kWh','最终购电量 kWh'],purchase),
        ('充放电',['日期','时段','充电量 kWh','放电量 kWh'],storage),
        ('紧急购电',['日期','时段','购电量 kWh'],emergency),
        ('日汇总',['日期','自然日最终购电量 kWh','自然日外网结算费 元','自然日紧急购电费 元','自然日总费 元','00:00电量 kWh','24:00电量 kWh','模板计划窗口最终购电量 kWh','模板计划窗口外网结算费 元'],daily)]
    lines=[f'# 第四问对应问题{mode}的指定日期表格','','数值来自首轮正式结果，与当前result4表格一致。原始浮点值直接导出，不主动舍入。指定时段采用自然日时间；日汇总同时列出自然日窗口和模板计划窗口，不能混加。第三问最终外网结算费已含调整影响，不与基准计划费重复相加。']
    for name,headers,rows in sections:
        with (O/f'q{mode}_{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f);w.writerow(headers);w.writerows(rows)
        lines+=['',f'## {name}','','| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]
        lines+=['| '+' | '.join(map(str,row))+' |' for row in rows]
    (O/f'q{mode}_指定日期表格.md').write_text('\n'.join(lines),encoding='utf-8')
print('Four dates, both questions, eight CSV tables and two Markdown reports checked and saved.')
