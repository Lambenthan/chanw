# =========================================================
# Chapter 10: 方法对比与 GRADE 证据等级
# 终极 forest plot：所有方法的合并估计并列
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

# ---------- 所有方法 ----------
fe_iv      <- rma(yi, vi, data = es, method = "EE")
fe_mh      <- rma.mh(measure = "RR", ai = tpos, bi = tneg,
                     ci = cpos, di = cneg, data = d)
re_dl      <- rma(yi, vi, data = es, method = "DL")
re_reml    <- rma(yi, vi, data = es, method = "REML")
re_hk      <- rma(yi, vi, data = es, method = "REML", test = "knha")
tf         <- trimfill(re_hk)

# Meta 回归在 ablat 三个值上的预测
re_ablat <- rma(yi, vi, mods = ~ ablat, data = es,
                method = "REML", test = "knha")
pred_ablat <- predict(re_ablat, newmods = c(13, 33, 55))

# ---------- 汇总表 ----------
results <- tibble(
  method = c("朴素合并", "FE-IV", "FE-MH", "RE-DL",
             "RE-REML", "RE-REML+HK", "Trim-and-fill",
             "条件 RR @ 13°", "条件 RR @ 33°", "条件 RR @ 55°"),
  logRR = c(
    log(sum(d$tpos) / sum(d$tpos + d$tneg) /
        (sum(d$cpos) / sum(d$cpos + d$cneg))),
    fe_iv$beta, fe_mh$beta, re_dl$beta,
    re_reml$beta, re_hk$beta, tf$beta,
    pred_ablat$pred[1], pred_ablat$pred[2], pred_ablat$pred[3]
  ),
  ci_lb = c(NA, fe_iv$ci.lb, fe_mh$ci.lb, re_dl$ci.lb,
            re_reml$ci.lb, re_hk$ci.lb, tf$ci.lb,
            pred_ablat$ci.lb[1], pred_ablat$ci.lb[2], pred_ablat$ci.lb[3]),
  ci_ub = c(NA, fe_iv$ci.ub, fe_mh$ci.ub, re_dl$ci.ub,
            re_reml$ci.ub, re_hk$ci.ub, tf$ci.ub,
            pred_ablat$ci.ub[1], pred_ablat$ci.ub[2], pred_ablat$ci.ub[3])
) |>
  mutate(RR    = round(exp(logRR), 3),
         RR_lb = round(exp(ci_lb), 3),
         RR_ub = round(exp(ci_ub), 3),
         logRR = round(logRR, 4))

cat("\n===== 终极方法对比 =====\n")
print(results)

# ---------- 终极 forest 对比图 ----------
plot_df <- results |>
  filter(!is.na(ci_lb)) |>
  mutate(method = factor(method, levels = method))

p <- ggplot(plot_df, aes(x = logRR, y = method)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbar(aes(xmin = ci_lb, xmax = ci_ub),
                width = 0.2, color = "#4292C6", linewidth = 0.7) +
  geom_point(size = 3.5, color = "#EF6548") +
  geom_text(aes(label = sprintf("RR=%.2f [%.2f, %.2f]",
                                RR, RR_lb, RR_ub)),
            nudge_x = 0.1, hjust = 0,
            size = 3, family = "Times New Roman") +
  scale_x_continuous(limits = c(-1.6, 0.5)) +
  labs(x = "log RR (95% CI)", y = NULL,
       title = "全书方法对比：dat.bcg 上九种合并方法的合并估计",
       subtitle = "FE 与 RE 估计差异巨大；meta 回归条件 RR 跨度从 0.26 到 0.88") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap10_all_methods.png"),
       p, width = 9, height = 5.5, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 10 figures generated =====\n")
