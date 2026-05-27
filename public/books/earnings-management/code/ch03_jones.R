# =====================================================
# code/ch03_jones.R
# Jones (1991): 按 fyear pooled OLS（因 Bao 数据无 sich）
#   TA_it = a0 * (1/lag_at) + a1 * dSale_s + a2 * PPE_s + e
# DA_it = e_it
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(broom)
  library(here)
  library(ragg)
})

set.seed(2026)
source(here::here("code", "_theme.R"))
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

# 按 fyear 分组跑 Jones 回归
jones_by_year <- p |>
  filter(!is.na(TA), !is.na(dSale_s), !is.na(PPE_s)) |>
  group_by(fyear) |>
  nest() |>
  mutate(
    fit = map(data, ~ lm(TA ~ 0 + inv_lag_at + dSale_s + PPE_s,
                         data = .x)),
    n   = map_int(data, nrow),
    r2  = map_dbl(fit, ~ summary(.x)$r.squared)
  )

cat("======== 3.1 Jones 年度回归概况 ========\n")
cat(sprintf("回归年数:       %d\n", nrow(jones_by_year)))
cat(sprintf("平均样本量:     %.0f\n", mean(jones_by_year$n)))
cat(sprintf("平均 R^2:       %.4f\n", mean(jones_by_year$r2)))
cat(sprintf("R^2 中位:       %.4f\n", median(jones_by_year$r2)))

# 把残差合回原数据
jones_with_da <- jones_by_year |>
  mutate(data2 = map2(data, fit, ~ mutate(.x, DA_jones = resid(.y)))) |>
  select(fyear, data2) |>
  unnest(data2) |>
  ungroup()

cat("\n======== 3.2 DA_jones 描述统计 ========\n")
da_stats <- jones_with_da |>
  summarise(
    n      = n(),
    mean   = mean(DA_jones),
    median = median(DA_jones),
    sd     = sd(DA_jones),
    p10    = quantile(DA_jones, 0.10),
    p90    = quantile(DA_jones, 0.90),
    abs_mean = mean(abs(DA_jones))
  )
print(da_stats, digits = 4)

# 案例公司
cat("\n======== 3.3 案例公司 DA_jones ========\n")
case_rank <- jones_with_da |>
  group_by(fyear) |>
  mutate(rank_jones = percent_rank(abs(DA_jones))) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, DA_jones, rank_jones) |>
  arrange(company, fyear)
print(case_rank, n = Inf, width = Inf)

write_csv(case_rank, here::here("data", "ch03_case_ranks.csv"))
cat("\n案例公司打分已写出：data/ch03_case_ranks.csv\n")
