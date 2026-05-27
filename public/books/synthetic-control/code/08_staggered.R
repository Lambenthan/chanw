# 08_staggered.R —— 多处理单位与交错处理时点（staggered SC）
# 用 fect 内置 turnout 数据辅助说明：48 州 staggered policy_edr adoption（1972-2012）
# 然后回归 California 主线

suppressPackageStartupMessages({
  library(tidyverse); library(fect); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

data("turnout", package = "fect")

cat("===== turnout (staggered DiD) =====\n")
cat("行数：", nrow(turnout), "\n")
cat("州数：", length(unique(turnout$abb)), "\n")
cat("年份：", min(turnout$year), "-", max(turnout$year), "\n")

# Election Day Registration (EDR) adopted by 7 states in staggered fashion
trt_years <- turnout |> filter(policy_edr == 1) |>
  group_by(abb) |> summarise(first_treat = min(year)) |>
  arrange(first_treat)
cat("\n=== EDR 采纳州及首治年份 ===\n")
print(trt_years)

# fect ife 跑 staggered ATT
fit_stagger <- fect(turnout ~ policy_edr,
                     data = turnout, index = c("abb", "year"),
                     method = "ife", CV = TRUE, force = "two-way",
                     se = TRUE, nboots = 200, parallel = FALSE, seed = 2026)
cat("\n===== fect ife (staggered) =====\n")
cat("ATT (post avg):", round(fit_stagger$att.avg, 3), "\n")
cat("SE            :", round(fit_stagger$est.avg[1, "S.E."], 3), "\n")
cat("95% CI        : [",
    round(fit_stagger$est.avg[1, "CI.lower"], 2), ",",
    round(fit_stagger$est.avg[1, "CI.upper"], 2), "]\n")

# 也跑 mc 估计
fit_mc <- fect(turnout ~ policy_edr,
                data = turnout, index = c("abb", "year"),
                method = "mc", CV = TRUE, force = "two-way",
                se = TRUE, nboots = 200, parallel = FALSE, seed = 2026)
cat("\n===== fect mc (staggered) =====\n")
cat("ATT (post avg):", round(fit_mc$att.avg, 3), "\n")
cat("SE            :", round(fit_mc$est.avg[1, "S.E."], 3), "\n")
cat("95% CI        : [",
    round(fit_mc$est.avg[1, "CI.lower"], 2), ",",
    round(fit_mc$est.avg[1, "CI.upper"], 2), "]\n")

# === 图 1：event-study ife ===
att_ife <- data.frame(rel_time = as.numeric(rownames(fit_stagger$est.att)),
                      fit_stagger$est.att)

p1 <- att_ife |>
  filter(rel_time >= -10, rel_time <= 20) |>
  ggplot(aes(x = rel_time, y = ATT)) +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_vline(xintercept = 0, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  geom_ribbon(aes(ymin = CI.lower, ymax = CI.upper),
              fill = COLOR_TREAT, alpha = 0.18) +
  geom_line(color = COLOR_TREAT, linewidth = 0.9) +
  geom_point(color = COLOR_TREAT, size = 1.3) +
  annotate("text", x = 0.5, y = 8, label = "Treatment time → 0",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.2) +
  scale_x_continuous(breaks = seq(-10, 20, 5)) +
  labs(x = "相对治疗时点（年）",
       y = "ATT 估计（投票率，%）",
       title = "fect ife (staggered ATT)：EDR 政策的 event-study") +
  theme_book()
ggsave(here::here("figure", "chap08_staggered_ife.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

# === 图 2：ife vs mc 三方法对比 ===
methods_df <- data.frame(
  method = c("ife (factor model)", "mc (matrix completion)"),
  ATT = round(c(fit_stagger$att.avg, fit_mc$att.avg), 2),
  CI_lower = round(c(fit_stagger$est.avg[1, "CI.lower"], fit_mc$est.avg[1, "CI.lower"]), 2),
  CI_upper = round(c(fit_stagger$est.avg[1, "CI.upper"], fit_mc$est.avg[1, "CI.upper"]), 2)
)
write.csv(methods_df, here::here("data", "chap08_methods.csv"), row.names = FALSE)

p2 <- methods_df |>
  ggplot(aes(x = method, y = ATT)) +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_pointrange(aes(ymin = CI_lower, ymax = CI_upper),
                  color = COLOR_TREAT, linewidth = 0.8, size = 0.6) +
  geom_text(aes(label = sprintf("ATT = %.2f", ATT)),
            family = "Times New Roman", size = 3.4,
            hjust = -0.3, color = COLOR_TREAT) +
  coord_flip() +
  labs(x = NULL, y = "ATT 估计 (投票率, %)",
       title = "Staggered turnout 数据下 ife 与 mc 的 ATT 对比") +
  theme_book()
ggsave(here::here("figure", "chap08_methods_compare.png"),
       p2, width = 7, height = 3.5, dpi = 300, device = ragg::agg_png)

write.csv(att_ife, here::here("data", "chap08_ife_att.csv"), row.names = FALSE)

cat("\nDONE chap08.\n")
