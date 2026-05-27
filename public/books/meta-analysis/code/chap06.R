# =========================================================
# Chapter 6: 异质性诊断 Q / I² / τ² / 预测区间
# 在 dat.bcg 上完整算异质性指标 + Galbraith / Baujat 图
# =========================================================

library(tidyverse)
library(metafor)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

d  <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)
es <- escalc(measure = "RR", ai = tpos, bi = tneg,
             ci = cpos, di = cneg, data = d, append = TRUE)

re <- rma(yi, vi, data = es, method = "REML", test = "knha")

# ---------- 异质性核心指标 ----------
cat("\n===== 异质性诊断 =====\n")
cat("Q          =", round(re$QE, 3),
    "  df =", re$k - 1,
    "  p =", format.pval(re$QEp, digits = 3), "\n")
cat("I²         =", round(re$I2, 2), "%\n")
cat("H²         =", round(re$H2, 3), "\n")
cat("tau²       =", round(re$tau2, 4),
    "  SE(tau²) =", round(re$se.tau2, 4), "\n")
cat("tau        =", round(sqrt(re$tau2), 4), "  (log RR scale)\n")
cat("tau on RR  : exp(tau) =", round(exp(sqrt(re$tau2)), 3), "\n")

# 95% CI for tau²（confint）
ci_tau <- confint(re)
cat("\n===== tau² 与 I² 的 95% CI =====\n")
print(ci_tau)

# 预测区间
pi <- predict(re)
cat("\n===== 95% 预测区间 =====\n")
cat("PI (logRR) = [", round(pi$pi.lb, 4), ",", round(pi$pi.ub, 4), "]\n")
cat("PI (RR)    = [", round(exp(pi$pi.lb), 3), ",",
                       round(exp(pi$pi.ub), 3), "]\n")

# ---------- Galbraith plot ----------
# Galbraith plot：横轴 1/SE_i，纵轴 yi/SE_i
# 同质时所有点应该落在 ±2 之间，过零线代表无效应
es_g <- es |>
  arrange(ablat) |>
  mutate(
    se_i  = sqrt(vi),
    inv_se = 1 / se_i,
    z_i    = yi / se_i,
    label  = sprintf("%d", trial)
  )

# 拟合一根 z = 0 + slope * (1/SE) 直线（forced through origin = 合并 logRR）
slope_fe <- as.numeric(rma(yi, vi, data = es, method = "EE")$beta)

p1 <- ggplot(es_g, aes(x = inv_se, y = z_i)) +
  geom_hline(yintercept =  2, linetype = "dashed", color = "red") +
  geom_hline(yintercept = -2, linetype = "dashed", color = "red") +
  geom_hline(yintercept =  0, color = "gray50", linewidth = 0.4) +
  geom_abline(slope = slope_fe, intercept = 0,
              color = "#4292C6", linewidth = 0.8) +
  geom_point(aes(size = inv_se), color = "#EF6548", alpha = 0.85) +
  geom_text(aes(label = label),
            nudge_x = 0.5, nudge_y = 0.3, size = 3,
            family = "Times New Roman") +
  scale_size_continuous(range = c(2, 5), guide = "none") +
  labs(x = "1 / SE  (精度)", y = "log RR / SE  (标准化效应)",
       title = "Galbraith 图：异质性的视觉诊断",
       subtitle = "红色虚线为 ±2 阈值；同质时点应集中在虚线之间") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap06_galbraith.png"),
       p1, width = 7, height = 5, dpi = 300, device = ragg::agg_png)

# ---------- Baujat plot ----------
# Baujat plot：横轴每项研究对 Q 的贡献（heterogeneity contribution），
# 纵轴每项研究对合并估计的影响（influence on pooled estimate）
pdf(here::here("figure", "chap06_baujat.pdf"),
    width = 7, height = 5, family = "Times")
baujat(re,
       xlab = "Contribution to overall heterogeneity",
       ylab = "Influence on overall result")
dev.off()

cat("\n===== Chapter 6 figures generated =====\n")
