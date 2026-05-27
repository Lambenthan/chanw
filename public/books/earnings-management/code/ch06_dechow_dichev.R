# =====================================================
# code/ch06_dechow_dichev.R
# Dechow-Dichev (2002) 应计质量:
#   WC_accruals = b0 + b1 * CFO_{t-1} + b2 * CFO_t + b3 * CFO_{t+1} + e
# 应计质量 = sd(e) by firm（5-year rolling 或 by firm）
# 这里用 by firm 残差标准差（要求该公司至少 5 个年份）
#
# 营运资金应计 WC_accr ≈ ΔCA - ΔCash - (ΔCL - ΔSTD) - DEP 不含的
# 这里采用：WC_accr = dCA - dCash - dCL + dSTD - dTP（即 TA + DEP）
# 缩放到 lag_at
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(broom)
  library(here)
})

set.seed(2026)
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

# WC_accr 已在 load_data.R 中预算并 winsorize
p2 <- p |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(
    CFO_lag  = lag(CFO_s),
    CFO_lead = lead(CFO_s)
  ) |>
  ungroup() |>
  filter(!is.na(WC_accr), !is.na(CFO_lag), !is.na(CFO_s), !is.na(CFO_lead))

cat(sprintf("DD 回归可用 firm-year 数: %d\n", nrow(p2)))

# pooled 回归然后用残差 sd by firm
fit <- lm(WC_accr ~ CFO_lag + CFO_s + CFO_lead, data = p2)
cat("\n======== 6.1 DD pooled 回归系数 ========\n")
print(tidy(fit), digits = 4)
cat(sprintf("R^2 = %.4f\n", summary(fit)$r.squared))

p2$resid_dd <- residuals(fit)

# 每家公司 5 年以上残差 sd
quality_by_firm <- p2 |>
  group_by(gvkey) |>
  filter(n() >= 5) |>
  summarise(
    n           = n(),
    AQ_dd       = sd(resid_dd),
    mean_resid  = mean(resid_dd),
    .groups     = "drop"
  )

cat(sprintf("\n应计质量 AQ_dd 公司数（至少 5 年）: %d\n", nrow(quality_by_firm)))
cat("\n======== 6.2 AQ_dd 描述统计（越大质量越差，越像被操纵）========\n")
print(
  quality_by_firm |>
    summarise(
      mean   = mean(AQ_dd),
      median = median(AQ_dd),
      sd     = sd(AQ_dd),
      p10    = quantile(AQ_dd, 0.10),
      p90    = quantile(AQ_dd, 0.90)
    ),
  digits = 4
)

# 案例公司
case_rank <- quality_by_firm |>
  left_join(
    p |> select(gvkey, company) |> distinct(),
    by = "gvkey"
  ) |>
  mutate(rank_aq = percent_rank(AQ_dd)) |>
  filter(!is.na(company))
cat("\n======== 6.3 案例公司 AQ_dd ========\n")
print(case_rank, n = Inf, width = Inf)

# 同时保留 firm-year 级残差（chap10 使用）
firm_year_out <- p2 |>
  select(gvkey, fyear, company, misstate, resid_dd) |>
  group_by(fyear) |>
  mutate(rank_dd = percent_rank(abs(resid_dd))) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, DA_dd = resid_dd, rank_dd) |>
  arrange(company, fyear)

write_csv(firm_year_out, here::here("data", "ch06_case_ranks.csv"))
cat("\n案例公司 firm-year 打分已写出：data/ch06_case_ranks.csv\n")
