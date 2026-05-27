# =====================================================
# code/ch06_dechow_dichev.py
# 第 6 章 Dechow-Dichev (2002) 应计质量 的 Python 实现
# =====================================================

import pandas as pd
import numpy as np
import statsmodels.api as sm

np.random.seed(2026)

p = pd.read_csv("data/em_panel.csv", low_memory=False)
p = p.sort_values(["gvkey", "fyear"]).reset_index(drop=True)
p["CFO_lag"] = p.groupby("gvkey")["CFO_s"].shift(1)
p["CFO_lead"] = p.groupby("gvkey")["CFO_s"].shift(-1)
p2 = p.dropna(subset=["WC_accr", "CFO_lag", "CFO_s",
                      "CFO_lead"]).reset_index(drop=True)

print(f"DD 回归可用 firm-year 数: {len(p2)}")

X = sm.add_constant(p2[["CFO_lag", "CFO_s", "CFO_lead"]])
fit = sm.OLS(p2["WC_accr"], X).fit()

print("\n======== 6.1 DD pooled 回归系数 ========")
print(fit.summary().tables[1])
print(f"R^2 = {fit.rsquared:.4f}")

p2["resid_dd"] = fit.resid

aq = (
    p2.groupby("gvkey")
      .filter(lambda d: len(d) >= 5)
      .groupby("gvkey")
      .agg(n=("resid_dd", "size"),
           AQ_dd=("resid_dd", "std"),
           mean_resid=("resid_dd", "mean"))
      .reset_index()
)

print(f"\n应计质量 AQ_dd 公司数（至少 5 年）: {len(aq)}")
print("\n======== 6.2 AQ_dd 描述统计 ========")
print(aq["AQ_dd"].describe().round(4))

# 案例公司
company_map = (p2[["gvkey", "company"]].dropna(subset=["company"])
               .drop_duplicates())
aq["rank_aq"] = aq["AQ_dd"].rank(pct=True)
aq_case = aq.merge(company_map, on="gvkey")
print("\n======== 6.3 案例公司 AQ_dd ========")
print(aq_case.to_string(index=False))
