# =====================================================
# code/ch05_performance_matched.R
# Performance-Matched DA (Kothari, Leone, Wasley 2005):
#   先用 Modified Jones 估出每家公司 DA_mj，
#   然后对每个 firm-year，按 ROA 在同 fyear 内找最接近的对照公司，
#   PM-DA = DA_mj(firm) - DA_mj(matched control firm)
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
})

set.seed(2026)
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()
p <- p |> mutate(dSaleRect_s = dSale_s - dRect_s)

# 复用 Modified Jones 残差
mj <- p |>
  filter(!is.na(TA), !is.na(dSaleRect_s), !is.na(PPE_s), !is.na(ROA)) |>
  group_by(fyear) |>
  nest() |>
  mutate(
    fit = map(data, ~ lm(TA ~ 0 + inv_lag_at + dSaleRect_s + PPE_s,
                         data = .x))
  ) |>
  mutate(data2 = map2(data, fit, ~ mutate(.x, DA_mj = resid(.y)))) |>
  select(fyear, data2) |>
  unnest(data2) |>
  ungroup()

# 同 fyear 内按 ROA 最近邻配对
match_pm <- function(df) {
  df <- df |> arrange(ROA)
  n <- nrow(df)
  if (n < 2) return(df |> mutate(DA_pm = NA_real_))
  # 找每行最近邻（不同 gvkey）：用 sort 后的左右邻居比较
  out <- df |> mutate(
    left_DA  = lag(DA_mj),
    right_DA = lead(DA_mj),
    left_d   = abs(lag(ROA)  - ROA),
    right_d  = abs(lead(ROA) - ROA),
    near_DA  = if_else(
      is.na(right_d) | (!is.na(left_d) & left_d <= right_d),
      left_DA, right_DA
    ),
    DA_pm    = DA_mj - near_DA
  ) |> select(-left_DA, -right_DA, -left_d, -right_d, -near_DA)
  out
}

pm <- mj |>
  group_by(fyear) |>
  group_modify(~ match_pm(.x)) |>
  ungroup()

cat("======== 5.1 PM-DA 描述统计 ========\n")
print(
  pm |> filter(!is.na(DA_pm)) |>
    summarise(
      n        = n(),
      mean     = mean(DA_pm),
      median   = median(DA_pm),
      sd       = sd(DA_pm),
      abs_mean = mean(abs(DA_pm))
    ),
  digits = 4
)

cat("\n======== 5.2 PM-DA 与 DA_mj 的 Pearson 相关 ========\n")
cor_val <- cor(pm$DA_pm, pm$DA_mj, use = "pairwise.complete.obs")
cat(sprintf("Pearson = %.4f\n", cor_val))

case_rank <- pm |>
  filter(!is.na(DA_pm)) |>
  group_by(fyear) |>
  mutate(rank_pm = percent_rank(abs(DA_pm))) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, DA_pm, rank_pm) |>
  arrange(company, fyear)

cat("\n======== 5.3 案例公司 PM-DA ========\n")
print(case_rank, n = Inf, width = Inf)

write_csv(case_rank, here::here("data", "ch05_case_ranks.csv"))
cat("\n案例公司打分已写出：data/ch05_case_ranks.csv\n")
