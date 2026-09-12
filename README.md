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

第二问按修订方案使用自然日左端点映射、严格滚动预测、联合残差情景和
CVaR 日前随机优化。依次运行：

```powershell
python src/q2_forecast.py
python src/q2_forecast_compare.py
python src/q2_optimize.py
python src/audit_q2.py
python src/q2_sensitivity.py
python src/q2_terminal_sensitivity.py
python src/q2_benchmarks.py
python src/q2_extend_boundary.py
python src/audit_result2.py
python src/export_q2_figure_data.py
npm run plot:q2
```

正式结果位于 `outputs/q2`。日前计划中的购电、充电和放电在同一天的所有
情景中保持一致，只有紧急购电随情景变化；实际数据仅用于次日更新与事后
结算。自然日首个区间采用前一行的 24:00 样本，2025 年 1 月 1 日首个区间
采用 0:10 样本作最近邻延拓。所有计算保留原始浮点精度。

`result2.xlsx` 保留官方模板标签。日期 `d` 的计划购电行写入自然日结果的
第 2–144 段及日期 `d+1` 的第 1 段；充放电量、SOC 和紧急购电仍按自然日
统计。2025 年 12 月 31 日最后一列由额外生成的 2026 年 1 月 1 日首段结果
补齐。写表后运行独立审计，确认重排、分段汇总和紧急购电合并均与原结果一致。
