# 2026CUMCM
This project documents the complete journey of participating in the 2026 China Undergraduate Mathematical Contest in Modeling (CUMCM).

## 第一问复现

计算环境需要 Python 3.11+、NumPy、SciPy 和 openpyxl。运行：

```powershell
python src/verify_q1.py
python src/q1_dynamic_programming.py
python src/audit_q1.py
```

论文图使用 Node.js 与 Sharp 生成：

```powershell
npm install
npm run plot:q1
```

第一问采用左端点分段常值功率。自然日求解将附件最后的午夜样本移至首位，作为显式周期边界假设；输出购电量逆向映射回模板原顺序。模板标签不修改，原始数值不主动舍入。

## 第二问复现

正式口径：每天00:00制定当天00:10至次日00:10的144段计划；当天首段执行前一天已锁定的末段。零点与00:10储电量严格区分，初始状态从1月1日连续递推。

```powershell
python src/refresh_q2.py
```

该命令重算预测、主模型、基准比较、风险及终端价值敏感性和场景图数据。需要NumPy、SciPy和openpyxl；本机临时SciPy依赖在tmp/q2_trial_deps。

随后使用已配置的@oai/artifact-tool运行src/fill_result2.mjs填写materials/result2.xlsx，再运行：

```powershell
python src/audit_result2.py
python src/audit_q2_time_axis.py
npm run plot:q2
```

本机可将fill_result2.mjs复制到tmp/q2_artifact后用捆绑Node运行，该目录的node_modules连接到工作区捆绑依赖。

正式数据在outputs/q2，正式图在figures/q2_*，解释和数值见outputs/q2/modeling_notes.md。q2_schedules.npz按计划日期保存365×144个动作及365×145个状态；q2_schedule.csv与natural_reporting.npz按2—12月自然日保存执行结果。result2_plan_rows.json提供直接写表的334×144个购电值。

计划表合计覆盖2月1日00:10至次年1月1日00:10；自然日费用、充放电和紧急购电覆盖2月1日00:00至次年1月1日00:00。两种窗口分别标注，不能混加。官方模板标签保持原样。

旧版结果、图和相关代码归档在outputs/q2_legacy_natural；outputs/q2_shifted_trial为前期新口径试验。q2_extend_boundary.py已经停用，不再生成次日新计划补格。

## 第三问复现

`python src/refresh_q3.py`运行预测来源滚动选择与九组独立仿真。主方案使用00:00、06:00、12:00、18:00预报，历史选择窗口28日，调整阈值0.1%，风险参数沿用第二问。退订退费属于显式假设，不退费方案单独保留。

使用已配置的@oai/artifact-tool运行`src/fill_result3.mjs`填写`materials/result3.xlsx`，随后运行`python src/audit_q3.py`与`python src/audit_q3_forecast.py`。图由`src/plot_q3_figures.mjs`生成，Word说明由`src/write_q3_report.py`生成。Node脚本可复制到已配置捆绑依赖的`tmp/q2_artifact`目录执行。

`outputs/q3/main`保存主方案，`outputs/q3/comparison.json`保存九组汇总，`outputs/q3/第三问建模与求解过程.docx`说明公式、假设、执行边界、结果及核验。原result3模板备份为`outputs/q3/result3_template_original.xlsx`。

主方案2—12月自然日总费用为14395252.02211192元。四时点方案并非本次比较中费用最低的组合：仅用00:00、06:00、12:00的费用为14392992.807341274元，此差异已如实保留。调整购电量页填写最终有效购电量，费用为调整后完整外网结算费，不与基准计划费重复相加。计划行窗口和自然日统计窗口沿用第二问并分别报告，模板标签保持不变。
