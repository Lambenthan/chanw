# =========================================================
# Chapter 10: 方法对比与结论
# OLS / 二层 / 三层 / 加协变量 全景对比
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

# ---------- 全部七种方法 ----------
m_ols       <- lm(math ~ cltype, data = d)
m_ols_full  <- lm(math ~ cltype + sex_F + eth_B + ses_F, data = d)
m_2l        <- lmer(math ~ cltype + (1 | tch), data = d, REML = TRUE)
m_2l_full   <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | tch),
                    data = d, REML = TRUE)
m_3l        <- lmer(math ~ cltype + (1 | sch/tch), data = d, REML = TRUE)
m_3l_full   <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | sch/tch),
                    data = d, REML = TRUE)
m_3l_ix     <- lmer(math ~ cltype * ses_F + sex_F + eth_B + (1 | sch/tch),
                    data = d, REML = TRUE)

extract <- function(model, name, type = "lmer") {
  if (type == "lm") {
    co <- summary(model)$coefficients
    eff <- co["cltypesmall", "Estimate"]
    se  <- co["cltypesmall", "Std. Error"]
    p   <- co["cltypesmall", "Pr(>|t|)"]
    sig_resid <- summary(model)$sigma^2
    sig_class <- NA
    sig_sch   <- NA
  } else {
    co <- summary(model)$coefficients
    eff <- co["cltypesmall", "Estimate"]
    se  <- co["cltypesmall", "Std. Error"]
    p   <- co["cltypesmall", "Pr(>|t|)"]
    vc  <- as.data.frame(VarCorr(model))
    sig_resid <- vc$vcov[vc$grp == "Residual"]
    sig_class <- if (any(grepl("tch", vc$grp))) {
      vc$vcov[grepl("tch", vc$grp)][1]
    } else NA
    sig_sch   <- if ("sch" %in% vc$grp) vc$vcov[vc$grp == "sch"] else NA
  }
  tibble(
    method      = name,
    eff_small   = round(eff, 3),
    se_small    = round(se,  3),
    p_small     = round(p,   4),
    ci_lwr      = round(eff - 1.96 * se, 3),
    ci_upr      = round(eff + 1.96 * se, 3),
    sigma2_resid = round(sig_resid, 1),
    sigma2_class = round(sig_class, 1),
    sigma2_sch   = round(sig_sch,   1)
  )
}

results <- bind_rows(
  extract(m_ols,      "OLS：朴素", "lm"),
  extract(m_ols_full, "OLS：+ 学生协变量", "lm"),
  extract(m_2l,       "二层：(1|tch)"),
  extract(m_2l_full,  "二层：+ 学生协变量"),
  extract(m_3l,       "三层：(1|sch/tch)"),
  extract(m_3l_full,  "三层：+ 学生协变量"),
  extract(m_3l_ix,    "三层：+ 跨层交互")
)

cat("\n===== 七种方法的小班效应对比 =====\n")
print(results)

# ---------- AIC / BIC / logLik 比较（需要 ML 拟合）----------
m_2l_full_ml <- update(m_2l_full, REML = FALSE)
m_3l_full_ml <- update(m_3l_full, REML = FALSE)
fit_cmp <- tibble(
  method = c("二层：+ 学生协变量", "三层：+ 学生协变量"),
  AIC = c(AIC(m_2l_full_ml), AIC(m_3l_full_ml)),
  BIC = c(BIC(m_2l_full_ml), BIC(m_3l_full_ml)),
  logLik = c(as.numeric(logLik(m_2l_full_ml)),
             as.numeric(logLik(m_3l_full_ml)))
) |>
  mutate(across(AIC:logLik, ~ round(.x, 1)))

cat("\n===== AIC/BIC/logLik 比较（ML 拟合）=====\n")
print(fit_cmp)

# ---------- 图 10.1：终极森林图 ----------
forest_df <- results |>
  mutate(method = factor(method, levels = rev(method)))

p <- ggplot(forest_df, aes(y = method)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbar(aes(xmin = ci_lwr, xmax = ci_upr),
                width = 0.18, color = "#4292C6", linewidth = 0.7) +
  geom_point(aes(x = eff_small), size = 3.5, color = "#EF6548") +
  geom_text(aes(x = eff_small,
                label = sprintf("%.2f [%.2f, %.2f]",
                                eff_small, ci_lwr, ci_upr)),
            nudge_y = 0.27, size = 3.0, family = "Times New Roman") +
  labs(x = "小班相对常班的数学分数提升 (95% CI)",
       y = NULL,
       title = "全书方法对比：dat = star_k 上七种小班效应估计",
       subtitle = "OLS 与 HLM 的点估计接近 +8 分；CI 宽度差异主要来自标准误是否考虑嵌套") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap10_all_methods.png"),
       p, width = 9.0, height = 5.5, dpi = 300, device = ragg::agg_png)

# ---------- 图 10.2：方差分量比较（横向条形）----------
vc_df <- results |>
  filter(!is.na(sigma2_class)) |>
  select(method, sigma2_resid, sigma2_class, sigma2_sch) |>
  pivot_longer(c(sigma2_resid, sigma2_class, sigma2_sch),
               names_to = "level", values_to = "variance") |>
  filter(!is.na(variance)) |>
  mutate(level = factor(level,
                        levels = c("sigma2_sch",
                                   "sigma2_class",
                                   "sigma2_resid")),
         method = factor(method, levels = unique(method)))

p2 <- ggplot(vc_df, aes(x = method, y = variance, fill = level)) +
  geom_col(position = position_stack(reverse = TRUE), color = "white") +
  scale_fill_manual(
    values = c("sigma2_sch"   = "#08519C",
               "sigma2_class" = "#4292C6",
               "sigma2_resid" = "#9ECAE1"),
    labels = c("sigma2_sch"   = ts("σ²(school)"),
               "sigma2_class" = ts("σ²(class)"),
               "sigma2_resid" = ts("σ²(residual)"))
  ) +
  coord_flip() +
  labs(x = NULL, y = "方差分量",
       title = "不同模型的方差分配格局",
       subtitle = "二层把学校层方差并入班级层；三层把它独立出来",
       fill = NULL) +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap10_variance_compare.png"),
       p2, width = 8.5, height = 4.2, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 10 figures generated =====\n")
