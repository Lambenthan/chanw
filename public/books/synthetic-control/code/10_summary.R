# 10_summary.R —— 终极对比表（所有方法 ATT 汇总）
suppressPackageStartupMessages({
  library(tidyverse); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))

# 汇总所有方法
summary_tbl <- tribble(
  ~chapter, ~method,                  ~ATT,     ~CI_lower, ~CI_upper, ~assumption,           ~limit,
  "第 1 章", "朴素 DiD (TWFE)",       -27.35,   NA,         NA,        "平行趋势",            "忽略 unit-time 异质",
  "第 2 章", "Abadie SC (经典)",      -18.85,   NA,         NA,        "凸壳内可拟合",        "无原生 SE",
  "第 3 章", "In-space placebo",       NA,      NA,         NA,        "可交换性",            "依赖 donor 过滤标准",
  "第 4 章", "Permutation 推断 (k=20)", NA,     NA,         NA,        "fit 公平性",          "p 对 filter 极敏感",
  "第 5 章", "GSC r=0 (Xu 2017)",     -27.35,   -33.20,     -21.50,    "FE 结构",             "退化为 DiD",
  "第 5 章", "GSC r=1",               -13.89,   -19.91,      -7.87,    "1-factor 结构",       "factor 过拟合风险",
  "第 5 章", "GSC r=2",               -0.40,    -20.39,      19.58,   "2-factor 结构",       "效应被 factor 吃光",
  "第 6 章", "SDID (Arkhangelsky)",   -15.60,   -34.41,       3.21,    "近期年加权可比",      "CI 包含 0",
  "第 7 章", "MC-NNM (Athey 2021)",   -25.91,   -30.82,     -20.99,    "低秩结构",            "λ 选择需 CV",
  "第 9 章", "SC 配置 A (仅 lag)",    -22.95,   NA,         NA,        "lag 充分概括状态",    "无收入价格信息",
  "第 9 章", "SC 配置 C (Abadie 完整)", -18.85, NA,         NA,        "完整预测器",          "依赖 1980-88 协变量",
  "第 9 章", "SC 配置 D (cig 平均)",  -30.65,   NA,         NA,        "1970-88 mean 概括",   "丢失 lag 信息"
)

cat("===== 终极对比表 =====\n")
print(summary_tbl)
write.csv(summary_tbl, here::here("data", "chap10_summary.csv"), row.names = FALSE)

# === 图：所有 ATT 估计的 forest plot ===
plot_df <- summary_tbl |>
  filter(!is.na(ATT)) |>
  mutate(label = paste0(method),
         has_ci = !is.na(CI_lower))

p <- plot_df |>
  ggplot(aes(x = ATT, y = reorder(label, ATT))) +
  geom_vline(xintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_vline(xintercept = -18.85, color = COLOR_DONOR, linetype = "dashed",
             linewidth = 0.4, alpha = 0.6) +
  geom_segment(data = filter(plot_df, has_ci),
               aes(x = CI_lower, xend = CI_upper, y = label, yend = label),
               color = COLOR_TREAT, linewidth = 0.7, alpha = 0.6) +
  geom_point(color = COLOR_TREAT, size = 2.4, alpha = 0.9) +
  geom_text(aes(label = sprintf("%.2f", ATT)),
            family = "Times New Roman", size = 3.0,
            hjust = -0.3, vjust = -0.5, color = "gray30") +
  scale_x_continuous(breaks = seq(-35, 25, 10)) +
  labs(x = "ATT 估计（包/人/年）",
       y = NULL,
       title = "所有方法 ATT 估计森林图",
       caption = "灰虚线：Abadie SC 经典值 −18.85；横线：95% CI（如可得）") +
  theme_book(base_size = 10)
ggsave(here::here("figure", "chap10_forest.png"),
       p, width = 8.5, height = 5.0, dpi = 300, device = ragg::agg_png)

cat("\nDONE chap10.\n")
