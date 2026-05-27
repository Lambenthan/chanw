# =========================================================
# Chapter 3: 空模型 —— 随机截距与方差分解
# 详细讲解 lme4 的空模型输出 + REML vs ML
# =========================================================

library(tidyverse)
library(lme4)
library(lmerTest)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

d <- read_csv(here::here("data", "star_k.csv"), show_col_types = FALSE) |>
  filter(!is.na(math), !is.na(cltype), !is.na(tch), !is.na(sch))

# ---------- 空模型（仅班级随机截距）----------
m0_reml <- lmer(math ~ 1 + (1 | tch), data = d, REML = TRUE)
m0_ml   <- lmer(math ~ 1 + (1 | tch), data = d, REML = FALSE)

cat("\n===== 空模型（REML）=====\n")
print(summary(m0_reml))

cat("\n===== REML vs ML 方差分量对比 =====\n")
vc_reml <- as.data.frame(VarCorr(m0_reml))
vc_ml   <- as.data.frame(VarCorr(m0_ml))

cmp <- tibble(
  param         = c("σ²(class)", "σ²(residual)", "intercept (β₀)"),
  REML          = c(round(vc_reml$vcov[vc_reml$grp == "tch"], 3),
                    round(vc_reml$vcov[vc_reml$grp == "Residual"], 3),
                    round(fixef(m0_reml), 3)),
  ML            = c(round(vc_ml$vcov[vc_ml$grp == "tch"], 3),
                    round(vc_ml$vcov[vc_ml$grp == "Residual"], 3),
                    round(fixef(m0_ml), 3))
)
print(cmp)

# ---------- 班级 BLUP（每个班的随机截距估计）----------
ranef_class <- ranef(m0_reml)$tch
cat("\n===== 班级 BLUP 分布 =====\n")
cat("最低 BLUP =",  round(min(ranef_class[, 1]), 2),  "\n")
cat("最高 BLUP =",  round(max(ranef_class[, 1]), 2),  "\n")
cat("BLUP SD =",    round(sd(ranef_class[, 1]), 2),   "\n")
cat("跟 sqrt(σ²(class)) 比较：sqrt =",
    round(sqrt(vc_reml$vcov[vc_reml$grp == "tch"]), 2), "\n")

# ---------- 收缩（shrinkage）演示 ----------
# 原始班级均值 vs 收缩后的 BLUP
class_raw <- d |>
  group_by(tch) |>
  summarise(raw_mean = mean(math, na.rm = TRUE),
            n = n(), .groups = "drop")

blup_df <- tibble(tch = rownames(ranef_class),
                  blup = ranef_class[, 1] + fixef(m0_reml)) |>
  left_join(class_raw |> mutate(tch = as.character(tch)), by = "tch")

cat("\n===== 收缩效果：原始均值 vs BLUP =====\n")
cat("原始均值 SD =",  round(sd(blup_df$raw_mean), 2), "\n")
cat("BLUP SD =",      round(sd(blup_df$blup), 2),     "\n")
cat("收缩比例 =",     round((1 - sd(blup_df$blup) / sd(blup_df$raw_mean)) * 100, 1),
    "%\n")

# ---------- 似然比检验 OLS vs HLM ----------
ols_null <- lm(math ~ 1, data = d)
ll_ols <- as.numeric(logLik(ols_null))
ll_hlm <- as.numeric(logLik(m0_ml))
cat("\n===== 似然比检验：OLS 是否被 HLM 击败？=====\n")
LR <- 2 * (ll_hlm - ll_ols)
cat("LR =", round(LR, 2), "  df = 1\n")
cat("p =",  format.pval(0.5 * pchisq(LR, df = 1, lower.tail = FALSE),
                         digits = 4), "\n")

# ---------- 图 3.1：BLUP 收缩示意 ----------
plot_df <- blup_df |>
  arrange(raw_mean) |>
  mutate(rank = row_number()) |>
  pivot_longer(c(raw_mean, blup), names_to = "type", values_to = "estimate")

# 用线段把同一班的两个估计连起来
seg_df <- blup_df |>
  arrange(raw_mean) |>
  mutate(rank = row_number())

raw_lab  <- "原始班级均值"
blup_lab <- paste0(ts("BLUP"), "（收缩后）")

p1 <- ggplot() +
  geom_segment(data = seg_df,
               aes(x = rank, xend = rank,
                   y = raw_mean, yend = blup),
               color = "gray60", alpha = 0.5, linewidth = 0.3) +
  geom_point(data = plot_df,
             aes(x = rank, y = estimate, color = type, size = type),
             alpha = 0.7) +
  scale_color_manual(values = c("raw_mean" = "#EF6548",
                                "blup"     = "#4292C6"),
                     labels = c("raw_mean" = raw_lab,
                                "blup"     = blup_lab)) +
  scale_size_manual(values = c("raw_mean" = 1.5, "blup" = 1.0),
                    labels = c("raw_mean" = raw_lab,
                               "blup"     = blup_lab)) +
  geom_hline(yintercept = fixef(m0_reml), linetype = "dashed",
             color = "gray40", linewidth = 0.4) +
  labs(x = "班级（按原始均值排序）", y = "数学分数",
       title = paste0(ts("BLUP"), " 收缩：极端班级被拉向总均值"),
       subtitle = "灰线连接同一班的两个估计；样本量小或极端的班收缩更多",
       color = NULL, size = NULL) +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap03_blup_shrinkage.png"),
       p1, width = 7.5, height = 4.5, dpi = 300, device = ragg::agg_png)

# ---------- 图 3.2：方差分解条形图 ----------
var_df <- tibble(
  level = c("between", "within"),
  variance = c(vc_reml$vcov[vc_reml$grp == "tch"],
               vc_reml$vcov[vc_reml$grp == "Residual"])
) |>
  mutate(pct = variance / sum(variance) * 100)

p2 <- ggplot(var_df, aes(x = "", y = variance, fill = level)) +
  geom_col(color = "white") +
  geom_text(aes(label = sprintf("%.1f\n(%.1f%%)", variance, pct)),
            position = position_stack(vjust = 0.5),
            family = "Times New Roman", color = "white", size = 4.2) +
  scale_fill_manual(
    values = c("between" = "#EF6548", "within" = "#4292C6"),
    labels = c("between" = paste0("班级间 ", ts("(between-class)")),
               "within"  = paste0("班级内 ", ts("(within-class)")))
  ) +
  coord_flip() +
  labs(x = NULL, y = "方差分量",
       title = paste0("空模型方差分解：班级间 ", ts("vs"), " 班级内"),
       fill = NULL) +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap03_variance_decomp.png"),
       p2, width = 7.5, height = 2.8, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 3 figures generated =====\n")
