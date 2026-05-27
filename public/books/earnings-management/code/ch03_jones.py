# =====================================================
# code/ch03_jones.py
# 第 3 章 Jones (1991) 的 Python 实现
# =====================================================

import pandas as pd
import numpy as np

np.random.seed(2026)

p = pd.read_csv("data/em_panel.csv", low_memory=False)
p = p.dropna(subset=["TA", "dSale_s", "PPE_s", "inv_lag_at"]).reset_index(drop=True)

# 按 fyear 分组跑 OLS，把残差合回原数据
da_jones = pd.Series(index=p.index, dtype=float)
year_r2 = {}
for yr, sub in p.groupby("fyear"):
    X = sub[["inv_lag_at", "dSale_s", "PPE_s"]].values
    y = sub["TA"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    da_jones.loc[sub.index] = resid
    # R 端 lm(y ~ 0 + X) 的 R² 用 uncentered SS：1 - SS_resid/SS_y
    year_r2[int(yr)] = 1 - np.sum(resid ** 2) / np.sum(y ** 2)

p["DA_jones"] = da_jones
r2_series = pd.Series(year_r2)
n_per_year = p["fyear"].value_counts()

print("======== 3.1 Jones 年度回归概况 ========")
print(f"回归年数：   {len(r2_series)}")
print(f"平均样本量： {n_per_year.mean():.0f}")
print(f"平均 R^2：   {r2_series.mean():.4f}")

print("\n======== 3.2 DA_jones 描述统计 ========")
print(p["DA_jones"].describe().round(4))

print("\n======== 3.3 案例公司 DA_jones ========")
p["rank_jones"] = (
    p.groupby("fyear")["DA_jones"]
     .transform(lambda s: s.abs().rank(pct=True))
)
case = p.loc[p["company"].notna(),
             ["company", "fyear", "misstate", "DA_jones", "rank_jones"]]
print(case.sort_values(["company", "fyear"]).to_string(index=False))
