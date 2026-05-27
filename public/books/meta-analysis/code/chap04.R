# =========================================================
# Chapter 4: 固定效应模型与逆方差加权
# 在 dat.bcg 上跑 FE model (IV + MH)
# =========================================================

library(tidyverse)
library(metafor)
library(here)
set.seed(2026)

# ---------- 数据准备 ----------
d <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)
es <- escalc(measure = "RR",
             ai = tpos, bi = tneg, ci = cpos, di = cneg,
             data = d, append = TRUE)

# ---------- 固定效应模型：逆方差加权 (IV) ----------
# method = "EE" (equal-effects) = "FE" (fixed-effects) 在 metafor 4.x 里都叫 EE
fe_iv <- rma(yi, vi, data = es, method = "EE")
cat("\n===== 固定效应模型（逆方差加权 IV） =====\n")
print(fe_iv)
cat("\n合并 RR =", round(exp(fe_iv$beta), 3),
    "  95% CI =", round(exp(fe_iv$ci.lb), 3), "to",
                  round(exp(fe_iv$ci.ub), 3), "\n")

# ---------- Mantel-Haenszel 加权 ----------
fe_mh <- rma.mh(measure = "RR",
                ai = tpos, bi = tneg, ci = cpos, di = cneg,
                data = d)
cat("\n===== Mantel-Haenszel 固定效应 =====\n")
print(fe_mh)
cat("\n合并 RR (MH) =", round(exp(fe_mh$beta), 3),
    "  95% CI =", round(exp(fe_mh$ci.lb), 3), "to",
                  round(exp(fe_mh$ci.ub), 3), "\n")

# ---------- 提取每项研究的权重 ----------
weights_iv <- weights(fe_iv) / 100   # 以百分比形式
cat("\n===== 13 项研究在 IV 模型下的权重（按权重排序）=====\n")
weights_df <- data.frame(
  trial   = es$trial,
  author  = es$author,
  year    = es$year,
  vi      = round(es$vi, 4),
  weight  = round(weights_iv * 100, 2)
) |> arrange(desc(weight))
print(weights_df)

# ---------- 异质性 Q 统计 ----------
cat("\n===== 异质性指标 =====\n")
cat("Q =", round(fe_iv$QE, 2),
    "  df =", fe_iv$k - 1,
    "  p =", format.pval(fe_iv$QEp, digits = 3), "\n")

# ---------- Forest plot ----------
pdf(here::here("figure", "chap04_forest_fe.pdf"),
    width = 8, height = 6.2, family = "Times")
forest(fe_iv,
       slab    = paste0(es$author, " (", es$year, ")"),
       atransf = exp,
       at      = log(c(0.05, 0.25, 1, 4)),
       xlab    = "Risk Ratio (log scale)",
       header  = c("Study", "RR [95% CI]"),
       mlab    = "Fixed-effects (IV) model",
       refline = 0,
       cex     = 0.8)
dev.off()

cat("\n===== Chapter 4 figures generated =====\n")
