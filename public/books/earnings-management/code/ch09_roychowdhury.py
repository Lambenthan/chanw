# =====================================================
# code/ch09_roychowdhury.py
# 第 9 章 Roychowdhury (2006) 真实活动 EM 的 Python 实现
# DISEXP 分量因 Bao 数据缺 xsga/xrd/xad 未实现
# =====================================================

import pandas as pd
import numpy as np

np.random.seed(2026)

p = pd.read_csv("data/em_panel.csv", low_memory=False)
p = p.sort_values(["gvkey", "fyear"]).reset_index(drop=True)
p["dSale_lag_s"] = p.groupby("gvkey")["dSale_s"].shift(1)


def by_year_resid(df, ycol, xcols):
    """对每个 fyear 子集跑 OLS 求残差，返回 (gvkey, fyear, resid) 三列。"""
    out = []
    for yr, sub in df.dropna(subset=[ycol] + xcols).groupby("fyear"):
        X = sub[xcols].values
        y = sub[ycol].values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        sub_resid = y - X @ beta
        out.append(pd.DataFrame({
            "gvkey": sub["gvkey"].values,
            "fyear": sub["fyear"].values,
            ycol + "_resid": sub_resid,
        }))
    return pd.concat(out, ignore_index=True)


cols_cfo = ["inv_lag_at", "Sale_s", "dSale_s"]
cols_prod = ["inv_lag_at", "Sale_s", "dSale_s", "dSale_lag_s"]

abn_cfo = by_year_resid(p, "CFO_s", cols_cfo).rename(
    columns={"CFO_s_resid": "abnCFO"})
abn_prod = by_year_resid(p, "PROD_s", cols_prod).rename(
    columns={"PROD_s_resid": "abnPROD"})

rm = abn_cfo.merge(abn_prod, on=["gvkey", "fyear"])
rm["RM_proxy"] = -rm["abnCFO"] + rm["abnPROD"]

print("======== 9.1 abnCFO / abnPROD / RM 描述统计 ========")
print(rm[["abnCFO", "abnPROD", "RM_proxy"]].describe().round(4))

base = p[["gvkey", "fyear", "company", "misstate"]].drop_duplicates()
rm2 = rm.merge(base, on=["gvkey", "fyear"])
rm2["rank_rm"] = (
    rm2.groupby("fyear")["RM_proxy"]
       .transform(lambda s: s.rank(pct=True))
)
case = rm2.loc[rm2["company"].notna(),
               ["company", "fyear", "misstate",
                "abnCFO", "abnPROD", "RM_proxy", "rank_rm"]]
print("\n======== 9.2 案例公司 RM_proxy ========")
print(case.sort_values(["company", "fyear"]).to_string(index=False))
