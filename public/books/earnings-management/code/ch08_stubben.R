# =====================================================
# code/ch08_stubben.R
# Stubben (2010) 收入侧 DA:
#   dRect_s = b0 + b1 * dSale_s + e
# 残差 = 可操纵营收（discretionary revenue）
# 按 fyear pooled
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(broom)
  library(here)
})

set.seed(2026)
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

stb_by_year <- p |>
  filter(!is.na(dRect_s), !is.na(dSale_s)) |>
  group_by(fyear) |>
  nest() |>
  mutate(
    fit = map(data, ~ lm(dRect_s ~ dSale_s, data = .x)),
    n   = map_int(data, nrow),
    r2  = map_dbl(fit, ~ summary(.x)$r.squared)
  )

cat("======== 8.1 Stubben 年度回归概况 ========\n")
cat(sprintf("回归年数:     %d\n", nrow(stb_by_year)))
cat(sprintf("平均样本量:   %.0f\n", mean(stb_by_year$n)))
cat(sprintf("平均 R^2:     %.4f\n", mean(stb_by_year$r2)))

stb_with_da <- stb_by_year |>
  mutate(data2 = map2(data, fit, ~ mutate(.x, DA_stb = resid(.y)))) |>
  select(fyear, data2) |>
  unnest(data2) |>
  ungroup()

cat("\n======== 8.2 DA_stb 描述统计 ========\n")
print(
  stb_with_da |> summarise(
    n        = n(),
    mean     = mean(DA_stb),
    median   = median(DA_stb),
    sd       = sd(DA_stb),
    abs_mean = mean(abs(DA_stb))
  ),
  digits = 4
)

case_rank <- stb_with_da |>
  group_by(fyear) |>
  mutate(rank_stb = percent_rank(abs(DA_stb))) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, DA_stb, rank_stb) |>
  arrange(company, fyear)

cat("\n======== 8.3 案例公司 DA_stb ========\n")
print(case_rank, n = Inf, width = Inf)

write_csv(case_rank, here::here("data", "ch08_case_ranks.csv"))
cat("\n案例公司打分已写出：data/ch08_case_ranks.csv\n")
