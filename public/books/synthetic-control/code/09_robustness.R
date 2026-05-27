# 09_robustness.R —— 协变量与预测器选择的稳健性
# 比较 4 种预测器配置：
#  A. 仅 cigsale lag (1975, 1980, 1988)
#  B. cigsale lag + ln_income, retprice
#  C. 完整 Abadie 2010 配置（A + ln_income + retprice + youth + beer）
#  D. lag-only with all years (1970-1988 each)

suppressPackageStartupMessages({
  library(tidyverse); library(tidysynth); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

smoking <- read.csv(here::here("data", "smoking.csv"))

# A. cigsale lag only
fit_A <- smoking |>
  synthetic_control(outcome = cigsale, unit = state, time = year,
                    i_unit = "California", i_time = 1989,
                    generate_placebos = FALSE) |>
  generate_predictor(time_window = 1975, cig_75 = cigsale) |>
  generate_predictor(time_window = 1980, cig_80 = cigsale) |>
  generate_predictor(time_window = 1988, cig_88 = cigsale) |>
  generate_weights(optimization_window = 1970:1988,
                   margin_ipop = .02, sigf_ipop = 7, bound_ipop = 6) |>
  generate_control()

# B. lag + income + retprice
fit_B <- smoking |>
  synthetic_control(outcome = cigsale, unit = state, time = year,
                    i_unit = "California", i_time = 1989,
                    generate_placebos = FALSE) |>
  generate_predictor(time_window = 1980:1988,
                     ln_inc = mean(lnincome, na.rm = TRUE),
                     ret    = mean(retprice, na.rm = TRUE)) |>
  generate_predictor(time_window = 1975, cig_75 = cigsale) |>
  generate_predictor(time_window = 1980, cig_80 = cigsale) |>
  generate_predictor(time_window = 1988, cig_88 = cigsale) |>
  generate_weights(optimization_window = 1970:1988,
                   margin_ipop = .02, sigf_ipop = 7, bound_ipop = 6) |>
  generate_control()

# C. 完整 Abadie 2010
fit_C <- smoking |>
  synthetic_control(outcome = cigsale, unit = state, time = year,
                    i_unit = "California", i_time = 1989,
                    generate_placebos = FALSE) |>
  generate_predictor(time_window = 1980:1988,
                     ln_inc = mean(lnincome, na.rm = TRUE),
                     ret    = mean(retprice, na.rm = TRUE),
                     youth  = mean(age15to24, na.rm = TRUE)) |>
  generate_predictor(time_window = 1984:1988, beer = mean(beer, na.rm = TRUE)) |>
  generate_predictor(time_window = 1975, cig_75 = cigsale) |>
  generate_predictor(time_window = 1980, cig_80 = cigsale) |>
  generate_predictor(time_window = 1988, cig_88 = cigsale) |>
  generate_weights(optimization_window = 1970:1988,
                   margin_ipop = .02, sigf_ipop = 7, bound_ipop = 6) |>
  generate_control()

# D. cigsale 全 pre-period 各年
fit_D <- smoking |>
  synthetic_control(outcome = cigsale, unit = state, time = year,
                    i_unit = "California", i_time = 1989,
                    generate_placebos = FALSE) |>
  generate_predictor(time_window = 1970:1988, cig_avg = mean(cigsale)) |>
  generate_weights(optimization_window = 1970:1988,
                   margin_ipop = .02, sigf_ipop = 7, bound_ipop = 6) |>
  generate_control()

compute_att <- function(fit, label) {
  gap <- fit |> grab_synthetic_control() |>
    mutate(gap = real_y - synth_y) |>
    filter(time_unit >= 1989) |>
    summarise(att = mean(gap)) |> pull(att)
  data.frame(spec = label, ATT = round(gap, 3))
}

specs <- bind_rows(
  compute_att(fit_A, "A. 仅 cigsale lag (1975/1980/1988)"),
  compute_att(fit_B, "B. lag + income + retprice"),
  compute_att(fit_C, "C. 完整 Abadie 2010"),
  compute_att(fit_D, "D. cigsale 1970-1988 平均")
)
cat("===== 预测器敏感性 =====\n")
print(specs)
write.csv(specs, here::here("data", "chap09_specs.csv"), row.names = FALSE)

# === 图：四种 spec 的 trajectory ===
extract_traj <- function(fit, label) {
  fit |> grab_synthetic_control() |>
    mutate(spec = label)
}

all_traj <- bind_rows(
  extract_traj(fit_A, "A. cig lag"),
  extract_traj(fit_B, "B. + 收入价格"),
  extract_traj(fit_C, "C. Abadie 完整"),
  extract_traj(fit_D, "D. cig 平均")
)

p1 <- all_traj |>
  pivot_longer(c(real_y, synth_y), names_to = "type", values_to = "y") |>
  mutate(type = ifelse(type == "real_y", "实际", "合成")) |>
  ggplot(aes(x = time_unit, y = y, color = type, linetype = type)) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.3) +
  geom_line(linewidth = 0.7) +
  facet_wrap(~ spec, nrow = 2) +
  scale_color_manual(values = c("实际" = COLOR_TREAT, "合成" = COLOR_DONOR)) +
  scale_linetype_manual(values = c("实际" = "solid", "合成" = "dashed")) +
  scale_x_continuous(breaks = seq(1970, 2000, 10)) +
  labs(x = "年份", y = "人均香烟销量",
       color = NULL, linetype = NULL,
       title = "四种预测器配置下的 California vs 合成 California") +
  theme_book()
ggsave(here::here("figure", "chap09_specs_compare.png"),
       p1, width = 8, height = 5.0, dpi = 300, device = ragg::agg_png)

p2 <- specs |>
  ggplot(aes(x = reorder(spec, ATT), y = ATT)) +
  geom_col(fill = COLOR_DONOR, alpha = 0.85, width = 0.6) +
  geom_text(aes(label = sprintf("%.2f", ATT)),
            hjust = 1.2, family = "Times New Roman", size = 3.5, color = "white") +
  coord_flip() +
  labs(x = NULL, y = "ATT 估计（包/人/年）",
       title = "经典 Abadie SC 在四种预测器配置下的 ATT") +
  theme_book()
ggsave(here::here("figure", "chap09_specs_bar.png"),
       p2, width = 7, height = 4.0, dpi = 300, device = ragg::agg_png)

cat("\nDONE chap09.\n")
