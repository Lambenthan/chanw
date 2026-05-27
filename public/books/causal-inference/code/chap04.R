# Chapter 4: G 计算——构造反事实人群
# G 计算三步算法 + Bootstrap 置信区间

library(tidyverse)
set.seed(2026)

# ── 读入数据 ──────────────────────────────────────────────
d <- read_csv(here::here("data", "rhc.csv"), show_col_types = FALSE) |>
  mutate(death180_bin = if_else(death180 == "Yes", 1L, 0L),
         sex_bin      = if_else(sex == "Male", 1L, 0L))

# ── 建模：与第 3 章模型 4 相同的结局模型 ─────────────────
# G 计算的全部"因果推断负担"都压在这个模型上
outcome_mod <- glm(death180_bin ~ rhc + age + sex_bin +
  apache_score + glasgow_coma_score +
  cancer + cardiovascular + congestive_hf + dementia +
  pulmonary + renal + hepatic + blood_pressure +
  heart_rate + respiratory_rate + temperature +
  albumin + creatinine + bilirubin + wbc + hematocrit +
  das_index + dnr_status + medical_insurance + race +
  income + edu + transfer_hx + mi + gi_bleed +
  tumor + immunosupperssion + psychiatric,
  data = d, family = binomial)

# ── 预测反事实：构造两个"平行世界"的数据集 ──────────────
# 关键操作——只改处理变量，协变量保持每个人的真实值
d1 <- d |> mutate(rhc = 1L)   # 所有人接受 RHC
d0 <- d |> mutate(rhc = 0L)   # 所有人不接受 RHC

Y1 <- predict(outcome_mod, newdata = d1, type = "response")
Y0 <- predict(outcome_mod, newdata = d0, type = "response")

# ── 边际化：对全人群取算术平均 ───────────────────────────
EY1 <- mean(Y1)
EY0 <- mean(Y0)
RD  <- EY1 - EY0

cat("E[Y(1)] =", round(EY1, 4), "\n")
cat("E[Y(0)] =", round(EY0, 4), "\n")
cat("Risk Difference =", round(RD, 4), "\n")

# ── Bootstrap 置信区间 ───────────────────────────────────
# 重复整个 G 计算流程 1000 次
n_boot <- 1000
boot_rd <- numeric(n_boot)

for (i in seq_len(n_boot)) {
  idx <- sample(nrow(d), replace = TRUE)
  bd  <- d[idx, ]

  mod <- glm(death180_bin ~ rhc + age + sex_bin +
    apache_score + glasgow_coma_score +
    cancer + cardiovascular + congestive_hf + dementia +
    pulmonary + renal + hepatic + blood_pressure +
    heart_rate + respiratory_rate + temperature +
    albumin + creatinine + bilirubin + wbc + hematocrit +
    das_index + dnr_status + medical_insurance + race +
    income + edu + transfer_hx + mi + gi_bleed +
    tumor + immunosupperssion + psychiatric,
    data = bd, family = binomial)

  bd1 <- bd |> mutate(rhc = 1L)
  bd0 <- bd |> mutate(rhc = 0L)
  boot_rd[i] <- mean(predict(mod, bd1, "response")) -
                mean(predict(mod, bd0, "response"))
}

ci <- quantile(boot_rd, c(0.025, 0.975))
cat("Bootstrap 95% CI:", round(ci, 4), "\n")

# ── 练习：加入 RHC * APACHE 交互项 ──────────────────────
outcome_mod2 <- glm(death180_bin ~ rhc * apache_score +
  age + sex_bin + glasgow_coma_score +
  cancer + cardiovascular + congestive_hf + dementia +
  pulmonary + renal + hepatic + blood_pressure +
  heart_rate + respiratory_rate + temperature +
  albumin + creatinine + bilirubin + wbc + hematocrit +
  das_index + dnr_status + medical_insurance + race +
  income + edu + transfer_hx + mi + gi_bleed +
  tumor + immunosupperssion + psychiatric,
  data = d, family = binomial)

d1 <- d |> mutate(rhc = 1L)
d0 <- d |> mutate(rhc = 0L)
RD2 <- mean(predict(outcome_mod2, d1, "response")) -
       mean(predict(outcome_mod2, d0, "response"))

cat("RD (no interaction):", round(RD, 4), "\n")
cat("RD (with interaction):", round(RD2, 4), "\n")
cat("Change:", round((RD2 - RD) / RD * 100, 1), "%\n")
