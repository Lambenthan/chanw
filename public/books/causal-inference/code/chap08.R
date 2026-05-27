# Chapter 8: 结果稳不稳——敏感性分析与未测量混杂
# E-value + sensemakr

library(tidyverse)
library(EValue)
library(sensemakr)
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

# ── E-value ──────────────────────────────────────────────
r0 <- mean(d$death180_bin[d$rhc == 0])

# AIPW 估计的风险差和 95% CI（来自第 6 章）
ate  <- 0.0442
se   <- 0.0139
ci_lo <- ate - 1.96 * se
ci_hi <- ate + 1.96 * se

# 转换为相对风险尺度
rr_point <- (r0 + ate) / r0
rr_lo    <- (r0 + ci_lo) / r0
rr_hi    <- (r0 + ci_hi) / r0

ev <- evalues.RR(rr_point, lo = rr_lo, hi = rr_hi)
print(ev)

# ── sensemakr ────────────────────────────────────────────
# 线性概率模型——sensemakr 需要 lm 对象
lin_mod <- lm(death180_bin ~ rhc + .,
              data = d |> select(death180_bin, rhc, all_of(covs)))

# 以 APACHE 评分为基准，分别看 1 倍、2 倍、3 倍强度的混杂
sens <- sensemakr(model = lin_mod,
                  treatment = "rhc",
                  benchmark_covariates = "apache_score",
                  kd = c(1, 2, 3))
summary(sens)

# ── 练习：IPW 的 E-value ─────────────────────────────────
ate_ipw <- 0.032; se_ipw <- 0.022

rr_ipw <- (r0 + ate_ipw) / r0
rr_lo  <- (r0 + ate_ipw - 1.96 * se_ipw) / r0

ev_ipw <- evalues.RR(rr_ipw, lo = rr_lo)
print(ev_ipw)
