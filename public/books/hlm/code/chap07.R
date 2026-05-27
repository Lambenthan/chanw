# =========================================================
# Chapter 7: 跨层交互
# 班级层 cltype × 学生层 ses_F：小班对低 SES 学生的额外作用？
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

# ---------- M9：跨层交互 cltype × ses_F ----------
m9 <- lmer(math ~ cltype * ses_F + sex_F + eth_B + (1 | tch),
           data = d, REML = TRUE)
cat("\n===== M9：cltype × ses_F 跨层交互 =====\n")
print(summary(m9))

# 主效应 + 交互项
co <- summary(m9)$coefficients
cat("\n===== 关键系数 =====\n")
print(round(co, 4))

# ---------- 估计四种"班级类型 × SES"组合下的预测均值 ----------
# 简化：固定 sex_F 和 eth_B 在样本均值
sex_mean <- mean(d$sex_F)
eth_mean <- mean(d$eth_B)

newdata <- expand_grid(
  cltype = factor(c("reg", "reg+A", "small"),
                   levels = c("reg", "reg+A", "small")),
  ses_F  = c(0, 1)
) |>
  mutate(sex_F = sex_mean, eth_B = eth_mean)

# 用 fixed effects 算 + se
mm <- model.matrix(~ cltype * ses_F + sex_F + eth_B, data = newdata)
beta <- fixef(m9)
V <- vcov(m9)

newdata <- newdata |>
  mutate(
    pred = as.numeric(mm %*% beta),
    se   = sqrt(diag(mm %*% V %*% t(mm))),
    lwr  = pred - 1.96 * se,
    upr  = pred + 1.96 * se,
    ses_label = ifelse(ses_F == 1, "low", "high")
  )

cat("\n===== 预测均值（固定其他协变量在样本平均）=====\n")
print(newdata |> select(cltype, ses_label, pred, se, lwr, upr) |>
        mutate(across(pred:upr, ~ round(.x, 2))))

# 计算"小班相对常班"的效应在两类 SES 下分别多大
small_minus_reg_low <- newdata$pred[newdata$cltype == "small" & newdata$ses_F == 1] -
                       newdata$pred[newdata$cltype == "reg"   & newdata$ses_F == 1]
small_minus_reg_high <- newdata$pred[newdata$cltype == "small" & newdata$ses_F == 0] -
                        newdata$pred[newdata$cltype == "reg"   & newdata$ses_F == 0]

cat("\n小班 - 常班（低 SES 学生）  =", round(small_minus_reg_low, 2), "分\n")
cat("小班 - 常班（非低 SES 学生）=", round(small_minus_reg_high, 2), "分\n")

# 交互项的统计显著性
ix_p <- co["cltypesmall:ses_F", "Pr(>|t|)"]
cat("交互项 cltypesmall:ses_F 的 p 值 =", round(ix_p, 4), "\n")

# ---------- 图 7.1：四种情形下的预测分数（带 CI）----------
p1 <- ggplot(newdata, aes(x = cltype, y = pred,
                          color = ses_label, group = ses_label)) +
  geom_line(linewidth = 0.8, position = position_dodge(0.15)) +
  geom_errorbar(aes(ymin = lwr, ymax = upr),
                width = 0.12, linewidth = 0.6,
                position = position_dodge(0.15)) +
  geom_point(size = 3.5, position = position_dodge(0.15)) +
  scale_color_manual(
    values = c("low" = "#EF6548", "high" = "#4292C6"),
    labels = c("low"  = paste0("低 ",   ts("SES (F)")),
               "high" = paste0("非低 ", ts("SES (N)")))
  ) +
  scale_x_discrete(labels = c("reg"   = ts("reg"),
                              "reg+A" = ts("reg+A"),
                              "small" = ts("small"))) +
  labs(x = "班级类型", y = "预测数学分数",
       title = paste0("班级类型 × 学生 ", ts("SES"), " 的跨层交互"),
       subtitle = paste0("两条线如果平行，说明小班效应不依赖 ",
                         ts("SES"), "；本数据下接近平行"),
       color = NULL) +
  theme_book(base_size = 11) +
  theme(axis.text.x = ggtext::element_markdown())

ggsave(here::here("figure", "chap07_interaction.png"),
       p1, width = 7.5, height = 4.5, dpi = 300, device = ragg::agg_png)

# ---------- 图 7.2：交互项系数与 95% CI（强制对比）----------
ix_terms <- c("cltypereg+A:ses_F", "cltypesmall:ses_F")
ix_df <- tibble(
  term  = ix_terms,
  est   = co[ix_terms, "Estimate"],
  se    = co[ix_terms, "Std. Error"],
  p     = co[ix_terms, "Pr(>|t|)"]
) |>
  mutate(lwr = est - 1.96 * se,
         upr = est + 1.96 * se,
         label = c(paste0("常班+助教 × 低 ", ts("SES")),
                   paste0("小班 × 低 ",      ts("SES"))))

ix_df$label <- factor(ix_df$label, levels = ix_df$label)

p2 <- ggplot(ix_df, aes(y = label, x = est)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbarh(aes(xmin = lwr, xmax = upr),
                 height = 0.18, color = "#4292C6", linewidth = 0.7) +
  geom_point(size = 4, color = "#EF6548") +
  geom_text(aes(label = sprintf("β = %.2f, p = %.3f", est, p)),
            nudge_y = 0.22, size = 3.3, family = "Times New Roman") +
  labs(x = paste0("跨层交互系数 ", ts("β (95% CI)")), y = NULL,
       title = paste0("跨层交互项系数：班级类型对 ", ts("SES"), " 效应的调节"),
       subtitle = paste0("CI 跨过 0 表示交互不显著；本数据中均不显著")) +
  theme_book(base_size = 11) +
  theme(axis.text.y = ggtext::element_markdown(family = "Heiti TC"))

ggsave(here::here("figure", "chap07_interaction_coef.png"),
       p2, width = 7.0, height = 3.5, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 7 figures generated =====\n")
