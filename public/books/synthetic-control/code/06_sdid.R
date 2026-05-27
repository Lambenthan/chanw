# 06_sdid.R —— 合成 DiD (Arkhangelsky 2021, AER)
# 用 synthdid 包跑 California Prop 99 数据

suppressPackageStartupMessages({
  library(tidyverse); library(synthdid); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

data("california_prop99", package = "synthdid")
df <- california_prop99
str(df)

# panel.matrices 转矩阵
setup <- panel.matrices(df, unit = "State", time = "Year",
                        outcome = "PacksPerCapita", treatment = "treated")
Y <- setup$Y     # T × N matrix
N0 <- setup$N0   # N0 = donor count = 38
T0 <- setup$T0   # T0 = pre-period count = 19 (1970-1988)
cat("Y dim:", dim(Y), "; N0 =", N0, "; T0 =", T0, "\n")

# 主估计：synthdid
tau_sdid <- synthdid_estimate(Y, N0, T0)
cat("\n===== SDID =====\n")
cat("ATT estimate:", round(as.numeric(tau_sdid), 3), "包/人/年\n")

# 同时跑 SC 和 DiD 对比
tau_sc  <- sc_estimate(Y, N0, T0)
tau_did <- did_estimate(Y, N0, T0)
cat("SC  estimate:", round(as.numeric(tau_sc), 3), "\n")
cat("DiD estimate:", round(as.numeric(tau_did), 3), "\n")

# bootstrap SE & CI
set.seed(2026)
se_sdid <- sqrt(vcov(tau_sdid, method = "placebo"))
cat("\nSDID SE (placebo):", round(se_sdid, 3), "\n")
cat("SDID 95% CI: [",
    round(as.numeric(tau_sdid) - 1.96 * se_sdid, 2), ",",
    round(as.numeric(tau_sdid) + 1.96 * se_sdid, 2), "]\n")

# 比较表
est_tbl <- data.frame(
  method = c("DiD (TWFE)", "SC (Abadie)", "SDID (Arkhangelsky)"),
  ATT    = round(c(as.numeric(tau_did), as.numeric(tau_sc), as.numeric(tau_sdid)), 2)
)
print(est_tbl)
write.csv(est_tbl, here::here("data", "chap06_est_three.csv"), row.names = FALSE)

# === 图 1：synthdid_plot —— treatment vs synthetic control ===
# synthdid 包 plot 输出 ggplot
p1 <- plot(tau_sdid, treated.name = "California", control.name = "合成控制 (SDID)") +
  theme_book() +
  labs(x = "年份", y = "人均香烟销量（packs / capita）",
       title = "SDID：处理 vs 合成对照")
ggsave(here::here("figure", "chap06_sdid_plot.png"),
       p1, width = 7, height = 4.5, dpi = 300, device = ragg::agg_png)

# === 图 2：三方法对比柱状图 ===
p2 <- est_tbl |>
  ggplot(aes(x = reorder(method, ATT), y = ATT)) +
  geom_col(fill = COLOR_DONOR, alpha = 0.85, width = 0.6) +
  geom_text(aes(label = sprintf("%.2f", ATT)),
            vjust = ifelse(est_tbl$ATT < 0, 1.3, -0.4),
            family = "Times New Roman", size = 4, color = COLOR_TREAT) +
  geom_hline(yintercept = 0, color = "gray60") +
  scale_y_continuous(limits = c(-32, 5)) +
  labs(x = NULL, y = "ATT 估计（包/人/年）",
       title = "三种方法的 ATT 对比") +
  theme_book()
ggsave(here::here("figure", "chap06_three_methods.png"),
       p2, width = 6.5, height = 4.0, dpi = 300, device = ragg::agg_png)

# === 图 3：unit weights & time weights for SDID ===
unit_w <- summary(tau_sdid)$dimensions
# SDID 的核心创新：双权重
unit_weights <- attr(tau_sdid, "weights")$omega
time_weights <- attr(tau_sdid, "weights")$lambda

# 取 unit_weights > 0.001 的展示
state_names <- colnames(Y)[1:N0]
uw_df <- data.frame(state = state_names, weight = unit_weights) |>
  filter(weight > 0.001) |> arrange(desc(weight))
cat("\n=== SDID Unit weights (>0.001) ===\n")
print(uw_df)

# Pre-period years for time weights
pre_years <- 1970:(1970 + T0 - 1)
tw_df <- data.frame(year = pre_years, weight = time_weights)
cat("\n=== SDID Time weights ===\n")
print(tw_df)

p3 <- uw_df |>
  ggplot(aes(x = reorder(state, weight), y = weight)) +
  geom_col(fill = COLOR_DONOR, alpha = 0.85, width = 0.6) +
  geom_text(aes(label = sprintf("%.3f", weight)),
            hjust = -0.15, family = "Times New Roman", size = 3.2, color = "gray30") +
  coord_flip() +
  scale_y_continuous(limits = c(0, max(uw_df$weight) * 1.2)) +
  labs(x = NULL, y = "SDID Unit weight",
       title = "SDID 单元权重（>0.001）") +
  theme_book()
ggsave(here::here("figure", "chap06_sdid_unit_weights.png"),
       p3, width = 6.5, height = 4.0, dpi = 300, device = ragg::agg_png)

p4 <- tw_df |>
  ggplot(aes(x = year, y = weight)) +
  geom_col(fill = COLOR_ACCENT, alpha = 0.85, width = 0.75) +
  geom_text(aes(label = ifelse(weight > 0.001, sprintf("%.3f", weight), "")),
            vjust = -0.3, family = "Times New Roman", size = 2.8, color = "gray30") +
  scale_x_continuous(breaks = seq(1970, 1988, 2)) +
  labs(x = "年份", y = "SDID Time weight",
       title = "SDID 时间权重（pre-period 1970-1988）") +
  theme_book()
ggsave(here::here("figure", "chap06_sdid_time_weights.png"),
       p4, width = 7, height = 3.6, dpi = 300, device = ragg::agg_png)

write.csv(uw_df, here::here("data", "chap06_sdid_unit_weights.csv"), row.names = FALSE)
write.csv(tw_df, here::here("data", "chap06_sdid_time_weights.csv"), row.names = FALSE)

cat("\nDONE chap06.\n")
