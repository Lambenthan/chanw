# =====================================================
# code/ch10_summary.py
# 第 10 章 F-Score 与九方法终极对比的 Python 实现
# 直接读 R 端写出的 ch10_master_panel.csv 主合表
# =====================================================

import pandas as pd
import numpy as np
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

np.random.seed(2026)

master = pd.read_csv("data/ch10_master_panel.csv")

print("======== 10.1 九方法 Pearson 相关矩阵 ========")
methods = ["DA_healy", "DA_deangelo", "DA_jones", "DA_mj",
           "DA_pm", "DA_dd", "DA_mcn", "DA_stb", "DA_rm"]
print(master[methods].corr().round(3))

print("\n======== 10.2 九方法 Spearman 相关矩阵 ========")
print(master[methods].corr(method="spearman").round(3))

# F-Score logit
fs = master.dropna(subset=["DA_mj", "DA_rm", "DA_stb",
                            "DA_dd", "ROA", "misstate"])
print(f"\nF-Score 训练样本: {len(fs)} firm-year, "
      f"misstate=1: {int(fs['misstate'].sum())}")

X = sm.add_constant(fs[["DA_mj", "DA_rm", "DA_stb",
                        "DA_dd", "ROA"]])
fit = sm.Logit(fs["misstate"], X).fit(disp=False)

print("\n======== 10.3 F-Score logit 系数 ========")
print(fit.summary().tables[1])

score = fit.predict(X)
fs = fs.assign(pred_prob=score)
fs["F_Score"] = fs["pred_prob"] / fs["pred_prob"].mean()
print(f"\nF-Score AUC = {roc_auc_score(fs['misstate'], score):.4f}")

# 案例公司九方法对照
case = master[master["company"].notna()]
print("\n======== 10.4 案例公司九方法 DA（部分年份）========")
print(case[["company", "fyear", "misstate"] + methods]
      .sort_values(["company", "fyear"])
      .to_string(index=False))
