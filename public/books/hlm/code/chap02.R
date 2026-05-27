# =========================================================
# Chapter 2: 嵌套数据与组内相关 ICC
# 朴素 OLS vs 考虑班级嵌套的标准误对比 + ICC
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

# ---------- 朴素 OLS（不考虑嵌套）----------
ols_naive <- lm(math ~ cltype, data = d)
ols_se <- summary(ols_naive)$coefficients
cat("\n===== 朴素 OLS（不考虑嵌套）=====\n")
print(round(ols_se, 4))

# ---------- 把"班级"当成固定效应（dummy）----------
# 这只是为了演示组内组间方差概念，实际书里推荐随机效应
ols_class <- lm(math ~ cltype + factor(tch), data = d)
cat("\n===== OLS + 班级固定效应（dummy 法）=====\n")
co <- summary(ols_class)$coefficients
co_treat <- co[grep("cltype", rownames(co)), ]
print(round(co_treat, 4))

# ---------- 用 lmer 跑空模型（仅班级随机截距）----------
m0_class <- lmer(math ~ 1 + (1 | tch), data = d)
cat("\n===== 空模型：仅班级随机截距 =====\n")
print(summary(m0_class))

# 抽取方差分量
vc <- as.data.frame(VarCorr(m0_class))
sigma2_class <- vc$vcov[vc$grp == "tch"]
sigma2_resid <- vc$vcov[vc$grp == "Residual"]
icc_class <- sigma2_class / (sigma2_class + sigma2_resid)
cat("\n===== ICC（仅班级层面）=====\n")
cat("σ²(class) =",        round(sigma2_class, 2), "\n")
cat("σ²(residual) =",     round(sigma2_resid, 2), "\n")
cat("ICC(class) =",       round(icc_class * 100, 2), "%\n")

# ---------- 考虑嵌套的处理效应 ----------
m1_class <- lmer(math ~ cltype + (1 | tch), data = d)
cat("\n===== 加入处理效应（cltype）=====\n")
print(summary(m1_class))

# 朴素 vs HLM 标准误对比
ols_se_small <- ols_se["cltypesmall", "Std. Error"]
hlm_se_small <- summary(m1_class)$coefficients["cltypesmall", "Std. Error"]
cat("\n===== 标准误对比：小班效应 =====\n")
cat("朴素 OLS 的 SE =",    round(ols_se_small, 3), "\n")
cat("HLM (仅班级) SE =",   round(hlm_se_small, 3), "\n")
cat("SE 膨胀比例 =",       round(hlm_se_small / ols_se_small, 2), "倍\n")

# ---------- 模拟：把同一班学生当独立 vs 当一组的差异 ----------
# 演示 design effect = 1 + (n_bar - 1) * ICC
nbar <- mean(table(d$tch))
deff <- 1 + (nbar - 1) * icc_class
cat("\n===== 设计效应（design effect）=====\n")
cat("平均班级人数 n̄ =",    round(nbar, 2), "\n")
cat("设计效应 1 + (n̄-1) × ICC =", round(deff, 2), "\n")
cat("有效样本量 ≈ n / DEFF =",     round(nrow(d) / deff, 0), "（实际 n =", nrow(d), "）\n")

# ---------- 图 2.1：典型 6 个班的学生分数（同班相似性可视化）----------
set.seed(2026)
sample_classes <- d |>
  group_by(tch) |>
  filter(n() >= 12) |>
  ungroup() |>
  distinct(tch) |>
  slice_sample(n = 6) |>
  pull(tch)

p1 <- d |>
  filter(tch %in% sample_classes) |>
  mutate(tch_lab = sprintf("Class %s", tch)) |>
  ggplot(aes(x = tch_lab, y = math, color = cltype)) +
  geom_jitter(width = 0.18, alpha = 0.7, size = 2) +
  stat_summary(fun = mean, geom = "crossbar",
               width = 0.55, color = "gray20", linewidth = 0.5) +
  scale_color_manual(values = c("small" = "#EF6548",
                                "reg"   = "#4292C6",
                                "reg+A" = "#41AB5D"),
                     labels = c("small" = ts("small"),
                                "reg"   = ts("reg"),
                                "reg+A" = ts("reg+A"))) +
  labs(x = "随机抽 6 个班级", y = "数学考试分数",
       title = "同一个班的学生分数比跨班平均更相似",
       subtitle = "灰色横线为班级均值；同班学生的分散程度小于全样本",
       color = "班级类型") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap02_within_class.png"),
       p1, width = 7.5, height = 4.5, dpi = 300, device = ragg::agg_png)

# ---------- 图 2.2：方差分解饼图 ----------
var_df <- tibble(
  source = c("class", "resid"),
  value  = c(sigma2_class, sigma2_resid)
) |>
  mutate(pct = value / sum(value) * 100)

p2 <- ggplot(var_df, aes(x = "", y = value, fill = source)) +
  geom_col(width = 1, color = "white") +
  coord_polar(theta = "y") +
  scale_fill_manual(
    values = c("class" = "#EF6548", "resid" = "#4292C6"),
    labels = c("class" = paste0("班级间方差 ", ts("σ²(class)")),
               "resid" = paste0("班级内方差 ", ts("σ²(residual)")))
  ) +
  geom_text(aes(label = sprintf("%.1f%%", pct)),
            position = position_stack(vjust = 0.5),
            family = "Times New Roman", color = "white", size = 5) +
  labs(title = paste0("K 年级数学分数：班级间 ", ts("vs"), " 班级内方差"),
       subtitle = paste0(ts(sprintf("ICC(class) = %.1f%%", icc_class * 100))),
       fill = NULL) +
  theme_book(base_size = 11) +
  theme(axis.title = element_blank(),
        axis.text = element_blank(),
        panel.grid = element_blank())

ggsave(here::here("figure", "chap02_variance_pie.png"),
       p2, width = 6.0, height = 4.4, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 2 figures generated =====\n")
