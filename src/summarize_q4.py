from pathlib import Path
import json,numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/q4'
f=np.load(O/'price_forecasts.npz');a=f['actual'][31:];p=f['pred'][31:]
metrics={f'M{i}':dict(mae=float(abs(p[:,i]-a).mean()),rmse=float(np.sqrt(((p[:,i]-a)**2).mean()))) for i in range(3)}
(O/'price_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
s=json.loads((O/'summary.json').read_text(encoding='utf-8'))
lines=['# 第四问全年固定模型结果','', '统计范围为2025年2月1日00:00至2026年1月1日00:00，使用附件4真实电价事后结算。', '', '| 重算对象 | 外网结算费 元 | 紧急购电费 元 | 总费用 元 | 紧急购电量 kWh |','|---|---:|---:|---:|---:|']
for row in s:
    t=row['natural'];lines.append(f"| 问题{row['mode']} | {t['grid_fee']} | {t['emergency_fee']} | {t['total_cost']} | {t['emergency_kwh']} |")
lines+=['',f"第三问重算相对第二问重算费用减少{s[0]['natural']['total_cost']-s[1]['natural']['total_cost']}元。两者预测和调度机制均不同，不能只归因于日内调整。",'', '## 价格预测误差','', '| 模型 | MAE 元/kWh | RMSE 元/kWh |','|---|---:|---:|']
for name,m in metrics.items():lines.append(f"| {name} | {m['mae']} | {m['rmse']} |")
lines+=['','## 全年固定模型','', '第二问与第三问均全年固定使用M0，即历史同星期电价加权预测。不再按月比较M0/M1/M2后切换模型。M1、M2的误差仅用于方法对照，不参与正式决策。M0权重仍依据当时已知历史数据按原规则更新，模型类型全年不变。', '', 'M0作为简洁统一的基准模型确定，不宣称通过全年回看发现事前最优模型。电价预测值逐日生成，不等于全年使用一条不变的电价曲线。', '', '第三问部分仅允许06:00和12:00更新，18:00继续执行当前方案。统计区间和模板标签保持原设置。实际电价用于事后结算，不提前输入可执行决策。', '', '第四问继续保留延迟观测假设；与原第三问直接比较时，不应把全部差额归因于电价。固定电价对照用于分离该影响。', '', '旧月度选择及四时点结果保存在archive_monthly_four_time；新对照实验按当前固定M0与06/12策略重算。']
(O/'首轮结果说明.md').write_text('\n'.join(lines),encoding='utf-8');print(metrics)
