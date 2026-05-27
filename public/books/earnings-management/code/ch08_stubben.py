# =====================================================
# code/ch08_stubben.py
# 第 8 章 Stubben (2010) 收入侧 DA 的 Python 实现
# =====================================================

import pandas as pd
import numpy as np

np.random.seed(2026)

p = pd.read_csv("data/em_panel.csv", low_memory=False)
p = p.dropna(subset=["dRect_s", "dSale_s"]).reset_index(drop=True)

da_stb = pd.Series(index=p.index, dtype=float)
year_r2 = {}
for yr, sub in p.groupby("fyear"):
    X = np.column_stack([np.ones(len(sub)), sub["dSale_s"].values])
    y = sub["dRect_s"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    da_stb.loc[sub.index] = resid
    ss_tot = np.sum((y - y.mean()) ** 2)
    year_r2[int(yr)] = 1 - np.sum(resid ** 2) / ss_tot if ss_tot > 0 else 0

p["DA_stb"] = da_stb

print("======== 8.1 Stubben 年度回归概况 ========")
print(f"回归年数：   {len(year_r2)}")
print(f"平均 R^2：   {pd.Series(year_r2).mean():.4f}")

print("\n======== 8.2 DA_stb 描述统计 ========")
print(p["DA_stb"].describe().round(4))

p["rank_stb"] = (
    p.groupby("fyear")["DA_stb"]
     .transform(lambda s: s.abs().rank(pct=True))
)
case = p.loc[p["company"].notna(),
             ["company", "fyear", "misstate", "DA_stb", "rank_stb"]]
print("\n======== 8.3 案例公司 DA_stb ========")
print(case.sort_values(["company", "fyear"]).to_string(index=False))
