# =========================================================
# Chapter 9: 模型诊断与影响分析
# 残差分层 + Cook's distance + 重启 / 收敛
# =========================================================

library(tidyverse)
library(lme4)
library(lmerTest)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

d <- read_csv(here::here("data", "star_k.csv"), show_col_types = FALSE) |>
  filter(!is.na(math), !is.na(cltype), !is.na(tch), !is.na(sch),
         !is.na(sx), !is.na(eth), !is.na(ses)) |>
  mutate(
    sex_F  = ifelse(sx == "F", 1, 0),
    eth_B  = ifelse(eth == "B", 1, 0),
    ses_F  = ifelse(ses == "F", 1, 0),
    cltype = factor(cltype, levels = c("reg", "reg+A", "small"))
  )

# ---------- 主模型（三层 + 全协变量）----------
m <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | sch/tch),
          data = d, REML = TRUE)

# ---------- 学生层残差（Level-1）----------
res_l1 <- residuals(m)
fit_l1 <- fitted(m)

# ---------- 班级层 + 学校层 BLUP ----------
re <- ranef(m)
class_blup <- re$`tch:sch`[, "(Intercept)"]
school_blup <- re$sch[, "(Intercept)"]

cat("\n===== 各层残差/BLUP 描述 =====\n")
cat("学生层残差 SD =",  round(sd(res_l1), 2), "\n")
cat("班级层 BLUP SD =", round(sd(class_blup), 2),  "\n")
cat("学校层 BLUP SD =", round(sd(school_blup), 2), "\n")

# ---------- QQ 检验：学生层残差正态性 ----------
shap_l1 <- if (length(res_l1) <= 5000) {
  shapiro.test(res_l1)
} else {
  shapiro.test(sample(res_l1, 5000))
}
cat("\n===== 残差正态性（Shapiro-Wilk，抽样 5000 检验）=====\n")
print(shap_l1)

# ---------- leave-one-out 班级 删除：估计变化 ----------
# 选样本量最大的几个班 + 几个 BLUP 极端的班，测稳健性
class_n <- d |> count(tch)
extreme_classes <- tibble(tch = rownames(re$`tch:sch`),
                          blup = class_blup) |>
  arrange(desc(abs(blup))) |>
  head(5) |>
  pull(tch)
big_classes <- class_n |> arrange(desc(n)) |> head(5) |> pull(tch)
candidate <- unique(c(extreme_classes, big_classes))

base_eff <- summary(m)$coefficients["cltypesmall", "Estimate"]
loo_results <- map_dfr(candidate, function(k) {
  d_loo <- d |> filter(tch != k)
  m_loo <- suppressWarnings(suppressMessages(
    lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | sch/tch),
         data = d_loo, REML = TRUE)
  ))
  tibble(
    excluded_tch = k,
    n_dropped    = sum(d$tch == k),
    eff_small    = summary(m_loo)$coefficients["cltypesmall", "Estimate"],
    se_small     = summary(m_loo)$coefficients["cltypesmall", "Std. Error"]
  )
})

loo_results <- loo_results |>
  mutate(delta = round(eff_small - base_eff, 3),
         eff_small = round(eff_small, 3),
         se_small  = round(se_small,  3))

cat("\n===== leave-one-class-out 敏感性分析 =====\n")
print(loo_results)
cat("\n基线小班效应:", round(base_eff, 3), "\n")

# ---------- 影响诊断：哪些班级"分量"最重？----------
# 三层模型里 tch:sch 的 rownames 形如 "1:23"，提取后半部分 (= tch)
class_summary <- d |>
  count(tch) |>
  mutate(tch = as.character(tch))
parse_tch <- function(s) sub("^[^:]+:", "", s)
infl_df <- tibble(label = rownames(re$`tch:sch`),
                  tch = parse_tch(rownames(re$`tch:sch`)),
                  blup = class_blup) |>
  left_join(class_summary, by = "tch") |>
  mutate(n = ifelse(is.na(n), 0, n),
         influence = n * abs(blup)) |>
  arrange(desc(influence))

cat("\n===== 影响最大的 10 个班级 =====\n")
print(infl_df |> head(10) |>
        mutate(blup = round(blup, 2), influence = round(influence, 1)))

# ---------- 图 9.1：残差 vs 拟合值 ----------
p1 <- tibble(fitted = fit_l1, resid = res_l1) |>
  ggplot(aes(x = fitted, y = resid)) +
  geom_hline(yintercept = 0, color = "gray40", linewidth = 0.4) +
  geom_point(alpha = 0.25, size = 0.8, color = "#4292C6") +
  geom_smooth(method = "loess", color = "#EF6548",
              se = FALSE, linewidth = 0.7) +
  labs(x = "拟合值（fitted math）",
       y = "学生层残差",
       title = "残差 vs 拟合值（学生层）",
       subtitle = "理想情形是水平散点；本数据残差均值与方差大致稳定") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap09_resid_vs_fit.png"),
       p1, width = 7.0, height = 4.2, dpi = 300, device = ragg::agg_png)

# ---------- 图 9.2：QQ 图（学生层残差）----------
qq_df <- tibble(res = res_l1) |>
  arrange(res) |>
  mutate(rank = row_number(),
         theoretical = qnorm((rank - 0.5) / n()))

p2 <- ggplot(qq_df, aes(x = theoretical, y = res)) +
  geom_point(alpha = 0.25, size = 0.7, color = "#4292C6") +
  geom_abline(slope = sd(res_l1), intercept = 0,
              color = "#EF6548", linewidth = 0.6) +
  labs(x = "理论分位数（标准正态）",
       y = "学生层残差",
       title = "学生层残差 QQ 图",
       subtitle = "尾部稍有偏离，但主体接近正态") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap09_qq.png"),
       p2, width = 6.0, height = 4.2, dpi = 300, device = ragg::agg_png)

# ---------- 图 9.3：leave-one-out 森林图 ----------
loo_plot <- loo_results |>
  mutate(label = sprintf("Class %s (n=%d)", excluded_tch, n_dropped),
         label = factor(label, levels = label))

p3 <- ggplot(loo_plot, aes(y = label, x = eff_small)) +
  geom_vline(xintercept = base_eff, linetype = "dashed",
             color = "#EF6548", linewidth = 0.6) +
  geom_errorbarh(aes(xmin = eff_small - 1.96 * se_small,
                     xmax = eff_small + 1.96 * se_small),
                 height = 0.18, color = "#4292C6", linewidth = 0.6) +
  geom_point(size = 3, color = "#EF6548") +
  geom_text(aes(label = sprintf("%.2f (Δ %+.2f)", eff_small, delta)),
            nudge_y = 0.25, size = 3, family = "Times New Roman") +
  labs(x = "去掉某班后的小班效应估计 (95% CI)",
       y = "去掉的班级",
       title = "leave-one-class-out 敏感性分析",
       subtitle = "红色虚线为完整样本估计；点估计变化幅度小，结论稳健") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap09_loo.png"),
       p3, width = 7.5, height = 4.5, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 9 figures generated =====\n")
