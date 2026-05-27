# =====================================================
# code/ch09_roychowdhury.R
# Roychowdhury (2006) 真实活动 EM:
#   异常 CFO:   CFO_s = b0*(1/lag_at) + b1*Sale_s + b2*dSale_s + e1
#   异常 PROD:  PROD_s = b0*(1/lag_at) + b1*Sale_s + b2*dSale_s + b3*dSale_lag_s + e2
#   PROD = COGS + ΔINV，缩放到 lag_at
# DISEXP 因 Bao 数据缺 xsga/xrd/xad，本书暂不实现，正文说明该限制
# 真实活动 EM 综合: RM = -abnCFO - abnPROD（数值大表示更可能压低费用、推高产出）
# 注: Roychowdhury 原文 abnPROD 是正向操纵信号（多生产以摊低单位 COGS）
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(broom)
  library(here)
})

set.seed(2026)
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

p <- p |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(dSale_lag_s = lag(dSale_s)) |>
  ungroup()

# 异常 CFO
cfo_by_year <- p |>
  filter(!is.na(CFO_s), !is.na(Sale_s), !is.na(dSale_s)) |>
  group_by(fyear) |>
  nest() |>
  mutate(
    fit = map(data, ~ lm(CFO_s ~ 0 + inv_lag_at + Sale_s + dSale_s,
                         data = .x)),
    n   = map_int(data, nrow),
    r2  = map_dbl(fit, ~ summary(.x)$r.squared)
  )

# 异常 PROD
prod_by_year <- p |>
  filter(!is.na(PROD_s), !is.na(Sale_s), !is.na(dSale_s), !is.na(dSale_lag_s)) |>
  group_by(fyear) |>
  nest() |>
  mutate(
    fit = map(data, ~ lm(PROD_s ~ 0 + inv_lag_at + Sale_s + dSale_s + dSale_lag_s,
                         data = .x)),
    n   = map_int(data, nrow),
    r2  = map_dbl(fit, ~ summary(.x)$r.squared)
  )

cat("======== 9.1 异常 CFO 回归概况 ========\n")
cat(sprintf("年数 %d / 平均样本 %.0f / 平均 R^2 %.4f\n",
            nrow(cfo_by_year), mean(cfo_by_year$n), mean(cfo_by_year$r2)))

cat("\n======== 9.2 异常 PROD 回归概况 ========\n")
cat(sprintf("年数 %d / 平均样本 %.0f / 平均 R^2 %.4f\n",
            nrow(prod_by_year), mean(prod_by_year$n), mean(prod_by_year$r2)))

cfo_with_da <- cfo_by_year |>
  mutate(data2 = map2(data, fit, ~ mutate(.x, abnCFO = resid(.y)))) |>
  select(fyear, data2) |>
  unnest(data2) |>
  ungroup() |>
  select(gvkey, fyear, abnCFO)

prod_with_da <- prod_by_year |>
  mutate(data2 = map2(data, fit, ~ mutate(.x, abnPROD = resid(.y)))) |>
  select(fyear, data2) |>
  unnest(data2) |>
  ungroup() |>
  select(gvkey, fyear, abnPROD)

rm_panel <- p |>
  select(gvkey, fyear, company, misstate) |>
  left_join(cfo_with_da, by = c("gvkey", "fyear")) |>
  left_join(prod_with_da, by = c("gvkey", "fyear")) |>
  mutate(RM_proxy = -abnCFO + abnPROD)   # 推高产出 + 推高 CFO

cat("\n======== 9.3 abnCFO 与 abnPROD 描述统计 ========\n")
print(
  rm_panel |>
    summarise(
      abnCFO_mean  = mean(abnCFO, na.rm = TRUE),
      abnCFO_sd    = sd(abnCFO, na.rm = TRUE),
      abnPROD_mean = mean(abnPROD, na.rm = TRUE),
      abnPROD_sd   = sd(abnPROD, na.rm = TRUE),
      RM_mean      = mean(RM_proxy, na.rm = TRUE),
      RM_sd        = sd(RM_proxy, na.rm = TRUE)
    ),
  digits = 4
)

case_rank <- rm_panel |>
  filter(!is.na(RM_proxy)) |>
  group_by(fyear) |>
  mutate(rank_rm = percent_rank(RM_proxy)) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, abnCFO, abnPROD, RM_proxy, rank_rm) |>
  arrange(company, fyear)

cat("\n======== 9.4 案例公司 RM_proxy ========\n")
print(case_rank, n = Inf, width = Inf)

write_csv(case_rank, here::here("data", "ch09_case_ranks.csv"))
cat("\n案例公司打分已写出：data/ch09_case_ranks.csv\n")
