# 07_mcnnm.R —— 矩阵填充 MC-NNM via fect

suppressPackageStartupMessages({
  library(tidyverse); library(fect); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

smoking <- read.csv(here::here("data", "smoking.csv"))
smoking$treated <- with(smoking, ifelse(state == "California" & year >= 1989, 1, 0))

mc <- fect(cigsale ~ treated,
           data = smoking, index = c("state", "year"),
           method = "mc", CV = TRUE, force = "two-way",
           se = TRUE, nboots = 200, parallel = FALSE, seed = 2026)

cat("===== MC-NNM (Athey et al. 2021) via fect =====\n")
cat("ATT (post-period avg):", round(mc$att.avg, 3), "包/人/年\n")
cat("SE                   :", round(mc$est.avg[1, "S.E."], 3), "\n")
cat("95% CI               : [",
    round(mc$est.avg[1, "CI.lower"], 2), ",",
    round(mc$est.avg[1, "CI.upper"], 2), "]\n")
cat("λ (CV)               :", round(mc$lambda.cv, 4), "\n\n")

# ATT 各年（相对 treatment 时点）
att_df <- data.frame(
  rel_time = as.numeric(rownames(mc$est.att)),
  mc$est.att
)
# 转回绝对年份：rel_time=0 是 treatment 第一年 1989, rel_time=-1 是 1988
att_df$year <- att_df$rel_time + 1989

cat("=== ATT per relative time (event-study format) ===\n")
print(att_df |> filter(rel_time >= -5, rel_time <= 12))

# 保存
write.csv(att_df, here::here("data", "chap07_mc_att.csv"), row.names = FALSE)
saveRDS(mc, here::here("data", "mc_out.rds"))

# === 图：MC-NNM event-study (ATT 各年 + 95% CI) ===
plot_df <- att_df |> filter(year >= 1980, year <= 2000)

p1 <- plot_df |>
  ggplot(aes(x = year, y = ATT)) +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  geom_ribbon(aes(ymin = CI.lower, ymax = CI.upper),
              fill = COLOR_TREAT, alpha = 0.18) +
  geom_line(color = COLOR_TREAT, linewidth = 0.9) +
  geom_point(color = COLOR_TREAT, size = 1.5) +
  annotate("text", x = 1989.3, y = 6, label = "Prop 99 → 1989",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.2) +
  scale_x_continuous(breaks = seq(1980, 2000, 2)) +
  scale_y_continuous(breaks = seq(-35, 5, 5)) +
  labs(x = "年份",
       y = "ATT 估计（实际 − 反事实，包/人/年）",
       title = sprintf("MC-NNM event-study（λ = %.4f）", mc$lambda.cv)) +
  theme_book()
ggsave(here::here("figure", "chap07_mcnnm.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

# Pre-period 安慰剂诊断：rel_time<0 的 ATT 应当接近 0
pre_mean <- mean(att_df$ATT[att_df$rel_time < 0])
pre_max  <- max(abs(att_df$ATT[att_df$rel_time < 0]))
cat("\n=== Pre-period MC ATT 平均:", round(pre_mean, 3), "\n")
cat("Pre-period |ATT| 最大:", round(pre_max, 3), "(用于诊断 pre-trend)\n")

cat("\nDONE chap07.\n")
