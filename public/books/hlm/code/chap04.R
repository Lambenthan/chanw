# =========================================================
# Chapter 4: 学生层协变量与组内/组间分解
# 把性别、族裔、SES 加进 Level-1，理解中心化
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
    sex_F   = ifelse(sx == "F", 1, 0),
    eth_B   = ifelse(eth == "B", 1, 0),    # 黑人哑变量
    ses_F   = ifelse(ses == "F", 1, 0)     # 免费午餐 = 低 SES
  )

cat("\n样本量（学生层协变量去 NA 后）:", nrow(d), "\n")
cat("学生数（应该等于行数）:", length(unique(d$id)), "\n")
cat("班级数:", length(unique(d$tch)), "\n")
cat("学校数:", length(unique(d$sch)), "\n")

# ---------- 模型 0：空模型（基线参考）----------
m0 <- lmer(math ~ 1 + (1 | tch), data = d, REML = TRUE)
vc0 <- as.data.frame(VarCorr(m0))
sigma2_class_0  <- vc0$vcov[vc0$grp == "tch"]
sigma2_resid_0  <- vc0$vcov[vc0$grp == "Residual"]
icc_0 <- sigma2_class_0 / (sigma2_class_0 + sigma2_resid_0)

# ---------- 模型 1：加入学生性别 ----------
m1 <- lmer(math ~ sex_F + (1 | tch), data = d, REML = TRUE)
cat("\n===== 模型 1：加 sex_F =====\n")
print(summary(m1))

# ---------- 模型 2：加入学生族裔（黑人哑变量）----------
m2 <- lmer(math ~ sex_F + eth_B + (1 | tch), data = d, REML = TRUE)
cat("\n===== 模型 2：加 eth_B =====\n")
print(summary(m2))

# ---------- 模型 3：加入 SES（免费午餐）----------
m3 <- lmer(math ~ sex_F + eth_B + ses_F + (1 | tch), data = d, REML = TRUE)
cat("\n===== 模型 3：加 ses_F =====\n")
print(summary(m3))

# 比较各模型的方差分量
extract_vc <- function(mod, name) {
  vc <- as.data.frame(VarCorr(mod))
  aic_val <- AIC(mod)
  bic_val <- BIC(mod)
  tibble(
    model    = name,
    sigma2_class = round(vc$vcov[vc$grp == "tch"], 2),
    sigma2_resid = round(vc$vcov[vc$grp == "Residual"], 2),
    AIC      = round(aic_val, 1),
    BIC      = round(bic_val, 1)
  )
}

cmp <- bind_rows(
  extract_vc(m0, "M0：空模型"),
  extract_vc(m1, "M1：加 sex_F"),
  extract_vc(m2, "M2：加 eth_B"),
  extract_vc(m3, "M3：加 ses_F")
) |>
  mutate(
    R2_within = round(1 - sigma2_resid / sigma2_resid_0, 3),
    R2_between = round(1 - sigma2_class / sigma2_class_0, 3)
  )

cat("\n===== 学生层协变量加入后的方差变化 =====\n")
print(cmp)

# ---------- 中心化演示：组均值中心化 vs 总均值中心化 ----------
# 用 SES 作为示例：F (low SES) = 1, N = 0
# 算每个班的 SES 比例（class-mean SES）
d_cent <- d |>
  group_by(tch) |>
  mutate(ses_class = mean(ses_F)) |>
  ungroup() |>
  mutate(ses_within = ses_F - ses_class)   # 组内偏差

# 组均值中心化模型
m_cmc <- lmer(math ~ ses_within + ses_class + (1 | tch),
              data = d_cent, REML = TRUE)
cat("\n===== 组均值中心化（CMC）：分离班内 SES 与班间 SES 效应 =====\n")
print(summary(m_cmc))

# 普通模型（不分解）
m_plain <- lmer(math ~ ses_F + (1 | tch), data = d_cent, REML = TRUE)

cmc_within  <- summary(m_cmc)$coefficients["ses_within", "Estimate"]
cmc_between <- summary(m_cmc)$coefficients["ses_class",  "Estimate"]
plain_ses   <- summary(m_plain)$coefficients["ses_F",     "Estimate"]

cat("\n班内 SES 效应（学生层）=",      round(cmc_within, 2), "\n")
cat("班间 SES 效应（班级层）=",      round(cmc_between, 2), "\n")
cat("不分解的混合系数 =",            round(plain_ses, 2), "\n")
cat("注意班间效应远大于班内效应 =>  低 SES 学生集中的班级整体表现更差\n")

# ---------- 图 4.1：方差分量随协变量加入的变化 ----------
plot_df <- cmp |>
  pivot_longer(c(sigma2_class, sigma2_resid),
               names_to = "level", values_to = "variance") |>
  mutate(level = factor(level, levels = c("sigma2_class", "sigma2_resid")),
         model = factor(model, levels = unique(cmp$model)))

p1 <- ggplot(plot_df, aes(x = model, y = variance, fill = level)) +
  geom_col(position = position_stack(reverse = TRUE), color = "white") +
  scale_fill_manual(
    values = c("sigma2_class" = "#EF6548", "sigma2_resid" = "#4292C6"),
    labels = c("sigma2_class" = paste0("班级间 ", ts("σ²(class)")),
               "sigma2_resid" = paste0("班级内 ", ts("σ²(residual)")))
  ) +
  geom_text(aes(label = round(variance, 0)),
            position = position_stack(vjust = 0.5, reverse = TRUE),
            family = "Times New Roman", color = "white", size = 3.4) +
  labs(x = NULL, y = "方差分量",
       title = "学生层协变量逐步加入后的方差变化",
       subtitle = "学生层变量主要降低班级内方差，对班级间方差影响有限",
       fill = NULL) +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap04_var_progress.png"),
       p1, width = 8.0, height = 4.2, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 4 figures generated =====\n")
