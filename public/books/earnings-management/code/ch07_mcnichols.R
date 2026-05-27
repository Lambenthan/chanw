# =====================================================
# code/ch07_mcnichols.R
# McNichols (2002) 改进的 DD:
#   WC_accr = b0 + b1*CFO_{t-1} + b2*CFO_t + b3*CFO_{t+1}
#                + b4*dSale_s + b5*PPE_s + e
# DA = |e|，按 firm-year
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(broom)
  library(here)
})

set.seed(2026)
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

p2 <- p |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(
    CFO_lag  = lag(CFO_s),
    CFO_lead = lead(CFO_s)
  ) |>
  ungroup() |>
  filter(!is.na(WC_accr), !is.na(CFO_lag), !is.na(CFO_s),
         !is.na(CFO_lead), !is.na(dSale_s), !is.na(PPE_s))

cat(sprintf("McNichols 回归可用 firm-year: %d\n", nrow(p2)))

fit <- lm(WC_accr ~ CFO_lag + CFO_s + CFO_lead + dSale_s + PPE_s,
          data = p2)
cat("\n======== 7.1 McNichols pooled 回归系数 ========\n")
print(tidy(fit), digits = 4)
cat(sprintf("R^2 = %.4f\n", summary(fit)$r.squared))

p2$DA_mcn <- residuals(fit)

cat("\n======== 7.2 DA_mcn 描述统计 ========\n")
print(
  p2 |> summarise(
    n        = n(),
    mean     = mean(DA_mcn),
    median   = median(DA_mcn),
    sd       = sd(DA_mcn),
    abs_mean = mean(abs(DA_mcn))
  ),
  digits = 4
)

case_rank <- p2 |>
  group_by(fyear) |>
  mutate(rank_mcn = percent_rank(abs(DA_mcn))) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, DA_mcn, rank_mcn) |>
  arrange(company, fyear)

cat("\n======== 7.3 案例公司 DA_mcn ========\n")
print(case_rank, n = Inf, width = Inf)

write_csv(case_rank, here::here("data", "ch07_case_ranks.csv"))
cat("\n案例公司打分已写出：data/ch07_case_ranks.csv\n")
