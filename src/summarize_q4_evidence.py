"""Independent evidence checks and paper-ready comparison notes."""
from pathlib import Path
import json,csv
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/q4';E=O/'evidence'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
baseline={s['mode']:s for s in read(O/'summary.json')};records=read(E/'summary.json')
assert len(records)==14
cases={(s['case'],s['mode']):s for s in records}
rows=[];audits=[]
price=np.load(O/'price_forecasts.npz')['actual']
from q2_data import load_q2_data
data=load_q2_data()
for r in records:
    path=E/r['case']/f"q{r['mode']}"
    with np.load(path/'schedules.npz') as z:a={k:z[k] for k in z.files}
    with np.load(path/'natural.npz') as z:n={k:z[k] for k in z.files}
    p=np.broadcast_to(np.roll(data.price_yuan_per_kwh,-1),price.shape) if r['case']=='fixed_tariff' else price
    fee=p*(a['purchase']+(.5*abs(a['purchase']-a['baseline']) if r['mode']==3 else 0))
    err=float(abs(fee-a['grid_fee']).max());assert err<1e-9
    assert abs(5*p*a['emergency']-a['emergency_fee']).max()<1e-9
    assert abs(float((n['grid_fee']+n['emergency_fee']).sum())-r['natural']['total_cost'])<1e-7
    assert np.array_equal(n['purchase'][:,0],a['purchase'][30:364,-1])
    assert np.array_equal(n['purchase'][:,1:],a['purchase'][31:,:143])
    np.testing.assert_allclose(a['energy'][:-1,-1],a['energy'][1:,0],atol=1e-7,rtol=0)
    rows.append(dict(case=r['case'],mode=r['mode'],cost=r['natural']['total_cost'],emergency_kwh=r['natural']['emergency_kwh'],
        cost_change_from_formal=r['natural']['total_cost']-baseline[r['mode']]['natural']['total_cost'],
        final_energy=r['final_midnight_energy'],scenario_count=r['scenario_count'],seed=r['random_seed']))
    audits.append(dict(case=r['case'],mode=r['mode'],fee_error=err,natural_mapping_exact=True))
assert cases['fixed_tariff',2]['natural']['total_cost']==14715290.650415003
with np.load(O/'q3/schedules.npz') as f,np.load(E/'fixed_m0/q3/schedules.npz') as g:
    assert all(np.array_equal(f[k],g[k]) for k in f.files)
(E/'audit.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
with (E/'comparison.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=['# 第四问补充对照与稳定性试验','','所有费用均为2025年2月1日00:00至次年1月1日00:00的自然日真实结算费。各方案从1月1日6000 kWh独立连续运行；原正式结果不替换。','','## 完整对照','','| 试验 | 问题 | 总费用 元 | 相对正式结果费用差 元 | 紧急购电量 kWh | 期末电量 kWh |','|---|---:|---:|---:|---:|---:|']
for r in rows:lines.append(f"| {r['case']} | {r['mode']} | {r['cost']} | {r['cost_change_from_formal']} | {r['emergency_kwh']} | {r['final_energy']} |")
lines+=['','## 模型择优的价值']
for m in [2,3]:
    delta=cases['fixed_m0',m]['natural']['total_cost']-baseline[m]['natural']['total_cost']
    lines.append(f'问题{m}：正式按月择优相对始终M0节省{delta}元。')
lines+=['','第三问正式方案与固定M0的全部已保存动作数组逐项完全相同。第二问固定电价试验精确复现原第二问费用，支持场景求解器对固定电价的兼容性。','','## 电价与光伏信息影响分开说明']
for m in [2,3]:
    fixed=cases['fixed_tariff',m]['natural']['total_cost'];variable=cases['fixed_m0',m]['natural']['total_cost']
    lines.append(f'问题{m}：保持同一预测信息、固定M0规则和源荷抽样，波动电价情形相对固定电价费用变化{variable-fixed}元。')
lines+=['','该差额包含实际电价水平与形态变化、价格不确定性和重新调度的共同影响，不能称为纯粹的“电价预测误差成本”。固定电价下价格场景无波动。',f"固定电价下，第三问把原实测锚点换为延迟观测锚点后，费用变化{cases['fixed_tariff',3]['natural']['total_cost']-14395252.02211192}元。",'', '## 抽样稳定性']
for m in [2,3]:
    seedcases=[baseline[m]]+[cases[k,m] for k in ['seed_20260913','seed_20260914']]
    v=[r['natural']['total_cost'] for r in seedcases]
    lines.append(f'问题{m}，30场景三个种子的费用范围为{min(v)}至{max(v)}元，极差{max(v)-min(v)}元；相对正式费用极差为{(max(v)-min(v))/v[0]*100}%。')
    for count in [50,100]:
        r=cases[f'scenarios_{count}',m]
        lines.append(f"{count}场景总费用{r['natural']['total_cost']}元，期末电量{r['final_midnight_energy']} kWh。")
lines+=['','三个种子只能提供初步敏感性证据，不能构造有充分重复次数支持的置信区间。场景数比较只有一个固定种子，不能据此宣布已收敛，也不能选择最便宜的随机种子作为优化成果。每次改变抽样都重算历史配对与月度选择，包含模型选择的变化。期末电量不同的比较须同时报告状态，不能全部归因于当期策略。','','## 完美电价对照']
for m in [2,3]:lines.append(f"问题{m}，正式方案比完美电价对照多花{baseline[m]['natural']['total_cost']-cases['perfect_price',m]['natural']['total_cost']}元。")
lines+=['','此对照提前使用当日真实电价，仅作不可执行参照。源荷仍有不确定性，优化仍包含风险和终端价值，故不宣称实际现金费用严格下界。其价格残差为零。','','## 指定日期论文表格','','outputs/q4/paper_tables保存3月20日、6月21日、9月23日、12月21日的指定时段购电、六段充放电、紧急购电和日汇总，共8份CSV及2份Markdown。全部取自当前正式首轮结果，不使用敏感性方案，不主动舍入。','', '独立核验通过真实电价结算、自然日映射和跨日衔接；各运行还检查电量平衡、容量和功率边界、同段充放电互斥。']
(E/'补充试验说明.md').write_text('\n'.join(lines),encoding='utf-8');print(json.dumps(rows,ensure_ascii=False,indent=2))
