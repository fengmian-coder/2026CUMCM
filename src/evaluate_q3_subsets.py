from pathlib import Path
import json,csv
import numpy as np
from q2_data import load_q2_data
R=Path(__file__).resolve().parents[1];O=R/'outputs/q3';data=load_q2_data()
rows=json.loads((O/'all_subsets.json').read_text(encoding='utf-8'));assert len(rows)==8
lookup={frozenset(r['hours'][1:]):r for r in rows};p=np.roll(data.price_yuan_per_kwh,-1)
audits=[]
for r in rows:
    with np.load(O/r['case']/'schedules.npz') as z:a={k:z[k] for k in z.files}
    with np.load(O/r['case']/'natural.npz') as z:n={k:z[k] for k in z.files}
    state=a['energy'][:,1:]-a['energy'][:,:-1]-.9*a['charge']+a['discharge']/.9
    balance=a['purchase']+data.source_pv_kw/6+a['discharge']+a['emergency']-data.source_load_kw/6-a['charge']-a['surplus']
    assert abs(state).max()<1e-7 and abs(balance).max()<1e-7
    assert np.array_equal(n['purchase'][:,0],a['purchase'][30:364,-1])
    assert np.array_equal(n['purchase'][:,1:],a['purchase'][31:,:143])
    assert abs(p*(a['purchase']+.5*abs(a['purchase']-a['baseline']))-a['grid_fee']).max()<1e-9
    first=min(r['hours'][1:],default=24)*6
    for k,b in [('purchase','baseline'),('charge','baseline_charge'),('discharge','baseline_discharge')]:assert np.array_equal(a[k][:,:first],a[b][:,:first])
    assert abs(a['energy'][:-1,-1]-a['energy'][1:,0]).max()<1e-7
    assert abs((n['grid_fee']+n['emergency_fee']).sum()-r['natural_totals']['total_cost_yuan'])<1e-7
    audits.append(dict(case=r['case'],state_error=float(abs(state).max()),balance_error=float(abs(balance).max()),mapping_exact=True,pre_first_update_locked=True))
cost=lambda r:r['natural_totals']['total_cost_yuan']
full=lookup[frozenset([6,12,18])];base=lookup[frozenset()];best=min(rows,key=cost)
marginals=[]
for h in [6,12,18]:
    for subset,r in lookup.items():
        if h in subset:continue
        after=lookup[subset|{h}]
        marginals.append(dict(added_hour=h,existing_hours=sorted(subset),saving_yuan=cost(r)-cost(after)))
out=dict(best_case=best['case'],best_hours=best['hours'],saving_vs_only0=cost(base)-cost(best),saving_vs_all=cost(full)-cost(best),marginal_savings=marginals,audits=audits)
(O/'subsets_evaluation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 原第三问八种预报时点组合评价','','00:00始终保留，枚举06:00、12:00、18:00的全部8种使用组合。保持原第三问实测光伏锚点、固定电价、30场景及随机种子20260912、28日择优窗口、0.1%调整门槛、退费解释和风险参数一致。每组从1月1日独立连续运行；费用统计2月1日00:00至次年1月1日00:00。未使用第四问的延迟观测改法。','','| 使用时点 | 总费用 元 | 紧急购电量 kWh | 期末电量 kWh |','|---|---:|---:|---:|']
for r in sorted(rows,key=cost):lines.append(f"| {'、'.join(f'{h:02d}:00' for h in r['hours'])} | {cost(r)} | {r['natural_totals']['emergency_kwh']} | {r['final_midnight_energy']} |")
lines+=['',f"本次样本中费用最低的组合为{best['hours']}，相对仅零点节省{cost(base)-cost(best)}元，相对四时点节省{cost(full)-cost(best)}元。",'', '## 从完整方案分别删除一次','','正差额表示删除后更贵。','','| 删除时点 | 删除后的总费用 元 | 相对完整方案费用差 元 |','|---|---:|---:|']
for h in [6,12,18]:
    r=lookup[frozenset({6,12,18}-{h})];lines.append(f'| {h}:00 | {cost(r)} | {cost(r)-cost(full)} |')
lines+=['','## 不同前提下增加一个时点','','正节省表示加入后更便宜，负节省表示加入后更贵。','','| 已有日内时点 | 新增时点 | 费用节省 元 |','|---|---:|---:|']
for m in marginals:lines.append(f"| {m['existing_hours']} | {m['added_hour']} | {m['saving_yuan']} |")
lines+=['','## 解释范围','','8种组合覆盖的是预先固定的更新时间集合，不是所有可能调度策略的全局最优搜索。每次允许更新仍执行收益门槛，允许保持计划。各策略SOC连续递推，因此差额包括跨日路径影响；期末电量列明，不能隐藏库存差别。','','比较针对当前模型、数据和一个固定场景种子，最佳组合是样本内回顾性结果，不是未来全年最优保证。不能依据完整年度实际费用倒选每一天的更新时点。若要把某组合作为事前策略，需要独立日期或多种子支持。经确认，正式result3采用00:00、06:00、12:00方案；四时点结果保存在updates_061218，原提交表及旧敏感性结果保存在archive_four_time。','','题目最后一句可据此回答是否值得引入日内预报，以及不同更新时间的条件性价值。不能仅凭固定加入顺序认定某时点绝对无用；应结合全部12项条件边际比较及分别删除试验。']
(O/'八种时点组合总体评价.md').write_text('\n'.join(lines),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
