# Chapter 9: 谁获益谁受害——因果森林与处理效应异质性
# grf 因果森林 + 变量重要性 + 亚组分析

library(tidyverse)
library(grf)
set.seed(2026)

# ── 读入数据 ──────────────────────────────────────────────
d <- read_csv(here::here("data", "rhc.csv"), show_col_types = FALSE) |>
  mutate(death180_bin = if_else(death180 == "Yes", 1L, 0L),
         sex_bin      = if_else(sex == "Male", 1L, 0L),
         cancer_bin   = if_else(cancer == "No", 0L, 1L))

covs <- c("age", "sex_bin", "cancer_bin", "cardiovascular",
          "congestive_hf", "dementia", "psychiatric", "pulmonary",
          "renal", "hepatic", "gi_bleed", "tumor",
          "immunosupperssion", "transfer_hx", "mi",
          "apache_score", "glasgow_coma_score", "blood_pressure",
          "heart_rate", "respiratory_rate", "temperature",
          "albumin", "creatinine", "bilirubin", "wbc",
          "hematocrit", "das_index", "weight")

X <- as.matrix(d[, covs])
W <- d$rhc
Y <- d$death180_bin

# ── 因果森林 ─────────────────────────────────────────────
# 2000 棵树，honesty = TRUE 保证统计推断合法
cf <- causal_forest(X, Y, W,
                    num.trees = 2000,
                    honesty = TRUE,
                    seed = 2026)

# 每名患者的 CATE 预测
cate <- predict(cf)$predictions
cat("CATE 均值:", round(mean(cate), 4),
    " SD:", round(sd(cate), 4), "\n")
cat("CATE > 0 (受害):", round(mean(cate > 0)*100, 1), "%\n")
cat("CATE < 0 (获益):", round(mean(cate < 0)*100, 1), "%\n")

# ── 变量重要性 ───────────────────────────────────────────
vimp <- variable_importance(cf)
vimp_df <- data.frame(Variable = covs,
                      Importance = as.numeric(vimp)) |>
  arrange(desc(Importance))
cat("Top 5 变量:\n")
print(head(vimp_df, 5))

# ── BLP 检验 ─────────────────────────────────────────────
blp <- test_calibration(cf)
print(blp)

# ── 因果森林的 AIPW 平均效应 ─────────────────────────────
ate_cf <- average_treatment_effect(cf, target.sample = "all")
cat("ATE:", round(ate_cf[1], 4),
    " SE:", round(ate_cf[2], 4),
    " 95% CI: [", round(ate_cf[1] - 1.96*ate_cf[2], 4),
    ",", round(ate_cf[1] + 1.96*ate_cf[2], 4), "]\n")

# ── 亚组分析：按 CATE 五等分 ─────────────────────────────
d$cate <- cate
d$cate_q <- cut(d$cate,
    breaks = quantile(d$cate, probs = seq(0, 1, 0.2)),
    labels = c("Q1", "Q2", "Q3", "Q4", "Q5"),
    include.lowest = TRUE)

for (q in c("Q1", "Q5")) {
  idx <- which(d$cate_q == q)
  ate_q <- average_treatment_effect(cf, subset = idx,
                                    target.sample = "all")
  cat(q, ": ATE =", round(ate_q[1], 4),
      ", 95% CI = [", round(ate_q[1] - 1.96*ate_q[2], 4),
      ",", round(ate_q[1] + 1.96*ate_q[2], 4), "]\n")
}
