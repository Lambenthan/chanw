# =========================================================
# Chapter 8: 发表偏倚的诊断与校正
# 漏斗图 / Egger / Begg / trim-and-fill 在 dat.bcg 上
# =========================================================

library(tidyverse)
library(metafor)
library(here)
set.seed(2026)

d  <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)
es <- escalc(measure = "RR", ai = tpos, bi = tneg,
             ci = cpos, di = cneg, data = d, append = TRUE)

re <- rma(yi, vi, data = es, method = "REML", test = "knha")

# ---------- Egger 回归检验 ----------
egger <- regtest(re, model = "lm")
cat("\n===== Egger 回归检验 =====\n")
print(egger)

# ---------- Begg 秩相关检验 ----------
begg <- ranktest(re)
cat("\n===== Begg 秩相关检验 =====\n")
print(begg)

# ---------- Trim-and-fill ----------
tf <- trimfill(re)
cat("\n===== Trim-and-fill =====\n")
print(tf)
cat("\n填补研究数:", tf$k0, "\n")
cat("填补后合并 logRR =", round(tf$beta, 4),
    "  RR =", round(exp(tf$beta), 3),
    "  95% CI = [", round(exp(tf$ci.lb), 3), ",",
                    round(exp(tf$ci.ub), 3), "]\n")

# ---------- 漏斗图 ----------
pdf(here::here("figure", "chap08_funnel.pdf"),
    width = 7, height = 5.5, family = "Times")
funnel(re,
       xlab    = "log Risk Ratio",
       atransf = exp,
       at      = log(c(0.05, 0.25, 1, 4)),
       refline = re$beta,
       label   = "out",
       cex     = 0.9)
dev.off()

# ---------- Trim-and-fill 漏斗图 ----------
pdf(here::here("figure", "chap08_funnel_tf.pdf"),
    width = 7, height = 5.5, family = "Times")
funnel(tf,
       xlab    = "log Risk Ratio",
       atransf = exp,
       at      = log(c(0.05, 0.25, 1, 4)),
       refline = tf$beta,
       label   = "out",
       cex     = 0.9)
dev.off()

# ---------- contour-enhanced funnel ----------
pdf(here::here("figure", "chap08_funnel_contour.pdf"),
    width = 7, height = 5.5, family = "Times")
funnel(re,
       level    = c(90, 95, 99),
       shade    = c("white", "gray85", "gray70"),
       refline  = 0,
       atransf  = exp,
       at       = log(c(0.05, 0.25, 1, 4)),
       legend   = TRUE,
       xlab     = "log Risk Ratio")
dev.off()

cat("\n===== Chapter 8 figures generated =====\n")
