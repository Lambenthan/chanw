# =========================================================
# Chapter 5: 随机效应模型与 τ² 估计
# 在 dat.bcg 上跑 DL / REML / HK 三种 RE 估计
# =========================================================

library(tidyverse)
library(metafor)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

# ---------- 数据 ----------
d <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)
es <- escalc(measure = "RR",
             ai = tpos, bi = tneg, ci = cpos, di = cneg,
             data = d, append = TRUE)

# ---------- 三种估计量 ----------
re_dl   <- rma(yi, vi, data = es, method = "DL")
re_reml <- rma(yi, vi, data = es, method = "REML")
re_hk   <- rma(yi, vi, data = es, method = "REML", test = "knha")
fe_iv   <- rma(yi, vi, data = es, method = "EE")

# ---------- 抽取关键数字函数 ----------
extract_key <- function(model, name) {
  data.frame(
    method  = name,
    logRR   = round(as.numeric(model$beta), 4),
    se      = round(model$se, 4),
    ci_lb   = round(model$ci.lb, 4),
    ci_ub   = round(model$ci.ub, 4),
    RR      = round(exp(as.numeric(model$beta)), 3),
    RR_lb   = round(exp(model$ci.lb), 3),
    RR_ub   = round(exp(model$ci.ub), 3),
    tau2    = round(model$tau2, 4),
    I2      = round(model$I2, 1),
    H2      = round(model$H2, 2)
  )
}

results <- bind_rows(
  extract_key(fe_iv,   "FE-IV"),
  extract_key(re_dl,   "RE-DL"),
  extract_key(re_reml, "RE-REML"),
  extract_key(re_hk,   "RE-REML+HK")
)

cat("\n===== 四种合并方法对比 =====\n")
print(results)

# ---------- HK 模型详情 ----------
cat("\n===== RE-REML + HK 详细输出 =====\n")
print(re_hk)

# 预测区间（PI）
cat("\n===== 预测区间 (REML + HK) =====\n")
pi_hk <- predict(re_hk)
cat("合并 logRR =", round(pi_hk$pred, 4),
    "  PI = [", round(pi_hk$pi.lb, 4), ",",
                round(pi_hk$pi.ub, 4), "]\n")
cat("合并 RR    =", round(exp(pi_hk$pred), 3),
    "  PI (RR) = [", round(exp(pi_hk$pi.lb), 3), ",",
                     round(exp(pi_hk$pi.ub), 3), "]\n")

# ---------- Forest plot for RE-REML + HK ----------
pdf(here::here("figure", "chap05_forest_re.pdf"),
    width = 8, height = 6.5, family = "Times")
forest(re_hk,
       slab    = paste0(es$author, " (", es$year, ")"),
       atransf = exp,
       at      = log(c(0.05, 0.25, 1, 4)),
       xlab    = "Risk Ratio (log scale)",
       header  = c("Study", "RR [95% CI]"),
       mlab    = "Random-effects (REML + HK)",
       refline = 0,
       cex     = 0.8,
       addpred = TRUE)
dev.off()

# ---------- 比较图：四种方法的 forest 简化版 ----------
plot_df <- results |>
  mutate(method = factor(method,
                         levels = c("FE-IV", "RE-DL",
                                    "RE-REML", "RE-REML+HK")))

p <- ggplot(plot_df, aes(y = method)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbar(aes(xmin = ci_lb, xmax = ci_ub),
                width = 0.15, color = "#4292C6", linewidth = 0.8) +
  geom_point(aes(x = logRR), size = 4, color = "#EF6548") +
  geom_text(aes(x = logRR,
                label = sprintf("RR=%.2f, CI=[%.2f,%.2f]",
                                RR, RR_lb, RR_ub)),
            nudge_y = 0.25, size = 3, family = "Times New Roman") +
  labs(x = "log RR (95% CI)", y = NULL,
       title = "四种合并方法在 dat.bcg 上的结果对比",
       subtitle = "FE 与三种 RE 估计的 logRR 几乎一致，但 CI 宽度差异明显") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap05_methods_compare.png"),
       p, width = 8, height = 4, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 5 figures generated =====\n")
