"""
code/02_mscore.py
第 2 章：Beneish M-Score（八变量规则基线，Python 等价实现）

公式：
    M = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI
        + 0.892*SGI + 0.115*DEPI - 0.172*SGAI
        + 4.679*TATA - 0.327*LVGI

Bao 28 变量集对 M-Score 的覆盖：
    - 缺失 xsga（销售管理费用），SGAI 项无法直接计算 -> 置为 1（中性值）
    - 缺失 oancf（经营现金流），TATA 项采用应计制近似：
      TATA ≈ (ib - 营运资本变动) / at
      其中营运资本变动 ≈ Δ(act - lct - che + dlc)
"""
import random

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, ndcg_score

random.seed(2026)
np.random.seed(2026)

# ---------- 1. 读数据 ----------
d = pd.read_csv("data/bao2020_full.csv")
print(f"[原始] firm-years = {len(d):,}")

# ---------- 2. 按 gvkey 取上一年 lag ----------
need_cols = ["rect", "sale", "cogs", "act", "ppegt", "at",
             "dp", "dlc", "dltt", "lct", "che", "ib"]

d = d.sort_values(["gvkey", "fyear"]).reset_index(drop=True)
g = d.groupby("gvkey", sort=False)
d["lag_fyear"] = g["fyear"].shift(1)
for c in need_cols:
    d[f"lag_{c}"] = g[c].shift(1)

d = d[d["lag_fyear"].notna() & (d["lag_fyear"] == d["fyear"] - 1)].copy()
print(f"[有连续上一年] firm-years = {len(d):,}")


# ---------- 3. 构造八个 Beneish 变量 ----------
def safe_div(num, den):
    out = num / den
    out = out.where(den.notna() & (den != 0) & num.notna(), np.nan)
    return out


d["DSRI"] = safe_div(d["rect"] / d["sale"],
                     d["lag_rect"] / d["lag_sale"])
d["GMI"]  = safe_div((d["lag_sale"] - d["lag_cogs"]) / d["lag_sale"],
                     (d["sale"] - d["cogs"]) / d["sale"])
d["AQI"]  = safe_div(1 - (d["act"] + d["ppegt"]) / d["at"],
                     1 - (d["lag_act"] + d["lag_ppegt"]) / d["lag_at"])
d["SGI"]  = safe_div(d["sale"], d["lag_sale"])
d["DEPI"] = safe_div(d["lag_dp"] / (d["lag_dp"] + d["lag_ppegt"]),
                     d["dp"] / (d["dp"] + d["ppegt"]))
d["SGAI"] = 1.0  # xsga 不在 Bao 28 变量集
d["LVGI"] = safe_div((d["dlc"] + d["dltt"]) / d["at"],
                     (d["lag_dlc"] + d["lag_dltt"]) / d["lag_at"])

wc_t   = d["act"]     - d["lct"]     - d["che"]     + d["dlc"]
wc_lag = d["lag_act"] - d["lag_lct"] - d["lag_che"] + d["lag_dlc"]
delta_wc = wc_t - wc_lag
d["TATA"] = safe_div(d["ib"] - delta_wc, d["at"])

# ---------- 4. M-Score ----------
d["mscore"] = (
    -4.84
    + 0.920 * d["DSRI"]
    + 0.528 * d["GMI"]
    + 0.404 * d["AQI"]
    + 0.892 * d["SGI"]
    + 0.115 * d["DEPI"]
    - 0.172 * d["SGAI"]
    + 4.679 * d["TATA"]
    - 0.327 * d["LVGI"]
)

before = len(d)
d_score = d[d["mscore"].notna() & np.isfinite(d["mscore"])].copy()
print(f"[可打分] firm-years = {len(d_score):,}")
print(f"[被丢弃] firm-years = {before - len(d_score):,}")

# 1% / 99% winsorize
lo, hi = d_score["mscore"].quantile([0.005, 0.995])
d_score["mscore"] = d_score["mscore"].clip(lo, hi)

# ---------- 5. 时间切分 ----------
test = d_score.query("2009 <= fyear <= 2014").copy()
print(f"[测试集] firm-years = {len(test):,}, "
      f"fraud = {int(test['misstate'].sum())}")

# ---------- 6. 测试集性能 ----------
y_true  = test["misstate"].astype(int).values
y_score = test["mscore"].values

auc_val = roc_auc_score(y_true, y_score)

n_test = len(test)
k_top  = int(np.ceil(n_test * 0.01))
top_idx = np.argsort(-y_score)[:k_top]
hits    = int(y_true[top_idx].sum())
recall_1pct    = hits / int(y_true.sum())
precision_1pct = hits / k_top

# NDCG@100：sklearn 的 ndcg_score 需要 (1, n) 形状
k_ndcg = 100
ndcg100 = ndcg_score(y_true.reshape(1, -1),
                     y_score.reshape(1, -1),
                     k=k_ndcg)

print("\n========== 测试集性能（M-Score） ==========")
print(f"AUC          = {auc_val:.4f}")
print(f"NDCG@100     = {ndcg100:.4f}")
print(f"Recall@1%    = {recall_1pct:.4f}  "
      f"(前 {k_top} 名命中 {hits} / {int(y_true.sum())})")
print(f"Precision@1% = {precision_1pct:.4f}")

# ---------- 7. 案例公司 ----------
print("\n========== 案例公司 ==========")
cases = d_score[((d_score["gvkey"] == 6127)  & (d_score["fyear"] == 2000)) |
                ((d_score["gvkey"] == 10787) & (d_score["fyear"] == 2000))]
print(cases[["gvkey", "fyear", "misstate", "mscore",
             "DSRI", "GMI", "SGI", "TATA", "LVGI"]]
      .to_string(index=False))

threshold = -2.22
flag_rate   = (test["mscore"] > threshold).mean()
flag_recall = (test.loc[test["misstate"] == 1, "mscore"] > threshold).mean()
print(f"\n[阈值 M > -2.22] 测试集 flag 率 = {100*flag_rate:.3f}%, "
      f"舞弊样本被 flag 的比例 = {100*flag_recall:.3f}%")
