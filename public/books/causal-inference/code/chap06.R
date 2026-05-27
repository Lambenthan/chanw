# Chapter 6: 双重稳健估计——AIPW 的两根保险绳
# 手动实现 AIPW + 倾向得分截断

library(tidyverse)
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

# ── 第一根绳：结果模型 ──────────────────────────────────
out_mod <- glm(death180_bin ~ rhc + .,
               data = d |> select(death180_bin, rhc, all_of(covs)),
               family = binomial)

# ── 第二根绳：处理模型 ──────────────────────────────────
ps_mod <- glm(rhc ~ .,
              data = d |> select(rhc, all_of(covs)),
              family = binomial)
d$ps <- predict(ps_mod, type = "response")

# ── 反事实预测 ───────────────────────────────────────────
d1 <- d0 <- d
d1$rhc <- 1; d0$rhc <- 0
d$m1 <- predict(out_mod, newdata = d1, type = "response")
d$m0 <- predict(out_mod, newdata = d0, type = "response")

# ── 组装 AIPW：三个部分逐项计算 ──────────────────────────
d$aipw_score <- with(d, {
  (m1 - m0) +                               # A: G 计算部分
    rhc / ps * (death180_bin - m1) -         # B: 处理组校正
    (1 - rhc) / (1 - ps) * (death180_bin - m0)  # C: 对照组校正
})

ate_aipw <- mean(d$aipw_score)
se_aipw  <- sd(d$aipw_score) / sqrt(nrow(d))
cat("ATE:", round(ate_aipw, 4),
    " SE:", round(se_aipw, 4),
    " 95% CI: [", round(ate_aipw - 1.96*se_aipw, 4),
    ",", round(ate_aipw + 1.96*se_aipw, 4), "]\n")

# ── 练习：倾向得分截断 ──────────────────────────────────
d$ps_trim <- pmax(0.025, pmin(0.975, d$ps))

d$aipw_trim <- with(d, {
  (m1 - m0) +
    rhc / ps_trim * (death180_bin - m1) -
    (1 - rhc) / (1 - ps_trim) * (death180_bin - m0)
})

ate_trim <- mean(d$aipw_trim)
se_trim  <- sd(d$aipw_trim) / sqrt(nrow(d))
cat("Trimmed ATE:", round(ate_trim, 4),
    " SE:", round(se_trim, 4), "\n")
