# =========================================================
# Chapter 8: 三层模型 —— 学生 / 班级 / 学校
# 把 sch 加进 Level-3，分解三层方差
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

# ---------- 三层空模型 ----------
m0_3l <- lmer(math ~ 1 + (1 | sch/tch), data = d, REML = TRUE)
cat("\n===== 三层空模型 =====\n")
print(summary(m0_3l))

vc <- as.data.frame(VarCorr(m0_3l))
sigma2_class <- vc$vcov[vc$grp == "tch:sch"]
sigma2_sch   <- vc$vcov[vc$grp == "sch"]
sigma2_resid <- vc$vcov[vc$grp == "Residual"]
total <- sigma2_class + sigma2_sch + sigma2_resid

icc_class    <- sigma2_class / total
icc_sch      <- sigma2_sch   / total
icc_within   <- sigma2_resid / total

cat("\n===== 三层方差分解 =====\n")
cat("σ²(school)   =", round(sigma2_sch,   2), "  ICC =", round(icc_sch * 100,   2), "%\n")
cat("σ²(class)    =", round(sigma2_class, 2), "  ICC =", round(icc_class * 100, 2), "%\n")
cat("σ²(residual) =", round(sigma2_resid, 2), "  ICC =", round(icc_within * 100, 2), "%\n")
cat("总方差        =", round(total, 2), "\n")

# ---------- 三层模型 + 处理效应 + 学生协变量 ----------
m_3l_full <- lmer(math ~ cltype + sex_F + eth_B + ses_F +
                    (1 | sch/tch),
                  data = d, REML = TRUE)
cat("\n===== 三层 + 全部协变量 =====\n")
print(summary(m_3l_full))

# ---------- 二层 vs 三层：处理效应对比 ----------
m_2l_full <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | tch),
                  data = d, REML = TRUE)

extract_treat <- function(model, name) {
  co <- summary(model)$coefficients
  vc <- as.data.frame(VarCorr(model))
  has_sch <- "sch" %in% vc$grp
  tibble(
    model = name,
    eff_small = round(co["cltypesmall", "Estimate"], 3),
    se_small  = round(co["cltypesmall", "Std. Error"], 3),
    p_small   = round(co["cltypesmall", "Pr(>|t|)"], 4),
    sigma2_class    = round(vc$vcov[grepl("tch", vc$grp)][1], 2),
    sigma2_sch      = if (has_sch) round(vc$vcov[vc$grp == "sch"], 2) else NA,
    sigma2_resid    = round(vc$vcov[vc$grp == "Residual"], 2)
  )
}

cmp <- bind_rows(
  extract_treat(m_2l_full, "二层：(1|tch)"),
  extract_treat(m_3l_full, "三层：(1|sch/tch)")
)
cat("\n===== 二层 vs 三层 模型对比 =====\n")
print(cmp)

# 学校层方差消失到哪去了？方差分解
vc_2l <- as.data.frame(VarCorr(m_2l_full))
vc_3l <- as.data.frame(VarCorr(m_3l_full))

cat("\n===== 二层模型把学校层方差混进了班级层 =====\n")
cat("二层 σ²(class) =",  round(vc_2l$vcov[vc_2l$grp == "tch"], 2),     "\n")
cat("三层 σ²(class) =",  round(vc_3l$vcov[vc_3l$grp == "tch:sch"], 2), "\n")
cat("三层 σ²(school) =", round(vc_3l$vcov[vc_3l$grp == "sch"], 2),    "\n")
cat("二层 ≈ 三层(class) + 三层(school) =",
    round(vc_3l$vcov[vc_3l$grp == "tch:sch"] +
          vc_3l$vcov[vc_3l$grp == "sch"], 2), "\n")

# ---------- LRT：三层 vs 二层 ----------
m_2l_ml <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | tch),
                data = d, REML = FALSE)
m_3l_ml <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | sch/tch),
                data = d, REML = FALSE)
lrt <- anova(m_2l_ml, m_3l_ml)
cat("\n===== LRT：三层是否优于二层？=====\n")
print(lrt)

# ---------- 图 8.1：三层方差分解条形图 ----------
var_df <- tibble(
  level = c("resid", "class", "school"),
  variance = c(sigma2_resid, sigma2_class, sigma2_sch)
) |>
  mutate(level = factor(level, levels = c("resid", "class", "school")),
         pct = variance / sum(variance) * 100)

p1 <- ggplot(var_df, aes(x = "", y = variance, fill = level)) +
  geom_col(color = "white", width = 0.6) +
  geom_text(aes(label = sprintf("%.1f\n(%.1f%%)", variance, pct)),
            position = position_stack(vjust = 0.5),
            family = "Times New Roman", color = "white", size = 4.0) +
  scale_fill_manual(
    values = c("resid"  = "#9ECAE1",
               "class"  = "#4292C6",
               "school" = "#08519C"),
    labels = c("resid"  = paste0("学生层 ", ts("σ²(residual)")),
               "class"  = paste0("班级层 ", ts("σ²(class)")),
               "school" = paste0("学校层 ", ts("σ²(school)")))
  ) +
  coord_flip() +
  labs(x = NULL, y = "方差分量",
       title = "三层方差分解：学校 / 班级 / 学生层各占多少？",
       fill = NULL) +
  theme_book(base_size = 11) +
  theme(legend.position = "bottom")

ggsave(here::here("figure", "chap08_three_level_pie.png"),
       p1, width = 8.0, height = 3.0, dpi = 300, device = ragg::agg_png)

# ---------- 图 8.2：学校 BLUP 分布 ----------
re_3l <- ranef(m_3l_full)
school_blup <- tibble(
  sch  = rownames(re_3l$sch),
  blup = re_3l$sch[, "(Intercept)"]
) |>
  arrange(blup) |>
  mutate(rank = row_number())

p2 <- ggplot(school_blup, aes(x = rank, y = blup)) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray50") +
  geom_point(size = 1.6, color = "#08519C") +
  geom_segment(aes(xend = rank, y = 0, yend = blup),
               color = "#08519C", alpha = 0.4, linewidth = 0.3) +
  labs(x = "学校（按 BLUP 排序）", y = "学校 BLUP（相对全样本均值）",
       title = "79 所学校的随机截距 BLUP",
       subtitle = "学校之间的真实平均水平差异（已扣除班级与学生层效应）") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap08_school_blup.png"),
       p2, width = 7.5, height = 4.0, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 8 figures generated =====\n")
