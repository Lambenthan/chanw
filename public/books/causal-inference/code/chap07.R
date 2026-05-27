# Chapter 7: 机器学习增强——Super Learner、DML 与 TMLE
# Super Learner + DoubleML + tmle

library(tidyverse)
library(SuperLearner)
library(DoubleML)
library(mlr3)
library(mlr3learners)
library(data.table)
library(tmle)
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

# ── Super Learner：结果模型 ──────────────────────────────
sl_out <- SuperLearner(
  Y = d$death180_bin,
  X = d |> select(rhc, all_of(covs)),
  family = binomial(),
  SL.library = c("SL.mean", "SL.glm", "SL.glmnet", "SL.ranger"),
  cvControl = list(V = 5)
)
sl_out

# ── DML：DoubleML 实现 ──────────────────────────────────
dt <- as.data.table(d |> select(death180_bin, rhc, all_of(covs)))

dml_data <- DoubleMLData$new(
  data = dt,
  y_col = "death180_bin",
  d_cols = "rhc",
  x_cols = covs
)

dml_irm <- DoubleMLIRM$new(
  data = dml_data,
  ml_g = lrn("classif.ranger", predict_type = "prob", num.trees = 500),
  ml_m = lrn("classif.ranger", predict_type = "prob", num.trees = 500),
  score = "ATE",
  n_folds = 5,
  n_rep = 3
)

dml_irm$fit()
dml_irm$summary()
print(dml_irm$confint())

# ── TMLE：tmle 实现 ─────────────────────────────────────
SL_lib <- c("SL.glm", "SL.glmnet", "SL.ranger", "SL.mean")

tmle_fit <- tmle(
  Y = d$death180_bin,
  A = d$rhc,
  W = d |> select(all_of(covs)),
  Q.SL.library = SL_lib,
  g.SL.library = SL_lib,
  family = "binomial"
)

tmle_fit
