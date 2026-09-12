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
```

正式结果位于 `outputs/q2`。日前计划中的购电、充电和放电在同一天的所有
情景中保持一致，只有紧急购电随情景变化；实际数据仅用于次日更新与事后
结算。自然日首个区间采用前一行的 24:00 样本，2025 年 1 月 1 日首个区间
采用 0:10 样本作最近邻延拓。所有计算保留原始浮点精度。

`result2.xlsx` 的列从 0:10 开始并包含次日 0:00–0:10，而修订模型的自然日
计划为当日 0:00–24:00。写回模板前必须明确这两个 24 小时窗口的映射，程序
不会改写模板标签或默认平移结果。
