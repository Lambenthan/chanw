# =========================================================
# Chapter 5: 班级层协变量与处理效应
# 把 cltype（处理）加进 Level-2，估计核心因果效应
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
         !is.na(sx), !is.na(eth), !is.na(ses), !is.na(exp)) |>
  mutate(
    sex_F     = ifelse(sx == "F", 1, 0),
    eth_B     = ifelse(eth == "B", 1, 0),
    ses_F     = ifelse(ses == "F", 1, 0),
    cltype    = factor(cltype, levels = c("reg", "reg+A", "small")),
    exp_c     = exp - mean(exp, na.rm = TRUE)         # 老师工龄中心化
  )

cat("\n样本量:", nrow(d), "  班级数:", length(unique(d$tch)), "\n")

# ---------- M4：仅班级层处理变量 cltype ----------
m4 <- lmer(math ~ cltype + (1 | tch), data = d, REML = TRUE)
cat("\n===== M4：cltype + (1|tch) =====\n")
print(summary(m4))

# ---------- M5：cltype + 学生协变量 ----------
m5 <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | tch),
           data = d, REML = TRUE)
cat("\n===== M5：cltype + 学生层协变量 =====\n")
print(summary(m5))

# ---------- M6：cltype + 学生协变量 + 教师工龄 ----------
m6 <- lmer(math ~ cltype + sex_F + eth_B + ses_F + exp_c + (1 | tch),
           data = d, REML = TRUE)
cat("\n===== M6：再加教师工龄 exp_c =====\n")
print(summary(m6))

# ---------- 提取处理效应进行对比 ----------
extract_treat <- function(model, name) {
  co <- summary(model)$coefficients
  tibble(
    model = name,
    eff_small  = round(co["cltypesmall",  "Estimate"], 3),
    se_small   = round(co["cltypesmall",  "Std. Error"], 3),
    p_small    = round(co["cltypesmall",  "Pr(>|t|)"], 4),
    eff_aide   = round(co["cltypereg+A",  "Estimate"], 3),
    se_aide    = round(co["cltypereg+A",  "Std. Error"], 3),
    p_aide     = round(co["cltypereg+A",  "Pr(>|t|)"], 4)
  )
}

# 朴素 OLS 的对应估计（参照）
ols <- lm(math ~ cltype, data = d)
co_ols <- summary(ols)$coefficients
ols_row <- tibble(
  model = "OLS：朴素无嵌套",
  eff_small = round(co_ols["cltypesmall", "Estimate"], 3),
  se_small  = round(co_ols["cltypesmall", "Std. Error"], 3),
  p_small   = round(co_ols["cltypesmall", "Pr(>|t|)"], 4),
  eff_aide  = round(co_ols["cltypereg+A", "Estimate"], 3),
  se_aide   = round(co_ols["cltypereg+A", "Std. Error"], 3),
  p_aide    = round(co_ols["cltypereg+A", "Pr(>|t|)"], 4)
)

cmp <- bind_rows(
  ols_row,
  extract_treat(m4, "M4：仅 cltype"),
  extract_treat(m5, "M5：+ 学生协变量"),
  extract_treat(m6, "M6：+ 教师工龄")
)
cat("\n===== 小班效应在不同模型里的稳定性 =====\n")
print(cmp)

# 方差分量变化
extract_vc <- function(model, name) {
  vc <- as.data.frame(VarCorr(model))
  tibble(
    model = name,
    sigma2_class = round(vc$vcov[vc$grp == "tch"], 2),
    sigma2_resid = round(vc$vcov[vc$grp == "Residual"], 2)
  )
}

# 基线参考：M3
m3 <- lmer(math ~ sex_F + eth_B + ses_F + (1 | tch), data = d, REML = TRUE)
vc_m3 <- as.data.frame(VarCorr(m3))
sigma2_class_m3  <- vc_m3$vcov[vc_m3$grp == "tch"]
sigma2_resid_m3  <- vc_m3$vcov[vc_m3$grp == "Residual"]

vc_cmp <- bind_rows(
  extract_vc(m3, "M3：学生协变量基线"),
  extract_vc(m4, "M4：+ cltype"),
  extract_vc(m5, "M5：+ cltype + 学生层"),
  extract_vc(m6, "M6：再 + 教师工龄")
) |>
  mutate(R2_class = round(1 - sigma2_class / sigma2_class_m3, 3))

cat("\n===== 班级层方差被 cltype 解释了多少？=====\n")
print(vc_cmp)

# ---------- 图 5.1：处理效应的森林图（OLS vs HLM 系列）----------
forest_df <- cmp |>
  mutate(model = factor(model, levels = rev(model)))

p1 <- ggplot(forest_df, aes(y = model)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbar(aes(xmin = eff_small - 1.96 * se_small,
                    xmax = eff_small + 1.96 * se_small),
                width = 0.18, color = "#4292C6", linewidth = 0.7) +
  geom_point(aes(x = eff_small), size = 3.5, color = "#EF6548") +
  geom_text(aes(x = eff_small,
                label = sprintf("%.2f (SE=%.2f)", eff_small, se_small)),
            nudge_y = 0.25, size = 3.2, family = "Times New Roman") +
  labs(x = "小班相对常班的数学分数提升 (95% CI)", y = NULL,
       title = "小班效应在不同模型设定下的稳定性",
       subtitle = "点估计在 OLS 和 HLM 之间几乎不变；CI 宽度差异显著") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap05_treatment_forest.png"),
       p1, width = 8.0, height = 4.0, dpi = 300, device = ragg::agg_png)

# ---------- 图 5.2：班级 BLUP（M4） vs 班级 BLUP（M5）----------
re_m4 <- ranef(m4)$tch
re_m5 <- ranef(m5)$tch

blup_df <- tibble(
  tch = rownames(re_m4),
  blup_m4 = re_m4[, 1],
  blup_m5 = re_m5[, 1]
)

p2 <- ggplot(blup_df, aes(x = blup_m4, y = blup_m5)) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed",
              color = "gray50") +
  geom_point(color = "#4292C6", alpha = 0.6, size = 1.5) +
  labs(x = "班级 BLUP（M4：仅 cltype）",
       y = "班级 BLUP（M5：+ 学生协变量）",
       title = "加入学生层协变量后的班级 BLUP 收缩",
       subtitle = "学生背景能解释一部分班间差异，BLUP 围绕 0 收紧") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap05_blup_compare.png"),
       p2, width = 6.5, height = 4.5, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 5 figures generated =====\n")
