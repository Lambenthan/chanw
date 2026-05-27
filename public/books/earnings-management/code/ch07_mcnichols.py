# =====================================================
# code/ch07_mcnichols.py
# 第 7 章 McNichols (2002) 改进 DD 的 Python 实现
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
                      "CFO_lead", "dSale_s",
                      "PPE_s"]).reset_index(drop=True)

print(f"McNichols 回归可用 firm-year: {len(p2)}")

X = sm.add_constant(p2[["CFO_lag", "CFO_s", "CFO_lead",
                        "dSale_s", "PPE_s"]])
fit = sm.OLS(p2["WC_accr"], X).fit()

print("\n======== 7.1 McNichols pooled 回归系数 ========")
print(fit.summary().tables[1])
print(f"R^2 = {fit.rsquared:.4f}")

p2["DA_mcn"] = fit.resid
print("\n======== 7.2 DA_mcn 描述统计 ========")
print(p2["DA_mcn"].describe().round(4))

p2["rank_mcn"] = (
    p2.groupby("fyear")["DA_mcn"]
      .transform(lambda s: s.abs().rank(pct=True))
)
case = p2.loc[p2["company"].notna(),
              ["company", "fyear", "misstate", "DA_mcn", "rank_mcn"]]
print("\n======== 7.3 案例公司 DA_mcn ========")
print(case.sort_values(["company", "fyear"]).to_string(index=False))
