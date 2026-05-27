# =====================================================
# code/ch04_modified_jones.R
# Modified Jones (Dechow, Sloan, Sweeney 1995):
#   TA_it = a0 * (1/lag_at) + a1 * (dSale - dRect)_s + a2 * PPE_s + e
# 与 Jones 区别在于把营收变化扣掉应收变化，假设应收变动属可操纵部分
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
p <- p |> mutate(dSaleRect_s = dSale_s - dRect_s)

mj_by_year <- p |>
  filter(!is.na(TA), !is.na(dSaleRect_s), !is.na(PPE_s)) |>
  group_by(fyear) |>
  nest() |>
  mutate(
    fit = map(data, ~ lm(TA ~ 0 + inv_lag_at + dSaleRect_s + PPE_s,
                         data = .x)),
    n   = map_int(data, nrow),
    r2  = map_dbl(fit, ~ summary(.x)$r.squared)
  )

cat("======== 4.1 Modified Jones 年度回归概况 ========\n")
cat(sprintf("回归年数:       %d\n", nrow(mj_by_year)))
cat(sprintf("平均样本量:     %.0f\n", mean(mj_by_year$n)))
cat(sprintf("平均 R^2:       %.4f\n", mean(mj_by_year$r2)))

mj_with_da <- mj_by_year |>
  mutate(data2 = map2(data, fit, ~ mutate(.x, DA_mj = resid(.y)))) |>
  select(fyear, data2) |>
  unnest(data2) |>
  ungroup()

cat("\n======== 4.2 DA_mj 描述统计 ========\n")
da_stats <- mj_with_da |>
  summarise(
    n        = n(),
    mean     = mean(DA_mj),
    median   = median(DA_mj),
    sd       = sd(DA_mj),
    abs_mean = mean(abs(DA_mj))
  )
print(da_stats, digits = 4)

# 与原 Jones 的相关
jones_da <- read_csv(here::here("data", "ch03_case_ranks.csv"),
                     show_col_types = FALSE)

case_rank <- mj_with_da |>
  group_by(fyear) |>
  mutate(rank_mj = percent_rank(abs(DA_mj))) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, DA_mj, rank_mj) |>
  arrange(company, fyear)

cat("\n======== 4.3 案例公司 DA_mj ========\n")
print(case_rank, n = Inf, width = Inf)

write_csv(case_rank, here::here("data", "ch04_case_ranks.csv"))
cat("\n案例公司打分已写出：data/ch04_case_ranks.csv\n")
