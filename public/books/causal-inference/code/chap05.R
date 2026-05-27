## ============================================================
## Chapter 05: 倾向得分——匹配、加权与平衡诊断
## 完整脚本：PS 估计 + PSM + IPW + OW + 平衡诊断 + 图
## ============================================================

library(tidyverse)
library(MatchIt)
library(WeightIt)
library(cobalt)
set.seed(2026)

# --- 读入数据 ---
d <- read_csv(here::here("data", "rhc.csv"), show_col_types = FALSE) |>
  mutate(death180_bin = ifelse(death180 == "Yes", 1, 0))

# --- 协变量公式 ---
covs <- c("age", "sex", "edu", "das_index", "apache_score",
  "glasgow_coma_score", "blood_pressure", "wbc", "heart_rate",
  "respiratory_rate", "temperature", "pa_o2vs_fio2",
  "albumin", "hematocrit", "bilirubin", "creatinine",
  "sodium", "potassium", "pa_co2", "ph", "weight",
  "dnr_status", "medical_insurance", "race", "income",
  "cancer", "cardiovascular", "congestive_hf", "dementia",
  "psychiatric", "pulmonary", "renal", "hepatic",
  "gi_bleed", "tumor", "immunosupperssion", "transfer_hx", "mi")

fml <- as.formula(paste("rhc ~", paste(covs, collapse = " + ")))

# --- 倾向得分估计 ---
ps_model <- glm(fml, data = d, family = binomial)
d$ps <- predict(ps_model, type = "response")
cat("PS summary:\n")
print(summary(d$ps))
d |> group_by(rhc) |> summarise(
  mean_ps = mean(ps), sd_ps = sd(ps),
  min_ps = min(ps), max_ps = max(ps)) |> print()

# --- Figure 1: PS 重叠直方图 ---
p_overlap <- ggplot(d, aes(x = ps,
    fill = factor(rhc, labels = c("No RHC", "RHC")))) +
  geom_histogram(aes(y = after_stat(density)),
                 bins = 50, alpha = 0.6, position = "identity") +
  scale_fill_manual(values = c("No RHC" = "#4292C6",
                               "RHC"    = "#EF6548")) +
  labs(x = "Propensity Score", y = "Density", fill = "Group") +
  theme_minimal(base_size = 14, base_family = "serif") +
  theme(legend.position = c(0.85, 0.85))

ggsave(here::here("figure", "chap05_ps_overlap.pdf"),
       p_overlap, width = 7, height = 4.5)

# --- PSM: 1:1 最近邻匹配 + 卡钳 ---
m_out <- matchit(fml, data = d, method = "nearest",
                 distance = "glm", caliper = 0.2, ratio = 1)
print(summary(m_out))

m_data <- match.data(m_out)
cat("Matched n:", nrow(m_data), "\n")

rd_psm <- mean(m_data$death180_bin[m_data$rhc == 1]) -
          mean(m_data$death180_bin[m_data$rhc == 0])
cat("PSM RD:", round(rd_psm, 4), "\n")

# Bootstrap CI for PSM
boot_psm <- replicate(1000, {
  idx <- sample(nrow(m_data), replace = TRUE)
  bd <- m_data[idx, ]
  mean(bd$death180_bin[bd$rhc == 1]) - mean(bd$death180_bin[bd$rhc == 0])
})
cat("PSM 95% CI:", round(quantile(boot_psm, c(0.025, 0.975)), 4), "\n")

# --- IPW ---
w_ipw <- weightit(fml, data = d, method = "glm", estimand = "ATE")
print(summary(w_ipw))
d$w_ipw <- w_ipw$weights

ate_ipw <- weighted.mean(d$death180_bin[d$rhc == 1], d$w_ipw[d$rhc == 1]) -
           weighted.mean(d$death180_bin[d$rhc == 0], d$w_ipw[d$rhc == 0])
cat("IPW RD:", round(ate_ipw, 4), "\n")

# Bootstrap CI for IPW
boot_ipw <- replicate(1000, {
  idx <- sample(nrow(d), replace = TRUE)
  bd <- d[idx, ]
  w_b <- weightit(fml, data = bd, method = "glm", estimand = "ATE")
  bd$w <- w_b$weights
  weighted.mean(bd$death180_bin[bd$rhc == 1], bd$w[bd$rhc == 1]) -
    weighted.mean(bd$death180_bin[bd$rhc == 0], bd$w[bd$rhc == 0])
})
cat("IPW 95% CI:", round(quantile(boot_ipw, c(0.025, 0.975)), 4), "\n")

# --- Overlap Weights ---
w_ow <- weightit(fml, data = d, method = "glm", estimand = "ATO")
print(summary(w_ow))
d$w_ow <- w_ow$weights

ate_ow <- weighted.mean(d$death180_bin[d$rhc == 1], d$w_ow[d$rhc == 1]) -
          weighted.mean(d$death180_bin[d$rhc == 0], d$w_ow[d$rhc == 0])
cat("OW RD:", round(ate_ow, 4), "\n")

# Bootstrap CI for OW
boot_ow <- replicate(1000, {
  idx <- sample(nrow(d), replace = TRUE)
  bd <- d[idx, ]
  w_b <- weightit(fml, data = bd, method = "glm", estimand = "ATO")
  bd$w <- w_b$weights
  weighted.mean(bd$death180_bin[bd$rhc == 1], bd$w[bd$rhc == 1]) -
    weighted.mean(bd$death180_bin[bd$rhc == 0], bd$w[bd$rhc == 0])
})
cat("OW 95% CI:", round(quantile(boot_ow, c(0.025, 0.975)), 4), "\n")

# --- Figure 2: Love plot ---
p_love <- love.plot(fml, data = d,
  stats = "m", abs = TRUE,
  thresholds = c(m = 0.1),
  weights = list(PSM = m_out, IPW = w_ipw, OW = w_ow),
  colors = c("#999999", "#EF6548", "#4292C6", "#66C2A5"),
  shapes = c(17, 16, 15, 18),
  sample.names = c("Unadjusted", "PSM", "IPW", "OW"),
  line = TRUE) +
  theme_minimal(base_size = 12, base_family = "serif") +
  theme(legend.position = "bottom")

ggsave(here::here("figure", "chap05_love_plot.pdf"),
       p_love, width = 8, height = 7)

cat("All Chapter 5 outputs generated.\n")
