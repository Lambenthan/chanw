# =========================================================
# Chapter 7: 亚组分析与 meta 回归
# 在 dat.bcg 上用 ablat 与 alloc 解释异质性
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

# ---------- 主模型（无协变量，作基线） ----------
re_base <- rma(yi, vi, data = es, method = "REML", test = "knha")
cat("\n===== 基线模型（无协变量） =====\n")
cat("logRR =", round(re_base$beta, 4),
    "  tau^2 =", round(re_base$tau2, 4),
    "  I^2 =",  round(re_base$I2, 1), "%\n")

# ---------- 亚组分析：按 alloc ----------
cat("\n===== 亚组分析：按分配方式 alloc =====\n")
re_random     <- rma(yi, vi, subset = (alloc == "random"),     data = es,
                     method = "REML", test = "knha")
re_alternate  <- rma(yi, vi, subset = (alloc == "alternate"),  data = es,
                     method = "REML", test = "knha")
re_systematic <- rma(yi, vi, subset = (alloc == "systematic"), data = es,
                     method = "REML", test = "knha")

cat("alloc = random      (k =",     re_random$k,    "): logRR =",
    round(re_random$beta, 4),     ", RR =", round(exp(re_random$beta), 3),
    ", CI = [", round(exp(re_random$ci.lb), 3), ",",
                round(exp(re_random$ci.ub), 3), "]\n")
cat("alloc = alternate   (k =",     re_alternate$k, "): logRR =",
    round(re_alternate$beta, 4),  ", RR =", round(exp(re_alternate$beta), 3),
    ", CI = [", round(exp(re_alternate$ci.lb), 3), ",",
                round(exp(re_alternate$ci.ub), 3), "]\n")
cat("alloc = systematic  (k =",     re_systematic$k,"): logRR =",
    round(re_systematic$beta, 4), ", RR =", round(exp(re_systematic$beta), 3),
    ", CI = [", round(exp(re_systematic$ci.lb), 3), ",",
                round(exp(re_systematic$ci.ub), 3), "]\n")

# 亚组之间的差异检验（用 alloc 作 categorical moderator）
re_alloc <- rma(yi, vi, mods = ~ alloc, data = es,
                method = "REML", test = "knha")
cat("\n===== alloc 作为 categorical moderator =====\n")
print(re_alloc)
cat("\nalloc 类型差异检验：QM =", round(re_alloc$QM, 3),
    ", df =", re_alloc$QMdf[1],
    ", p =", format.pval(re_alloc$QMp, digits = 3), "\n")

# ---------- Meta 回归：按 ablat（连续协变量） ----------
re_ablat <- rma(yi, vi, mods = ~ ablat, data = es,
                method = "REML", test = "knha")
cat("\n===== Meta 回归：纬度 ablat =====\n")
print(re_ablat)

# 计算 R²（已解释 tau² 的比例）
R2_ablat <- max(0, (re_base$tau2 - re_ablat$tau2) / re_base$tau2) * 100
cat("\nR^2 (ablat 解释的 tau^2 比例) =", round(R2_ablat, 1), "%\n")
cat("基线 tau^2 =", round(re_base$tau2, 4),
    "  加入 ablat 后 tau^2 =", round(re_ablat$tau2, 4), "\n")

# ---------- 联合模型：ablat + alloc ----------
re_joint <- rma(yi, vi, mods = ~ ablat + alloc, data = es,
                method = "REML", test = "knha")
cat("\n===== 联合 Meta 回归：ablat + alloc =====\n")
print(re_joint)

R2_joint <- max(0, (re_base$tau2 - re_joint$tau2) / re_base$tau2) * 100
cat("\nR^2 (joint, ablat + alloc) =", round(R2_joint, 1), "%\n")

# ---------- Bubble plot for ablat 回归 ----------
es_g <- es |>
  arrange(ablat) |>
  mutate(weight_re = 1 / (vi + re_base$tau2),
         label = sprintf("%d", trial))

# 预测线（基于 ablat 模型）
pred_x <- seq(min(es$ablat), max(es$ablat), length.out = 100)
pred_y <- predict(re_ablat, newmods = pred_x)

p <- ggplot(es_g, aes(x = ablat, y = yi)) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray50") +
  geom_ribbon(data = data.frame(x = pred_x,
                                lo = pred_y$ci.lb,
                                hi = pred_y$ci.ub),
              aes(x = x, ymin = lo, ymax = hi),
              inherit.aes = FALSE,
              fill = "#EF6548", alpha = 0.15) +
  geom_line(data = data.frame(x = pred_x, y = pred_y$pred),
            aes(x = x, y = y), inherit.aes = FALSE,
            color = "#EF6548", linewidth = 0.8) +
  geom_point(aes(size = weight_re), color = "#4292C6", alpha = 0.85) +
  geom_text(aes(label = label), nudge_x = 0.7, nudge_y = 0.05,
            size = 3, family = "Times New Roman") +
  scale_size_continuous(range = c(2, 7), guide = "none") +
  labs(x = "试验地点的绝对纬度（度）",
       y = "log RR",
       title = "Bubble plot：纬度对 BCG 效应的影响",
       subtitle = "气泡大小与随机效应权重成正比；红色实线为 meta 回归拟合") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap07_bubble_ablat.png"),
       p, width = 7.5, height = 5, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 7 figures generated =====\n")
