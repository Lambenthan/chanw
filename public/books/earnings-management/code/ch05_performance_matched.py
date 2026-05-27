# =====================================================
# code/ch05_performance_matched.py
# 第 5 章 Performance-Matched DA (Kothari 2005) 的 Python 实现
# =====================================================

import pandas as pd
import numpy as np

np.random.seed(2026)

p = pd.read_csv("data/em_panel.csv", low_memory=False)
p["dSaleRect_s"] = p["dSale_s"] - p["dRect_s"]
p = p.dropna(subset=["TA", "dSaleRect_s", "PPE_s",
                      "inv_lag_at", "ROA"]).reset_index(drop=True)

# 先跑 Modified Jones 得到 DA_mj
da_mj = pd.Series(index=p.index, dtype=float)
for yr, sub in p.groupby("fyear"):
    X = sub[["inv_lag_at", "dSaleRect_s", "PPE_s"]].values
    y = sub["TA"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    da_mj.loc[sub.index] = y - X @ beta
p["DA_mj"] = da_mj

# 同 fyear 内按 ROA 最近邻配对
da_pm = pd.Series(index=p.index, dtype=float)
for yr, sub in p.groupby("fyear"):
    sub = sub.sort_values("ROA")
    da = sub["DA_mj"].values
    roa = sub["ROA"].values
    n = len(sub)
    if n < 2:
        continue
    left_da = np.roll(da, 1)
    right_da = np.roll(da, -1)
    left_d = np.abs(np.roll(roa, 1) - roa)
    right_d = np.abs(np.roll(roa, -1) - roa)
    left_d[0] = np.inf
    right_d[-1] = np.inf
    use_left = left_d <= right_d
    near = np.where(use_left, left_da, right_da)
    da_pm.loc[sub.index] = da - near

p["DA_pm"] = da_pm

print("======== 5.1 PM-DA 描述统计 ========")
print(p["DA_pm"].describe().round(4))

print("\n======== 5.2 与 DA_mj Pearson 相关 ========")
cor_val = p[["DA_pm", "DA_mj"]].corr().iloc[0, 1]
print(f"Pearson = {cor_val:.4f}")

p["rank_pm"] = (
    p.groupby("fyear")["DA_pm"]
     .transform(lambda s: s.abs().rank(pct=True))
)
case = p.loc[p["company"].notna(),
             ["company", "fyear", "misstate", "DA_pm", "rank_pm"]]
print("\n======== 5.3 案例公司 PM-DA ========")
print(case.sort_values(["company", "fyear"]).to_string(index=False))
