# 01_explore_data.R —— 数据探索 + 朴素 DiD 图
# 产出：
#   figure/chap01_timeseries.png  CA vs 38 州时间序列
#   figure/chap01_did_box.png      CA 1988 在分布中的位置
#   figure/chap01_pre_correlation.png  1970-1988 趋势

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
  library(ragg)
  library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

smoking <- read.csv(here::here("data", "smoking.csv"))

# ===== 图 1：CA vs 38 州 cigsale 时间序列 =====
agg <- smoking |>
  mutate(group = ifelse(state == "California", "California", "其他 38 州")) |>
  group_by(group, year) |>
  summarise(cigsale = mean(cigsale, na.rm = TRUE), .groups = "drop")

p1 <- ggplot(agg, aes(x = year, y = cigsale, color = group, linetype = group)) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  annotate("text", x = 1989.3, y = 175, label = "Prop 99\n实施 1989",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.2) +
  geom_line(linewidth = 1.0) +
  scale_color_manual(values = c("California" = COLOR_TREAT,
                                "其他 38 州" = COLOR_DONOR)) +
  scale_linetype_manual(values = c("California" = "solid", "其他 38 州" = "dashed")) +
  scale_x_continuous(breaks = seq(1970, 2000, 5)) +
  scale_y_continuous(limits = c(40, 200), breaks = seq(40, 200, 30)) +
  labs(x = "年份",
       y = "人均香烟销量（packs / capita）",
       color = NULL, linetype = NULL) +
  theme_book()

ggsave(here::here("figure", "chap01_timeseries.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

cat("=== chap01 图 1 写入 ===\n")

# ===== 图 2：1988 加州在 39 州 cigsale 分布中的位置 =====
yr1988 <- smoking |> filter(year == 1988)
ca_val <- yr1988 |> filter(state == "California") |> pull(cigsale)

p2 <- ggplot(yr1988, aes(x = cigsale)) +
  geom_histogram(binwidth = 10, fill = COLOR_DONOR, color = "white", alpha = 0.7) +
  geom_vline(xintercept = ca_val, color = COLOR_TREAT, linewidth = 1.0) +
  annotate("text", x = ca_val + 4, y = 6,
           label = paste0("California\n", ca_val, " 包"),
           color = COLOR_TREAT, family = "Heiti TC", size = 3.4, hjust = 0) +
  scale_x_continuous(breaks = seq(50, 200, 25)) +
  labs(x = "1988 年人均香烟销量（packs / capita）",
       y = "州数") +
  theme_book()

ggsave(here::here("figure", "chap01_did_box.png"),
       p2, width = 6.5, height = 3.6, dpi = 300, device = ragg::agg_png)

cat("=== chap01 图 2 写入 ===\n")

# ===== 图 3：pre-period 1970-1988 CA 与 5 个相似州对比 =====
similar_states <- c("Connecticut", "Utah", "Nevada", "New Hampshire", "Idaho")
pre_dat <- smoking |>
  filter(year <= 1988, state %in% c("California", similar_states))

p3 <- ggplot(pre_dat, aes(x = year, y = cigsale, group = state, color = state)) +
  geom_line(linewidth = 0.7, alpha = 0.85) +
  scale_color_manual(values = c("California" = COLOR_TREAT,
                                "Connecticut" = "#7DA3C2",
                                "Utah" = "#A8C99E",
                                "Nevada" = "#C2A87D",
                                "New Hampshire" = "#9B9B9B",
                                "Idaho" = "#B27DB0")) +
  scale_x_continuous(breaks = seq(1970, 1988, 4)) +
  scale_y_continuous(limits = c(40, 200)) +
  labs(x = "年份", y = "人均香烟销量（packs / capita）", color = NULL) +
  theme_book()

ggsave(here::here("figure", "chap01_pre_correlation.png"),
       p3, width = 7, height = 4.0, dpi = 300, device = ragg::agg_png)

cat("=== chap01 图 3 写入 ===\n")
cat("\n图全部写入 figure/。 \n")
