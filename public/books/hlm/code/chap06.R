# =========================================================
# Chapter 6: 随机斜率与协变结构
# 让 ses_F 的斜率在班级间随机变化 + LRT 检验
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

# ---------- M5（参照）：仅随机截距 ----------
m5 <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | tch),
           data = d, REML = TRUE)

# ---------- M7：ses_F 的斜率在班级间随机变化（无相关）----------
m7 <- lmer(math ~ cltype + sex_F + eth_B + ses_F +
             (1 + ses_F || tch), data = d, REML = TRUE)
cat("\n===== M7：random intercept + random slope (ses_F) =====\n")
print(summary(m7))

# ---------- M8：放开截距与斜率的相关 ----------
m8 <- lmer(math ~ cltype + sex_F + eth_B + ses_F +
             (1 + ses_F | tch), data = d, REML = TRUE)
cat("\n===== M8：random intercept + slope + 相关 =====\n")
print(summary(m8))

# ---------- LRT：随机斜率有没有显著改善模型？----------
cat("\n===== LRT 检验：M5 vs M7 =====\n")
# 注意：LRT 检验方差成分时，p 值要除以 2（或用 RLRsim 包），这里给原始 χ²
m5_ml <- lmer(math ~ cltype + sex_F + eth_B + ses_F + (1 | tch),
              data = d, REML = FALSE)
m7_ml <- lmer(math ~ cltype + sex_F + eth_B + ses_F +
                (1 + ses_F || tch), data = d, REML = FALSE)
lrt_57 <- anova(m5_ml, m7_ml)
print(lrt_57)

# ---------- 提取斜率的分布 ----------
ranef_m7 <- ranef(m7)$tch
cat("\n===== 班级层 ses_F 斜率分布 =====\n")
cat("斜率 BLUP 的均值（应接近 0）:", round(mean(ranef_m7$ses_F), 3), "\n")
cat("斜率 BLUP 的 SD:",                round(sd(ranef_m7$ses_F),   3), "\n")

# 固定效应的 SES 斜率
slope_fixed <- summary(m7)$coefficients["ses_F", "Estimate"]
cat("固定 SES 斜率（全班级平均）:",     round(slope_fixed, 2), "\n")

# 解读：斜率 SD 相对于固定效应有多大？
sd_ranef_slope <- sd(ranef_m7$ses_F)
cat("斜率个班 SD / 固定斜率 = ",
    round(abs(sd_ranef_slope / slope_fixed), 2), "倍\n")

# ---------- 图 6.1：随机斜率的可视化（spaghetti plot）----------
# 抽 30 个班级展示其内部 SES → math 的拟合直线
class_summary <- d |>
  group_by(tch) |>
  summarise(n_F = sum(ses_F == 1), n_N = sum(ses_F == 0),
            n = n(), .groups = "drop") |>
  filter(n >= 10, n_F >= 2, n_N >= 2)   # 班里至少有两类 SES 学生

set.seed(2026)
sampled_tch <- class_summary |>
  slice_sample(n = 30) |>
  pull(tch)

# 每个班的截距 + 斜率
re_full <- ranef(m7)$tch
fixed_int <- fixef(m7)["(Intercept)"]
fixed_slope <- fixef(m7)["ses_F"]

class_lines <- tibble(
  tch = rownames(re_full),
  intercept = fixed_int + re_full[, "(Intercept)"],
  slope     = fixed_slope + re_full[, "ses_F"]
) |>
  filter(tch %in% as.character(sampled_tch))

# 画线：x 从 0 到 1（ses_F 是 0/1），y = intercept + slope * x
plot_lines <- class_lines |>
  rowwise() |>
  do(tibble(tch = .$tch,
            x   = c(0, 1),
            y   = .$intercept + .$slope * c(0, 1))) |>
  ungroup()

p1 <- ggplot(plot_lines, aes(x = x, y = y, group = tch)) +
  geom_line(color = "#4292C6", alpha = 0.45, linewidth = 0.4) +
  geom_abline(intercept = fixed_int, slope = fixed_slope,
              color = "#EF6548", linewidth = 1.0) +
  scale_x_continuous(breaks = c(0, 1),
                     labels = c(paste0("非低 ", ts("SES (N)")),
                                paste0("低 ",   ts("SES (F)")))) +
  labs(x = paste0("学生 ", ts("SES")), y = "数学分数",
       title = paste0("30 个随机抽取的班级：班内 ",
                      ts("SES"), " 与 ", ts("math"), " 的关系"),
       subtitle = "每条蓝线一个班；红线为全班级平均；斜率班际差异有限") +
  theme_book(base_size = 11) +
  theme(axis.text.x = ggtext::element_markdown(family = "Heiti TC"))

ggsave(here::here("figure", "chap06_spaghetti.png"),
       p1, width = 7.5, height = 4.5, dpi = 300, device = ragg::agg_png)

# ---------- 图 6.2：斜率 BLUP 的分布 ----------
slope_df <- tibble(
  tch   = rownames(ranef_m7),
  slope = ranef_m7$ses_F + slope_fixed
)

p2 <- ggplot(slope_df, aes(x = slope)) +
  geom_histogram(bins = 25, fill = "#4292C6", color = "white", alpha = 0.85) +
  geom_vline(xintercept = slope_fixed,
             color = "#EF6548", linetype = "dashed", linewidth = 0.7) +
  labs(x = paste0("班级层估计的 ", ts("SES"), " 斜率"), y = "班级数",
       title = paste0("随机斜率分布：班级层 ", ts("SES"), " 效应的异质性"),
       subtitle = paste0("固定斜率 ", ts(sprintf("%.2f", slope_fixed)),
                         "；班际 ", ts(sprintf("SD %.2f", sd_ranef_slope)))) +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap06_slope_dist.png"),
       p2, width = 6.5, height = 4.0, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 6 figures generated =====\n")
