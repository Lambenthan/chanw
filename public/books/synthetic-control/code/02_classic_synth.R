# 02_classic_synth.R —— Abadie 2003 经典合成控制
# 用 tidysynth 实现（语法简洁，结果与 Synth 一致）
# 产出：
#   figure/chap02_synth_trajectory.png  CA 实际 vs 合成 CA
#   figure/chap02_synth_gap.png         处理效应 gap
#   figure/chap02_donor_weights.png     donor 权重柱状图
#   chap02 关键数字回贴 _NUMBERS.md

suppressPackageStartupMessages({
  library(tidyverse)
  library(tidysynth)
  library(here)
  library(ragg)
  library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

smoking <- read.csv(here::here("data", "smoking.csv"))

# tidysynth 流水线
sc_out <- smoking |>
  synthetic_control(outcome    = cigsale,
                    unit       = state,
                    time       = year,
                    i_unit     = "California",
                    i_time     = 1989,
                    generate_placebos = TRUE) |>
  # 预测器：1980-1988 各年 cigsale + 4 个协变量（参 Abadie 2010 Table 1）
  generate_predictor(time_window = 1980:1988,
                     ln_income      = mean(lnincome, na.rm = TRUE),
                     ret_price      = mean(retprice, na.rm = TRUE),
                     youth          = mean(age15to24, na.rm = TRUE)) |>
  generate_predictor(time_window = 1984:1988,
                     beer_sales     = mean(beer, na.rm = TRUE)) |>
  generate_predictor(time_window = 1975, cigsale_1975 = cigsale) |>
  generate_predictor(time_window = 1980, cigsale_1980 = cigsale) |>
  generate_predictor(time_window = 1988, cigsale_1988 = cigsale) |>
  generate_weights(optimization_window = 1970:1988,
                   margin_ipop = .02, sigf_ipop = 7, bound_ipop = 6) |>
  generate_control()

# === 关键数字 ===
cat("===== chap02 Abadie 经典合成控制 =====\n")
# pre/post RMSPE
pre_rmspe <- sc_out |> grab_significance(time_window = 1989:2000) |> filter(unit_name == "California") |> pull(pre_mspe) |> sqrt()
post_rmspe <- sc_out |> grab_significance(time_window = 1989:2000) |> filter(unit_name == "California") |> pull(post_mspe) |> sqrt()
ratio <- post_rmspe / pre_rmspe
cat("pre-period RMSPE  :", round(pre_rmspe, 3), "\n")
cat("post-period RMSPE :", round(post_rmspe, 3), "\n")
cat("RMSPE ratio       :", round(ratio, 2), "\n")

# Donor weights
weights <- sc_out |> grab_unit_weights() |> arrange(desc(weight))
cat("\n=== Donor weights (top 10) ===\n")
print(weights, n = 10)

# ATT 估计：post-period 平均 gap
gaps <- sc_out |> grab_synthetic_control() |>
  mutate(gap = real_y - synth_y)
post_gap <- gaps |> filter(time_unit >= 1989) |> summarise(att = mean(gap)) |> pull(att)
cat("\nATT (post-period mean gap, 1989-2000):", round(post_gap, 2), "包/人/年\n")

# 各年 gap
cat("\n=== 各年 gap (1989-2000) ===\n")
print(gaps |> filter(time_unit >= 1989) |> select(time_unit, real_y, synth_y, gap), n = 12)

# === 图 1：CA 实际 vs 合成 CA ===
p1 <- gaps |>
  pivot_longer(c(real_y, synth_y), names_to = "type", values_to = "y") |>
  mutate(type = ifelse(type == "real_y", "California 实际", "合成 California")) |>
  ggplot(aes(x = time_unit, y = y, color = type, linetype = type)) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  annotate("text", x = 1989.3, y = 30, label = "Prop 99 → 1989",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.2) +
  geom_line(linewidth = 1.0) +
  scale_color_manual(values = c("California 实际" = COLOR_TREAT,
                                "合成 California"  = COLOR_DONOR)) +
  scale_linetype_manual(values = c("California 实际" = "solid", "合成 California" = "dashed")) +
  scale_x_continuous(breaks = seq(1970, 2000, 5)) +
  scale_y_continuous(limits = c(20, 140), breaks = seq(20, 140, 20)) +
  labs(x = "年份", y = "人均香烟销量（packs / capita）",
       color = NULL, linetype = NULL) +
  theme_book()
ggsave(here::here("figure", "chap02_synth_trajectory.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

# === 图 2：gap ===
p2 <- gaps |>
  ggplot(aes(x = time_unit, y = gap)) +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.4) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  geom_line(color = COLOR_TREAT, linewidth = 1.0) +
  geom_point(color = COLOR_TREAT, size = 1.2) +
  annotate("text", x = 1989.3, y = -55, label = "Prop 99 → 1989",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.2) +
  scale_x_continuous(breaks = seq(1970, 2000, 5)) +
  scale_y_continuous(limits = c(-70, 25), breaks = seq(-70, 20, 15)) +
  labs(x = "年份",
       y = "处理效应估计（实际 − 合成，包/人）") +
  theme_book()
ggsave(here::here("figure", "chap02_synth_gap.png"),
       p2, width = 7, height = 3.8, dpi = 300, device = ragg::agg_png)

# === 图 3：donor weights ===
top_donors <- weights |> filter(weight > 0.001) |> arrange(desc(weight))
p3 <- top_donors |>
  ggplot(aes(x = reorder(unit, weight), y = weight)) +
  geom_col(fill = COLOR_DONOR, alpha = 0.85, width = 0.65) +
  geom_text(aes(label = sprintf("%.3f", weight)),
            hjust = -0.15, family = "Times New Roman", size = 3.2, color = "gray30") +
  coord_flip() +
  scale_y_continuous(limits = c(0, max(top_donors$weight) * 1.15)) +
  labs(x = NULL, y = "合成控制权重") +
  theme_book()
ggsave(here::here("figure", "chap02_donor_weights.png"),
       p3, width = 6.5, height = 4.0, dpi = 300, device = ragg::agg_png)

# 保存 sc_out 供 chap03/04 使用
saveRDS(sc_out, here::here("data", "sc_out_classic.rds"))
cat("\n=== sc_out 保存到 data/sc_out_classic.rds ===\n")

# 写入 _NUMBERS.md 用的 csv
weights |> write.csv(here::here("data", "chap02_weights.csv"), row.names = FALSE)
gaps |> write.csv(here::here("data", "chap02_gaps.csv"), row.names = FALSE)

cat("\nDONE chap02.\n")
