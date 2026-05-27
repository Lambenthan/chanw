"""
code/01_data_overview.py
第 1 章：数据概览与零模型基线（Python 等价实现）
"""
import random
import numpy as np
import pandas as pd

random.seed(2026)
np.random.seed(2026)

d = pd.read_csv("data/bao2020_full.csv")

print(f"全样本: {len(d):,} firm-years, "
      f"{d['gvkey'].nunique():,} 公司, "
      f"fyear {int(d['fyear'].min())}-{int(d['fyear'].max())}")
print(f"misstate=1: {int(d['misstate'].sum())} "
      f"({100 * d['misstate'].mean():.4f}%)")

splits = {
    "train": d.query("1991 <= fyear <= 2002"),
    "valid": d.query("2003 <= fyear <= 2008"),
    "test":  d.query("2009 <= fyear <= 2014"),
}
for name, s in splits.items():
    print(f"{name}: n={len(s):,}, fraud={int(s['misstate'].sum())}, "
          f"rate={100 * s['misstate'].mean():.3f}%")

print("\n--- Enron (gvkey=6127) ---")
print(d.query("gvkey == 6127")
      .sort_values("fyear")[["fyear", "misstate", "p_aaer",
                              "at", "sale", "ni"]]
      .to_string(index=False))

test = splits["test"]
print(f"\n零模型: AUC=0.500, Recall@1%=0, Precision@1%=0")
print(f"测试集 n={len(test):,}, 阳性={int(test['misstate'].sum())}, "
      f"1% 名额={int(np.ceil(len(test) * 0.01))}")
