# =====================================================
# code/ch02_healy_deangelo.py
# 第 2 章 R 实现的 Python 等价版本
# =====================================================

import random
import numpy as np
import pandas as pd

np.random.seed(2026)
random.seed(2026)

p = pd.read_csv("data/em_panel.csv")

# ---------- Healy: 同年度均值差 ----------
p["TA_year_mean"] = p.groupby("fyear")["TA"].transform("mean")
p["DA_healy"] = p["TA"] - p["TA_year_mean"]

# ---------- DeAngelo: 上一年 TA 差 ----------
p = p.sort_values(["gvkey", "fyear"])
p["lag_TA"] = p.groupby("gvkey")["TA"].shift(1)
p["DA_deangelo"] = p["TA"] - p["lag_TA"]


def stats(x):
    return pd.Series({
        "n":        x.notna().sum(),
        "mean":     x.mean(),
        "median":   x.median(),
        "sd":       x.std(),
        "p10":      x.quantile(0.10),
        "p90":      x.quantile(0.90),
        "abs_mean": x.abs().mean(),
    })


print("======== 2.1 Healy DA 描述统计 ========")
print(stats(p["DA_healy"]).round(4))

print("\n======== 2.2 DeAngelo DA 描述统计 ========")
print(stats(p["DA_deangelo"].dropna()).round(4))

print("\n======== 2.3 两种方法相关 ========")
sub = p.dropna(subset=["DA_healy", "DA_deangelo"])
pe = sub[["DA_healy", "DA_deangelo"]].corr().iloc[0, 1]
sp = sub[["DA_healy", "DA_deangelo"]].corr(method="spearman").iloc[0, 1]
print(f"Pearson  = {pe:.4f}")
print(f"Spearman = {sp:.4f}")

print("\n======== 2.4 案例公司 DA ========")
p["rank_healy"] = (
    p.dropna(subset=["DA_healy"])
     .groupby("fyear")["DA_healy"]
     .transform(lambda s: s.abs().rank(pct=True))
)
p["rank_deangelo"] = (
    p.dropna(subset=["DA_deangelo"])
     .groupby("fyear")["DA_deangelo"]
     .transform(lambda s: s.abs().rank(pct=True))
)
case = (
    p.loc[p["company"].notna(),
          ["company", "fyear", "misstate",
           "DA_healy", "rank_healy",
           "DA_deangelo", "rank_deangelo"]]
    .sort_values(["company", "fyear"])
)
print(case.to_string(index=False))
