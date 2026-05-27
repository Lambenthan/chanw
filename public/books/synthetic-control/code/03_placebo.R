# 03_placebo.R —— In-space Placebo + In-time Placebo
# In-space placebo: 把每个 donor 当 "假处理州" 跑一遍 SC，看 gap 分布
# In-time placebo: 把 treatment 年改为 1980（提前 9 年），看是否检出虚假效应
# 产出：
#   figure/chap03_placebo_inspace.png   38 条假处理 gap + CA 真实 gap
#   figure/chap03_rmspe_ratio.png       RMSPE 比值排序
#   figure/chap03_intime_placebo.png    In-time placebo（treatment=1980）

suppressPackageStartupMessages({
  library(tidyverse)
  library(tidysynth)
  library(here)
  library(ragg)
  library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

sc_out <- readRDS(here::here("data", "sc_out_classic.rds"))

# === In-space placebo: 提取所有 placebo gaps ===
all_gaps <- sc_out |> grab_synthetic_control(placebo = TRUE) |>
  mutate(gap = real_y - synth_y,
         is_ca = .placebo == 0)

# === 图 1：In-space placebo gap ===
p1 <- ggplot() +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  geom_line(data = all_gaps |> filter(!is_ca),
            aes(x = time_unit, y = gap, group = .id),
            color = "gray70", alpha = 0.6, linewidth = 0.35) +
  geom_line(data = all_gaps |> filter(is_ca),
            aes(x = time_unit, y = gap),
            color = COLOR_TREAT, linewidth = 1.0) +
  annotate("text", x = 1999, y = -50, label = "California 真实", color = COLOR_TREAT,
           family = "Heiti TC", size = 3.3, hjust = 1) +
  annotate("text", x = 1972, y = -50, label = "38 个 placebo 州", color = "gray45",
           family = "Heiti TC", size = 3.3, hjust = 0) +
  scale_x_continuous(breaks = seq(1970, 2000, 5)) +
  labs(x = "年份",
       y = "Gap（实际 − 合成）") +
  theme_book()
ggsave(here::here("figure", "chap03_placebo_inspace.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

# === 图 2：RMSPE ratio 排序 + CA 排名 ===
sig_tab <- sc_out |> grab_significance(time_window = 1989:2000)
cat("=== RMSPE ratio 排序 (top + bottom) ===\n")
print(sig_tab |> arrange(desc(mspe_ratio)) |> head(10))
ca_rank <- which(sig_tab$unit_name[order(-sig_tab$mspe_ratio)] == "California")
n_states <- nrow(sig_tab)
exact_p <- ca_rank / n_states
cat("California rank   :", ca_rank, "/", n_states, "\n")
cat("Exact p-value     :", round(exact_p, 4), "\n")

p2 <- sig_tab |>
  mutate(is_ca = unit_name == "California",
         label = ifelse(is_ca, "California", NA)) |>
  arrange(desc(mspe_ratio)) |>
  mutate(rk = row_number()) |>
  ggplot(aes(x = rk, y = mspe_ratio, fill = is_ca)) +
  geom_col(width = 0.85, alpha = 0.92) +
  geom_text(aes(label = label),
           vjust = -0.4, family = "Heiti TC", size = 3.4, color = COLOR_TREAT,
           na.rm = TRUE) +
  scale_fill_manual(values = c("FALSE" = COLOR_DONOR, "TRUE" = COLOR_TREAT), guide = "none") +
  labs(x = "州（按 RMSPE 比值降序）", y = "post / pre RMSPE 比值") +
  theme_book()
ggsave(here::here("figure", "chap03_rmspe_ratio.png"),
       p2, width = 7, height = 3.8, dpi = 300, device = ragg::agg_png)

# === In-time placebo: treatment_year = 1980 ===
smoking <- read.csv(here::here("data", "smoking.csv"))
sc_intime <- smoking |>
  filter(year <= 1988) |>  # 只用 1970-1988 数据，模拟 "如果当年 Prop 99 是 1980 颁布"
  synthetic_control(outcome = cigsale, unit = state, time = year,
                    i_unit = "California", i_time = 1980,
                    generate_placebos = FALSE) |>
  generate_predictor(time_window = 1970:1979,
                     ln_income = mean(lnincome, na.rm = TRUE),
                     ret_price = mean(retprice, na.rm = TRUE),
                     youth     = mean(age15to24, na.rm = TRUE)) |>
  generate_predictor(time_window = 1975, cigsale_1975 = cigsale) |>
  generate_predictor(time_window = 1978, cigsale_1978 = cigsale) |>
  generate_weights(optimization_window = 1970:1979,
                   margin_ipop = .02, sigf_ipop = 7, bound_ipop = 6) |>
  generate_control()

gaps_intime <- sc_intime |> grab_synthetic_control() |>
  mutate(gap = real_y - synth_y)
post_gap_fake <- gaps_intime |> filter(time_unit >= 1980) |>
  summarise(att_fake = mean(gap)) |> pull(att_fake)
cat("\n=== In-time placebo (treatment_year=1980) ===\n")
cat("假 ATT (1980-1988) =", round(post_gap_fake, 2), "包/人/年\n")
cat("（真 ATT 是 −18.85，假 ATT 应当接近 0 才算 pass）\n")

p3 <- gaps_intime |>
  pivot_longer(c(real_y, synth_y), names_to = "type", values_to = "y") |>
  mutate(type = ifelse(type == "real_y", "California 实际", "合成 California")) |>
  ggplot(aes(x = time_unit, y = y, color = type, linetype = type)) +
  geom_vline(xintercept = 1980, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  annotate("text", x = 1980.3, y = 200, label = "假 treatment\n→ 1980",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.0) +
  geom_line(linewidth = 1.0) +
  scale_color_manual(values = c("California 实际" = COLOR_TREAT,
                                "合成 California" = COLOR_DONOR)) +
  scale_linetype_manual(values = c("California 实际" = "solid", "合成 California" = "dashed")) +
  scale_x_continuous(breaks = seq(1970, 1988, 2)) +
  scale_y_continuous(limits = c(80, 220)) +
  labs(x = "年份", y = "人均香烟销量（packs / capita）",
       color = NULL, linetype = NULL) +
  theme_book()
ggsave(here::here("figure", "chap03_intime_placebo.png"),
       p3, width = 7, height = 4.0, dpi = 300, device = ragg::agg_png)

cat("\nDONE chap03.\n")
