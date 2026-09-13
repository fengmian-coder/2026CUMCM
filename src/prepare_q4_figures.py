"""Prepare Q4 figures and discussion from full-precision saved results."""
from pathlib import Path
from datetime import date,timedelta
import json,numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/q4'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def arrays(p):
    with np.load(p) as z:return {k:z[k] for k in z.files}
s={r['mode']:r for r in read(O/'summary.json')};e={(r['case'],r['mode']):r for r in read(O/'evidence/summary.json')}
for r in s.values():assert r['fixed_model']==0 and r['update_hours']==([6,12] if r['mode']==3 else [])
p=arrays(O/'price_forecasts.npz');dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
forecast=[]
for dt in dates:
    d=(date.fromisoformat(dt)-date(2025,1,1)).days
    forecast.append(dict(date=dt,actual=p['actual'][d].tolist(),prediction=p['pred'][d,0].tolist()))
daily_dates=[date(2025,2,1)+timedelta(days=i) for i in range(334)]
monthly=[];dispatch=[];annual=[];sensitivity=[]
for m in [2,3]:
    a=arrays(O/f'q{m}/schedules.npz');n=arrays(O/f'q{m}/natural.npz');fixed=arrays(O/f'evidence/fixed_tariff/q{m}/natural.npz')
    assert abs((n['grid_fee']+n['emergency_fee']).sum()-s[m]['natural']['total_cost'])<1e-7
    d=(date(2025,6,21)-date(2025,1,1)).days
    dispatch.append(dict(mode=m,date='2025-06-21',purchase_kw=(a['purchase'][d]*6).tolist(),storage_kw=((a['discharge'][d]-a['charge'][d])*6).tolist(),soc=(a['energy'][d]/12000*100).tolist()))
    for month in range(2,13):
        mask=np.array([dt.month==month for dt in daily_dates])
        monthly.append(dict(mode=m,month=month,cost=float((n['grid_fee'][mask]+n['emergency_fee'][mask]).sum()),fixed_cost=float((fixed['grid_fee'][mask]+fixed['emergency_fee'][mask]).sum()),emergency=float(n['emergency'][mask].sum()),fixed_emergency=float(fixed['emergency'][mask].sum())))
    for label,r in [('固定电价',e['fixed_tariff',m]),('波动电价',s[m])]:annual.append(dict(mode=m,label=label,**r['natural']))
    for label,r in [('30',s[m]),('50',e['scenarios_50',m]),('100',e['scenarios_100',m]),('种子12',s[m]),('种子13',e['seed_20260913',m]),('种子14',e['seed_20260914',m])]:sensitivity.append(dict(mode=m,label=label,**r['natural'],final_energy=r['final_midnight_energy']))
