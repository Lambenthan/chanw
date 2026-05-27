# =====================================================
# code/ch01_overview.py
# 第 1 章 R 实现的 Python 等价版本
# =====================================================

import random
import numpy as np
import pandas as pd

np.random.seed(2026)
random.seed(2026)

p = pd.read_csv("data/em_panel.csv")

print("======== 1.1 样本规模 ========")
print(f"firm-year 总数： {len(p):,}")
print(f"公司数：         {p['gvkey'].nunique():,}")
print(f"时间跨度：       {int(p.fyear.min())}-{int(p.fyear.max())}")
mis = int((p['misstate'] == 1).sum())
print(f"AAER firm-year： {mis} ({mis / len(p) * 100:.2f}%)")
print(f"AAER 公司数：    {p.loc[p['misstate'] == 1, 'gvkey'].nunique()}")

print("\n======== 1.2 年份分布（前后 5 年）========")
yr = p.groupby("fyear").size().rename("n")
print(pd.concat([yr.head(5), yr.tail(5)]))
print(f"年均 firm-year： {yr.mean():.0f}")

print("\n======== 1.3 总应计 TA 描述统计 ========")
ta = p["TA"]
ta_stats = pd.Series({
    "mean":   ta.mean(),
    "median": ta.median(),
    "sd":     ta.std(),
    "q1":     ta.quantile(0.25),
    "q3":     ta.quantile(0.75),
    "p10":    ta.quantile(0.10),
    "p90":    ta.quantile(0.90),
})
print(ta_stats.round(4))

print("\n======== 1.4 案例公司切片 ========")
case = (
    p.loc[p["company"].notna(),
          ["company", "fyear", "at", "sale", "ib",
           "TA", "ROA", "misstate"]]
    .sort_values(["company", "fyear"])
)
print(case.to_string(index=False))
