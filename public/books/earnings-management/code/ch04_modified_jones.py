# =====================================================
# code/ch04_modified_jones.py
# 第 4 章 Modified Jones (1995) 的 Python 实现
# =====================================================

import pandas as pd
import numpy as np

np.random.seed(2026)

p = pd.read_csv("data/em_panel.csv", low_memory=False)
p["dSaleRect_s"] = p["dSale_s"] - p["dRect_s"]
p = p.dropna(subset=["TA", "dSaleRect_s", "PPE_s",
                      "inv_lag_at"]).reset_index(drop=True)

da_mj = pd.Series(index=p.index, dtype=float)
year_r2 = {}
for yr, sub in p.groupby("fyear"):
    X = sub[["inv_lag_at", "dSaleRect_s", "PPE_s"]].values
    y = sub["TA"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    da_mj.loc[sub.index] = resid
    year_r2[int(yr)] = 1 - np.sum(resid ** 2) / np.sum(y ** 2)

p["DA_mj"] = da_mj

print("======== 4.1 Modified Jones 年度回归概况 ========")
print(f"回归年数：   {len(year_r2)}")
print(f"平均 R^2：   {pd.Series(year_r2).mean():.4f}")

print("\n======== 4.2 DA_mj 描述统计 ========")
print(p["DA_mj"].describe().round(4))

# 与原 Jones 对比
da_jones = pd.Series(index=p.index, dtype=float)
for yr, sub in p.groupby("fyear"):
    if sub["dSale_s"].isna().any():
        continue
    X = sub[["inv_lag_at", "dSale_s", "PPE_s"]].values
    y = sub["TA"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    da_jones.loc[sub.index] = y - X @ beta
p["DA_jones"] = da_jones

print(f"\nPearson(DA_mj, DA_jones) = "
      f"{p[['DA_mj', 'DA_jones']].corr().iloc[0, 1]:.4f}")

p["rank_mj"] = (
    p.groupby("fyear")["DA_mj"]
     .transform(lambda s: s.abs().rank(pct=True))
)
case = p.loc[p["company"].notna(),
             ["company", "fyear", "misstate", "DA_mj", "rank_mj"]]
print("\n======== 4.3 案例公司 DA_mj ========")
print(case.sort_values(["company", "fyear"]).to_string(index=False))
