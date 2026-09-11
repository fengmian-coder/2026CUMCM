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
