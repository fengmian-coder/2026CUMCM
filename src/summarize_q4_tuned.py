from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]/'outputs/q4/archive_monthly_four_time';T=R/'tuned'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
old=read(R/'summary.json');new=read(T/'summary.json')
comparison=[]
for a,b in zip(old,new):
    comparison.append(dict(mode=a['mode'],first_cost=a['natural']['total_cost'],tuned_cost=b['natural']['total_cost'],
        cost_change=b['natural']['total_cost']-a['natural']['total_cost'],
        emergency_change_kwh=b['natural']['emergency_kwh']-a['natural']['emergency_kwh'],
        final_energy_change=b['final_midnight_energy']-a['final_midnight_energy']))
(T/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 第四问电价调参对照结果','','首轮正式结果保留。本次只更换电价预测，保持光伏、负载、场景抽样、风险参数、月度选择门槛和结算方法一致，各策略从1月1日6000 kWh连续运行。','','## 参数验证方法','','每月仅用此前14天验证，验证起点之前的数据拟合候选；选定后用当月开始前全部数据重估。历史不足时沿用首轮预测。M1比较8组傅里叶阶数：日3/6/12/24阶、周1/3阶；误差模型固定为平稳AR(1)，条件最小二乘估计，与首轮极大似然估计不同。这不是完整ARIMA(p,d,q)搜索。M2比较12组学习率、轮数和叶节点组合，其他参数固定，关闭随机早停。','','## 自然日费用对照','','统计范围为2月1日00:00至次年1月1日00:00。正差额表示调参版更贵。','','| 重算对象 | 首轮费用 元 | 调参费用 元 | 费用差 元 | 紧急购电量差 kWh |','|---|---:|---:|---:|---:|']
for r in comparison:lines.append(f"| 问题{r['mode']} | {r['first_cost']} | {r['tuned_cost']} | {r['cost_change']} | {r['emergency_change_kwh']} |")
lines+=['','## 预测误差','','| 模型 | 首轮MAE 元/kWh | 调参MAE 元/kWh |','|---|---:|---:|']
om=read(R/'price_metrics.json');nm=read(T/'price_metrics.json')
for name in om:lines.append(f"| {name} | {om[name]['mae']} | {nm[name]['mae']} |")
for mode in [2,3]:
    path=T/f'q{mode}/model_selection.json'
    logs=read(path if path.exists() else T/f'q{mode}/monthly_selection.json');lines+=['',f'问题{mode}选择：'+ '；'.join(f"{r['date'][:7]} M{r['selected']}" for r in logs)]
lines+=['','## 解释与限定','','参数只在此前日期验证，不代表全年事后最优。本次方案设计发生于看过首轮全年结果之后，因此属于回顾性方法改进，不能宣称未接触的外部测试。预测MAE改善不保证风险调度目标或事后现金费用改善。选择门槛保持0.5%，不为追求回测省钱临时调低。','','两套调度均通过电量平衡、充放电互斥、容量功率边界和SOC连续性检查。改变4月2日起的实际电价后，当日及此前调参预测完全不变。当前materials中的result4-2和result4-3保留首轮版本，调参版数据在本目录q2、q3下。']
(T/'调参对照说明.md').write_text('\n'.join(lines),encoding='utf-8');print(comparison)
