# =========================================================
# Chapter 1: 问题与数据 —— BCG 疫苗与全球结核
# 数据：metafor::dat.bcg（13 项 RCT，1948-1980）
# =========================================================

library(tidyverse)
library(metafor)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

# ---------- 数据读入 ----------
d <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)
cat("数据维度: ", dim(d), "\n")
print(d)

# 计算每个研究的事件率（每千人）和总样本量
d <- d |>
  mutate(
    n_t = tpos + tneg,                    # 处理组样本量
    n_c = cpos + cneg,                    # 对照组样本量
    rate_t = tpos / n_t * 1000,           # 处理组事件率（千分之）
    rate_c = cpos / n_c * 1000,           # 对照组事件率（千分之）
    rr     = (tpos / n_t) / (cpos / n_c)  # 风险比
  )

# ---------- 描述性数字 ----------
cat("\n总样本量: ", sum(d$n_t + d$n_c), "\n")
cat("处理组累计事件: ", sum(d$tpos), " / ", sum(d$n_t), "\n")
cat("对照组累计事件: ", sum(d$cpos), " / ", sum(d$n_c), "\n")
cat("纬度范围: ", range(d$ablat), "\n")
cat("年份范围: ", range(d$year), "\n")

# ---------- 朴素汇总：直接把 13 个 2x2 表加起来 ----------
total_tpos <- sum(d$tpos); total_tneg <- sum(d$tneg)
total_cpos <- sum(d$cpos); total_cneg <- sum(d$cneg)

p_t_pool <- total_tpos / (total_tpos + total_tneg)
p_c_pool <- total_cpos / (total_cpos + total_cneg)
naive_rr <- p_t_pool / p_c_pool
naive_logrr <- log(naive_rr)
cat("\n朴素合并风险比: ", round(naive_rr, 3), "  log RR: ", round(naive_logrr, 3), "\n")
cat("朴素合并：处理组发病率 ", round(p_t_pool * 1000, 2), "‰，对照组发病率 ",
    round(p_c_pool * 1000, 2), "‰\n", sep = "")

# ---------- 用 metafor 算每个研究的 log RR 和方差 ----------
es <- escalc(measure = "RR",
             ai = tpos, bi = tneg, ci = cpos, di = cneg,
             data = d, append = TRUE)
cat("\n各研究 log RR 与方差:\n")
print(es |> select(trial, author, year, ablat, yi, vi) |>
        mutate(yi = round(yi, 3), vi = round(vi, 4)))

# ---------- 图 1：13 项研究事件率对比（按纬度排序）----------
plot_df <- d |>
  arrange(ablat) |>
  mutate(label = sprintf("%s (%d, %d°)", author, year, ablat),
         label = factor(label, levels = label)) |>
  pivot_longer(c(rate_t, rate_c), names_to = "arm", values_to = "rate") |>
  mutate(arm = factor(arm, levels = c("rate_c", "rate_t"),
                      labels = c("对照组", "BCG 组")))

p1 <- ggplot(plot_df, aes(x = rate, y = label, color = arm)) +
  geom_line(aes(group = label), color = "gray70", linewidth = 0.4) +
  geom_point(size = 2.4) +
  scale_color_manual(values = c("对照组" = "#4292C6", "BCG 组" = "#EF6548")) +
  labs(x = "结核发病率（每千人）", y = NULL, color = NULL,
       title = "13 项 BCG 试验的事件率（按纬度从低到高排序）") +
  theme_book(base_size = 11) +
  theme(legend.position = "top")

ggsave(here::here("figure", "chap01_event_rates.png"),
       p1, width = 7.2, height = 4.8, dpi = 300, device = ragg::agg_png)

# ---------- 图 2：13 项研究的各自 log RR（雏形 forest）----------
es <- es |>
  mutate(ci_low  = yi - 1.96 * sqrt(vi),
         ci_high = yi + 1.96 * sqrt(vi),
         label   = sprintf("%s (%d)", author, year),
         label   = factor(label, levels = label[order(ablat)]))

p2 <- ggplot(es, aes(x = yi, y = label)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbarh(aes(xmin = ci_low, xmax = ci_high), height = 0.2,
                 color = "#4292C6") +
  geom_point(aes(size = 1 / vi), color = "#EF6548") +
  scale_size_continuous(range = c(1.5, 5), guide = "none") +
  labs(x = "log Risk Ratio（< 0 表示 BCG 有保护作用）", y = NULL,
       title = "13 项试验各自的 log RR 与 95% CI（按纬度排序）") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap01_naive_logrr.png"),
       p2, width = 7.2, height = 4.8, dpi = 300, device = ragg::agg_png)

# ---------- 图 3：log RR 对纬度的散点 ----------
p3 <- ggplot(es, aes(x = ablat, y = yi)) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray50") +
  geom_smooth(method = "lm", se = TRUE, color = "#EF6548",
              fill = "#EF6548", alpha = 0.15, linewidth = 0.6) +
  geom_point(aes(size = 1 / vi), color = "#4292C6") +
  scale_size_continuous(range = c(2, 6), guide = "none") +
  labs(x = "试验地点的绝对纬度（度）",
       y = "log Risk Ratio",
       title = "纬度越高，BCG 的保护作用越强") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap01_latitude_scatter.png"),
       p3, width = 6.8, height = 4.4, dpi = 300, device = ragg::agg_png)

# ---------- 简单线性回归 log RR ~ 纬度 ----------
fit_lat <- lm(yi ~ ablat, data = es, weights = 1 / vi)
cat("\nlog RR ~ 纬度 加权回归:\n")
print(summary(fit_lat))

cat("\n===== Chapter 1 数据准备完毕 =====\n")
