from pathlib import Path
import json,numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/q4'
f=np.load(O/'price_forecasts.npz');a=f['actual'][31:];p=f['pred'][31:]
metrics={f'M{i}':dict(mae=float(abs(p[:,i]-a).mean()),rmse=float(np.sqrt(((p[:,i]-a)**2).mean()))) for i in range(3)}
(O/'price_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
s=json.loads((O/'summary.json').read_text(encoding='utf-8'))
lines=['# 第四问首轮结果','', '统计范围为2025年2月1日00:00至2026年1月1日00:00，使用附件4真实电价事后结算。', '', '| 重算对象 | 外网结算费 元 | 紧急购电费 元 | 总费用 元 | 紧急购电量 kWh |','|---|---:|---:|---:|---:|']
for row in s:
    t=row['natural'];lines.append(f"| 问题{row['mode']} | {t['grid_fee']} | {t['emergency_fee']} | {t['total_cost']} | {t['emergency_kwh']} |")
lines+=['',f"第三问重算相对第二问重算费用减少{s[0]['natural']['total_cost']-s[1]['natural']['total_cost']}元。两者预测和调度机制均不同，不能只归因于日内调整。",'', '## 价格预测误差','', '| 模型 | MAE 元/kWh | RMSE 元/kWh |','|---|---:|---:|']
for name,m in metrics.items():lines.append(f"| {name} | {m['mae']} | {m['rmse']} |")
for mode in [2,3]:
    logs=json.loads((O/f'q{mode}/monthly_selection.json').read_text(encoding='utf-8'))
    lines+=['',f'问题{mode}月度选择：'+ '；'.join(f"{r['date'][:7]} M{r['selected']}" for r in logs)]
lines+=['','本轮M1/M2采用固定基准参数，未执行完整超参数搜索。价格模型的配对评价使用当前共同SOC，并减去统一终端价值。原附件、result1至result3保持不变。','', '本輪增加实测光伏延迟假设，A/F已重新生成；与原第三问比较时不能声称只改变电价。正式表格保留原模板时间标签，计划窗口与自然日窗口分别统计。', '', '其他细节见修改方法与运行口径.md。']
(O/'首轮结果说明.md').write_text('\n'.join(lines),encoding='utf-8');print(metrics)
