# =========================================================
# Chapter 3: 效应量及其方差的计算
# 在 dat.bcg 上计算 RR / OR / RD 三种效应量
# 生成三种效应量的 forest 对比图
# =========================================================

library(tidyverse)
library(metafor)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

# ---------- 读入数据 ----------
d <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)

# ---------- 用 escalc 计算三种效应量 ----------
es_rr <- escalc(measure = "RR",
                ai = tpos, bi = tneg, ci = cpos, di = cneg,
                data = d, append = FALSE)
es_or <- escalc(measure = "OR",
                ai = tpos, bi = tneg, ci = cpos, di = cneg,
                data = d, append = FALSE)
es_rd <- escalc(measure = "RD",
                ai = tpos, bi = tneg, ci = cpos, di = cneg,
                data = d, append = FALSE)

# 把三种效应量整理在一起
es_all <- d |>
  arrange(ablat) |>
  mutate(
    label = sprintf("%s (%d)", author, year),
    label = factor(label, levels = label)
  ) |>
  bind_cols(
    rr_yi = es_rr$yi[order(d$ablat)], rr_vi = es_rr$vi[order(d$ablat)],
    or_yi = es_or$yi[order(d$ablat)], or_vi = es_or$vi[order(d$ablat)],
    rd_yi = es_rd$yi[order(d$ablat)], rd_vi = es_rd$vi[order(d$ablat)]
  )

cat("\n===== 三种效应量的对比 =====\n")
print(es_all |>
  mutate(rr = round(exp(rr_yi), 3),
         or = round(exp(or_yi), 3),
         rd = round(rd_yi, 4)) |>
  select(trial, author, year, ablat, rr, or, rd) |>
  print(n = Inf))

# 算一些汇总数字给正文用
cat("\n===== 各研究 OR 和 RR 的差异（前 6 项）=====\n")
es_compare <- es_all |>
  mutate(rr = exp(rr_yi),
         or = exp(or_yi),
         diff_pct = (or - rr) / rr * 100) |>
  arrange(desc(abs(diff_pct))) |>
  select(author, year, rr, or, diff_pct) |>
  head(6) |>
  mutate(across(where(is.numeric), ~round(.x, 3)))
print(es_compare)

# ---------- 图：三种效应量的 forest 雏形（并列）----------
plot_long <- es_all |>
  pivot_longer(c(rr_yi, or_yi, rd_yi),
               names_to = "measure", values_to = "yi") |>
  pivot_longer(c(rr_vi, or_vi, rd_vi),
               names_to = "measure_v", values_to = "vi") |>
  filter(substr(measure, 1, 2) == substr(measure_v, 1, 2)) |>
  mutate(measure = recode(measure,
                          "rr_yi" = "log RR",
                          "or_yi" = "log OR",
                          "rd_yi" = "RD"),
         measure = factor(measure, levels = c("log RR", "log OR", "RD")),
         ci_low  = yi - 1.96 * sqrt(vi),
         ci_high = yi + 1.96 * sqrt(vi))

p <- ggplot(plot_long, aes(x = yi, y = label)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbar(aes(xmin = ci_low, xmax = ci_high),
                width = 0.2, color = "#4292C6") +
  geom_point(aes(size = 1 / vi), color = "#EF6548") +
  scale_size_continuous(range = c(1.2, 4), guide = "none") +
  facet_wrap(~ measure, scales = "free_x", nrow = 1) +
  labs(x = "效应量估计 (按纬度从低到高排)", y = NULL,
       title = "13 项 BCG 试验三种效应量并列展示") +
  theme_book(base_size = 10)

ggsave(here::here("figure", "chap03_three_effects.png"),
       p, width = 8.5, height = 4.5, dpi = 300, device = ragg::agg_png)

# ---------- 图：log OR 与 log RR 的散点对比 ----------
p2 <- ggplot(es_all, aes(x = rr_yi, y = or_yi)) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed",
              color = "gray50") +
  geom_point(size = 3, color = "#EF6548") +
  geom_text(aes(label = trial), nudge_x = 0.05, nudge_y = 0.05,
            size = 3, family = "Times New Roman") +
  labs(x = "log RR", y = "log OR",
       title = "log OR 与 log RR 的逐研究对比",
       subtitle = "虚线为 y=x；OR 通常比 RR 偏离零更远") +
  theme_book(base_size = 10)

ggsave(here::here("figure", "chap03_or_vs_rr.png"),
       p2, width = 6.5, height = 4.5, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 3 figures generated =====\n")
