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

正式主方案在00:00制定计划，06:00和12:00允许调整，18:00保持现有计划。八种时点组合已独立比较，当前选择是本题样本内经济性比较的结果，不声称未来最优。历史窗口28日、调整阈值0.1%、30场景及风险参数保持原设置。

`python src/refresh_q3.py`重算预测、主方案、全部时点组合和新主方案敏感性；`--reuse-verified`可复用配置一致的已保存结果。随后运行`python src/complete_q3_subsets.py`和`python src/evaluate_q3_subsets.py`生成完整时点比较。

使用捆绑@oai/artifact-tool运行`src/fill_result3.mjs`更新`materials/result3.xlsx`，再运行`python src/audit_q3.py`核对逐格结果、模板标签及物理关系。`python src/audit_q3_forecast.py`核对预测因果性。

绘图顺序：`python src/prepare_q3_plot_data.py`，再运行`src/plot_q3_figures.mjs`及`src/plot_q3_extended.mjs`。所有主方案运行图使用main数据；18:00费用差图比较四时点对照减当前主方案；预测误差图保留四个时点的信息分析。最后运行`python src/write_q3_report.py`更新Word报告并渲染核对。

`outputs/q3/main`为正式结果，与`updates_0612`数值一致；`updates_061218`为四时点对照。`archive_four_time`保存原提交表、报告和原四时点敏感性。根目录下窗口、门槛及退费敏感性按新主方案重算。晚间门槛试验仍是四时点历史对照，不能当成新主方案的敏感性。

主方案2—12月自然日总费用14392992.807341274元，紧急购电177358.41029724246 kWh。调整购电量页填写最终有效购电量，其费用是调整后完整外网结算费，不与基准计划费重复相加。时间口径保持原设置：计划行00:10至次日00:10，费用与充放电自然日统计，两种窗口分别报告；不改模板时间标签。

## 第四问全年固定模型

正式第四问全年固定M0，第二问与第三问均不按月切换模型。第三问仅06:00、12:00允许调整。M0仍依当时可用历史更新预测值与权重，模型类型全年不变。

复现：依次运行src/run_q4.py、src/summarize_q4.py、src/run_q4_evidence.py、src/summarize_q4_evidence.py、src/extract_q4_paper_tables.py；捆绑Node运行src/fill_result4.mjs 2及3后运行src/audit_q4_results.py。汇总见outputs/q4/首轮结果说明.md（文件名为沿用名称，正文为当前结果）。旧月度选择与四时点结果在outputs/q4/archive_monthly_four_time，不用于当前提交。

第四问绘图：先运行 python src/prepare_q4_figures.py，再运行 npm run plot:q4（或用捆绑Node与sharp执行）。5张图保存为figures/q4_*.png与.svg，解释见outputs/q4/图表与结果分析.md。典型日按计划时窗绘制，月度统计按自然日，不混用两种窗口。
