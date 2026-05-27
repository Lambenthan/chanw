# Chapter 3: 回归调整——因果估计的第一刀
# 逐步加变量的逻辑回归，观察 RHC 系数漂移

library(tidyverse)
library(broom)
set.seed(2026)

# ── 读入数据 ──────────────────────────────────────────────
d <- read_csv(here::here("data", "rhc.csv"), show_col_types = FALSE) |>
  mutate(death180_bin = if_else(death180 == "Yes", 1L, 0L),
         sex_bin      = if_else(sex == "Male", 1L, 0L))

# ── 四个嵌套模型 ─────────────────────────────────────────

# 模型 1：粗模型，只看 RHC 与死亡的边际关联
m1 <- glm(death180_bin ~ rhc, data = d, family = binomial)

# 模型 2：加入人口学——年龄和性别本身是混杂还是精度变量？
m2 <- glm(death180_bin ~ rhc + age + sex_bin,
          data = d, family = binomial)

# 模型 3：加入疾病严重度——APACHE 和 GCS 是最强的混杂源
m3 <- glm(death180_bin ~ rhc + age + sex_bin +
            apache_score + glasgow_coma_score,
          data = d, family = binomial)

# 模型 4：加入合并症和全部生理指标
m4 <- glm(death180_bin ~ rhc + age + sex_bin +
            apache_score + glasgow_coma_score +
            cancer + cardiovascular + congestive_hf + dementia +
            pulmonary + renal + hepatic + blood_pressure +
            heart_rate + respiratory_rate + temperature +
            albumin + creatinine + bilirubin + wbc + hematocrit +
            das_index + dnr_status + medical_insurance + race +
            income + edu + transfer_hx + mi + gi_bleed +
            tumor + immunosupperssion + psychiatric,
          data = d, family = binomial)

# ── 提取四个模型中 RHC 的 OR 和 95% CI ──────────────────
bind_rows(
  tidy(m1, conf.int = TRUE, exponentiate = TRUE) |>
    filter(term == "rhc") |> mutate(model = "Model 1"),
  tidy(m2, conf.int = TRUE, exponentiate = TRUE) |>
    filter(term == "rhc") |> mutate(model = "Model 2"),
  tidy(m3, conf.int = TRUE, exponentiate = TRUE) |>
    filter(term == "rhc") |> mutate(model = "Model 3"),
  tidy(m4, conf.int = TRUE, exponentiate = TRUE) |>
    filter(term == "rhc") |> mutate(model = "Model 4")
) |> select(model, estimate, conf.low, conf.high)

# ── 练习：APACHE 二次项 ─────────────────────────────────
m3b <- glm(death180_bin ~ rhc + age + sex_bin +
             apache_score + I(apache_score^2) +
             glasgow_coma_score,
           data = d, family = binomial)

cat("Model 3  OR:", exp(coef(m3)["rhc"]), "\n")
cat("Model 3b OR:", exp(coef(m3b)["rhc"]), "\n")
cat("AIC  M3:", AIC(m3), " M3b:", AIC(m3b), "\n")