data=dict(forecast=forecast,dispatch=dispatch,monthly=monthly,annual=annual,sensitivity=sensitivity)
(O/'figure_data.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
lines=['# 第四问图表与结果分析','','正式设置：全年固定M0，第二问不作日内调整，第三问允许06:00、12:00调整。自然日统计范围为2025年2月1日00:00至2026年1月1日00:00。原始数值和计算中间量不舍入，图中刻度仅控制显示精度。','','## 电价预测与典型日图','','q4_price_forecast展示题目指定的3月20日、6月21日、9月23日和12月21日，不按拟合好坏选日期。横轴为计划时刻，0:10至次日0:10；每个值对应左端点开始的10分钟区间，以阶梯线表示。预测使用当天00:00可获得的信息。',f"M0评估MAE为{read(O/'price_metrics.json')['M0']['mae']}元/kWh，RMSE为{read(O/'price_metrics.json')['M0']['rmse']}元/kWh。四张日曲线只展示局部，不代替全年误差。",'','## 固定电价与波动电价','','q4_tariff_cost_comparison分别展示完整费用、外网结算费和紧急购电费，横向两个面板使用相同坐标范围。固定电价对照保持第四问相同的光伏信息和调整时点，避免把原第三问实测锚点与第四问延迟观测差异混入价格对照。']
for m in [2,3]:
    v=s[m]['natural'];f=e['fixed_tariff',m]['natural']
    lines.append(f"问题{m}：波动电价总费用{v['total_cost']}元，固定电价总费用{f['total_cost']}元，费用变化{v['total_cost']-f['total_cost']}元；紧急购电量变化{v['emergency_kwh']-f['emergency_kwh']} kWh。")
lines+=['费用差同时包含实际电价水平、价格形态、预测不确定性及调度响应，不能称为纯电价预测误差成本。紧急购电量减少也不意味着总费用一定减少。','','## 电价与调度响应','','q4_price_dispatch采用指定日期6月21日，左右分别为第二问和第三问，上中下三行对应电价、功率和SOC。购电功率由10分钟购电量乘6得到；储能净输出为放电功率减充电功率，负值表示充电。SOC使用145个时段边界，功率使用144个时段值，不混淆状态与流量。','计划窗口为当天00:10至次日00:10。图中实际电价仅作事后参照，决策依据预测电价和价格场景；不能看到真实低价充电就认定模型事先知道真实电价。储能响应还受容量、功率、效率、负载、光伏、风险及终端价值共同制约。','','## 月度费用与紧急购电','','q4_monthly_comparison按自然日归入月份，左右分别比较第二问和第三问，上下分别表示费用和紧急购电量。图中的两种电价情形采用相同信息假设。']
for m in [2,3]:
    rows=[r for r in monthly if r['mode']==m];r=max(rows,key=lambda r:r['cost']-r['fixed_cost'])
    lines.append(f"问题{m}费用增幅最大的月份为{r['month']}月，增加{r['cost']-r['fixed_cost']}元。这是描述性统计，不能仅凭月份归因于天气或季节，需结合源荷及价格数据验证。")
lines+=['','## 场景数与抽样敏感性','','q4_sampling_sensitivity左图为30、50、100场景，右图为固定30场景下的三个随机种子；两问题使用统一费用坐标。右图是三次确定的独立运行点，不绘制没有统计依据的置信区间。']
for m in [2,3]:
    costs=[s[m]['natural']['total_cost']]+[e[k,m]['natural']['total_cost'] for k in ['seed_20260913','seed_20260914']]
    lines.append(f"问题{m}三个种子的费用极差为{max(costs)-min(costs)}元，占正式费用{(max(costs)-min(costs))/costs[0]*100}%。100场景相对30场景费用变化{e['scenarios_100',m]['natural']['total_cost']-costs[0]}元。")
lines+=['当前场景数试验只有一个种子，不能证明收敛；三个种子也不足以构造可靠置信区间。正式方案仍保留30场景，不因单次100场景费用较低自动替换。期末库存如下，费用比较不得隐藏库存差异。','','| 问题 | 场景或种子 | 总费用 元 | 期末电量 kWh |','|---|---|---:|---:|']
for r in sensitivity:lines.append(f"| {r['mode']} | {r['label']} | {r['total_cost']} | {r['final_energy']} |")
lines+=['','## 完美电价与可改进空间']
for m in [2,3]:lines.append(f"问题{m}正式方案比提前知道电价的对照多花{s[m]['natural']['total_cost']-e['perfect_price',m]['natural']['total_cost']}元。")
lines+=['完美电价仅是不可执行参照，不是保证可获得的节省额；源荷仍不确定，优化含风险项和终端价值，所以不能称为实际费用的严格下界。','','## 总体结论与解释边界',f"当前第三问重算比第二问重算少花{s[2]['natural']['total_cost']-s[3]['natural']['total_cost']}元，两者零点光伏预测和日内更新机制均不同，不能把全部收益只归因于06:00、12:00调整。",'全年固定M0消除了模型类型按月切换，预测值及权重仍根据当时已知历史更新。M0并非已证明在所有未来日期最优。','当前固定电价问题三已比较全部8种时点组合；波动电价下尚未重新枚举全部组合。因此本问结论是相同06:00、12:00策略在波动电价下的运行评价，不宣称其为波动电价最优时点选择。','图中不额外添加底部说明小字；必要的解释集中在本说明和论文正文。全部图输出PNG与SVG，配色沿用现有方案。']
(O/'图表与结果分析.md').write_text('\n'.join(lines),encoding='utf-8');print('Q4 plot data and discussion saved')
