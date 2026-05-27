# =====================================================
# code/chXX_figures.R
# 为 chap03-chap10 一次性产出所有章节图
# 复用 ch10_master_panel.csv 主合表
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
  library(ragg)
})

set.seed(2026)
source(here::here("code", "_theme.R"))
source(here::here("code", "_load_panel.R"))

master <- read_csv(here::here("data", "ch10_master_panel.csv"),
                   show_col_types = FALSE)

save_fig <- function(g, name, w = 6.8, h = 4.4) {
  ggsave(here::here("figure", name), plot = g,
         width = w, height = h, dpi = 300,
         device = ragg::agg_png)
}

# ---------- ch03: DA_jones 直方图 ----------
g <- master |> filter(!is.na(DA_jones)) |>
  ggplot(aes(DA_jones)) +
  geom_histogram(bins = 80, fill = em_colors$normal,
                 colour = "white", alpha = 0.85) +
  coord_cartesian(xlim = c(-0.4, 0.4)) +
  labs(x = "DA_jones (Jones 残差)", y = "firm-year 频数",
       title = "Jones 模型 DA 残差分布",
       subtitle = "1991-2014 按 fyear pooled OLS") +
  theme_book()
save_fig(g, "ch03_da_jones_distribution.png")

# ---------- ch04: DA_mj vs DA_jones 散点 ----------
sub <- master |> filter(!is.na(DA_mj), !is.na(DA_jones)) |>
  slice_sample(n = 8000)
g <- ggplot(sub, aes(DA_jones, DA_mj)) +
  geom_point(alpha = 0.2, size = 0.5, colour = em_colors$normal) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed",
              colour = em_colors$em) +
  coord_cartesian(xlim = c(-0.4, 0.4), ylim = c(-0.4, 0.4)) +
  labs(x = "DA_jones", y = "DA_mj (Modified Jones)",
       title = "Modified Jones 与 Jones DA 散点",
       subtitle = "Pearson 0.998") +
  theme_book()
save_fig(g, "ch04_mj_jones_scatter.png", w = 5.5, h = 5)

# ---------- ch05: PM-DA vs DA_mj 散点 ----------
sub <- master |> filter(!is.na(DA_pm), !is.na(DA_mj)) |>
  slice_sample(n = 8000)
g <- ggplot(sub, aes(DA_mj, DA_pm)) +
  geom_point(alpha = 0.2, size = 0.5, colour = em_colors$normal) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed",
              colour = em_colors$em) +
  coord_cartesian(xlim = c(-0.5, 0.5), ylim = c(-0.6, 0.6)) +
  labs(x = "DA_mj", y = "DA_pm (Performance-Matched)",
       title = "PM-DA 与 Modified Jones DA 散点",
       subtitle = "Pearson 0.676") +
  theme_book()
save_fig(g, "ch05_pm_mj_scatter.png", w = 5.5, h = 5)

# ---------- ch06: AQ_dd 直方图 ----------
p <- load_em_panel()
p2 <- p |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(CFO_lag = lag(CFO_s), CFO_lead = lead(CFO_s)) |>
  ungroup() |>
  filter(!is.na(WC_accr), !is.na(CFO_lag), !is.na(CFO_s), !is.na(CFO_lead))
fit_dd <- lm(WC_accr ~ CFO_lag + CFO_s + CFO_lead, data = p2)
p2$resid_dd <- residuals(fit_dd)
aq <- p2 |> group_by(gvkey) |> filter(n() >= 5) |>
  summarise(AQ_dd = sd(resid_dd), .groups = "drop")

g <- aq |> ggplot(aes(AQ_dd)) +
  geom_histogram(bins = 80, fill = em_colors$normal,
                 colour = "white", alpha = 0.85) +
  coord_cartesian(xlim = c(0, 0.5)) +
  labs(x = "AQ_dd (按公司 5+ 年残差标准差)", y = "公司数",
       title = "Dechow-Dichev 应计质量分布",
       subtitle = "7,126 家公司，越大盈余质量越差") +
  theme_book()
save_fig(g, "ch06_aq_dd_distribution.png")

# ---------- ch07: DA_mcn vs DA_dd 散点 ----------
sub <- master |> filter(!is.na(DA_mcn), !is.na(DA_dd)) |>
  slice_sample(n = 8000)
g <- ggplot(sub, aes(DA_dd, DA_mcn)) +
  geom_point(alpha = 0.2, size = 0.5, colour = em_colors$normal) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed",
              colour = em_colors$em) +
  coord_cartesian(xlim = c(-0.4, 0.4), ylim = c(-0.4, 0.4)) +
  labs(x = "DA_dd", y = "DA_mcn (McNichols)",
       title = "McNichols 残差与 DD 残差散点",
       subtitle = "Pearson 0.973") +
  theme_book()
save_fig(g, "ch07_mcn_dd_scatter.png", w = 5.5, h = 5)

# ---------- ch08: DA_stb 与 DA_jones 散点 + 直方图 ----------
sub <- master |> filter(!is.na(DA_stb), !is.na(DA_jones)) |>
  slice_sample(n = 8000)
g <- ggplot(sub, aes(DA_jones, DA_stb)) +
  geom_point(alpha = 0.2, size = 0.5, colour = em_colors$normal) +
  coord_cartesian(xlim = c(-0.4, 0.4), ylim = c(-0.3, 0.3)) +
  labs(x = "DA_jones (应计型)", y = "DA_stb (收入型)",
       title = "Stubben 收入型 DA 与 Jones 应计型 DA",
       subtitle = "Pearson 0.290, 两类信号近似独立") +
  theme_book()
save_fig(g, "ch08_stb_jones_scatter.png", w = 5.5, h = 5)

# ---------- ch09: abnCFO 与 abnPROD 散点 ----------
sub <- master |> filter(!is.na(DA_rm)) |>
  slice_sample(n = 8000)
# 重新计算 abnCFO / abnPROD（master 里只有合成 DA_rm）
p_rm <- p |> arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(dSale_lag_s = lag(dSale_s)) |>
  ungroup()
abn_cfo <- p_rm |> filter(!is.na(CFO_s), !is.na(Sale_s), !is.na(dSale_s)) |>
  group_by(fyear) |>
  mutate(abnCFO = resid(lm(CFO_s ~ 0 + inv_lag_at + Sale_s + dSale_s))) |>
  ungroup() |> select(gvkey, fyear, abnCFO)
abn_prod <- p_rm |> filter(!is.na(PROD_s), !is.na(Sale_s),
                           !is.na(dSale_s), !is.na(dSale_lag_s)) |>
  group_by(fyear) |>
  mutate(abnPROD = resid(lm(PROD_s ~ 0 + inv_lag_at + Sale_s + dSale_s + dSale_lag_s))) |>
  ungroup() |> select(gvkey, fyear, abnPROD)
rm_panel <- abn_cfo |> inner_join(abn_prod, by = c("gvkey", "fyear"))
sub2 <- rm_panel |> slice_sample(n = 8000)
g <- ggplot(sub2, aes(abnCFO, abnPROD)) +
  geom_point(alpha = 0.2, size = 0.5, colour = em_colors$normal) +
  geom_vline(xintercept = 0, linetype = "dashed", colour = em_colors$em) +
  geom_hline(yintercept = 0, linetype = "dashed", colour = em_colors$em) +
  coord_cartesian(xlim = c(-0.4, 0.4), ylim = c(-0.4, 0.4)) +
  labs(x = "abnCFO (异常经营现金流)", y = "abnPROD (异常生产成本)",
       title = "Roychowdhury 异常 CFO 与异常 PROD 散点",
       subtitle = "右下象限 (abnCFO<0, abnPROD>0) 是真实活动操纵的典型方向") +
  theme_book()
save_fig(g, "ch09_abn_cfo_prod_scatter.png")

# ---------- ch10: 相关矩阵热图 ----------
methods <- c("DA_healy", "DA_deangelo", "DA_jones", "DA_mj",
             "DA_pm", "DA_dd", "DA_mcn", "DA_stb", "DA_rm")
cor_mat <- master |> select(all_of(methods)) |>
  cor(use = "pairwise.complete.obs", method = "pearson")
cor_long <- as_tibble(cor_mat, rownames = "row") |>
  pivot_longer(-row, names_to = "col", values_to = "r") |>
  mutate(
    row = factor(row, levels = methods),
    col = factor(col, levels = methods)
  )
g <- ggplot(cor_long, aes(col, fct_rev(row), fill = r)) +
  geom_tile(colour = "white", linewidth = 0.3) +
  geom_text(aes(label = sprintf("%.2f", r)), size = 2.7,
            family = "Times New Roman") +
  scale_fill_gradient2(low = "#3182BD", mid = "white", high = em_colors$em,
                       midpoint = 0, limits = c(-0.1, 1)) +
  labs(x = NULL, y = NULL,
       title = "九种 DA 度量的 Pearson 相关矩阵") +
  theme_book() +
  theme(axis.text.x = element_text(angle = 35, hjust = 1),
        panel.grid = element_blank())
save_fig(g, "ch10_corr_heatmap.png", w = 6.8, h = 5.5)

# ---------- ch10: 案例公司各方法 DA 排名条形图 ----------
case <- master |> filter(!is.na(company))
# 各方法每年同样本分位
add_rank <- function(df, col) {
  newname <- paste0("rank_", sub("DA_", "", col))
  df |> group_by(fyear) |>
    mutate("{newname}" := percent_rank(abs(.data[[col]]))) |>
    ungroup()
}
master2 <- master
for (m in methods) master2 <- add_rank(master2, m)

case_avg <- master2 |> filter(!is.na(company), misstate == 1) |>
  group_by(company) |>
  summarise(across(starts_with("rank_"), \(x) mean(x, na.rm = TRUE)),
            .groups = "drop") |>
  pivot_longer(-company, names_to = "method",
               values_to = "rank") |>
  mutate(method = sub("rank_", "", method),
         method = factor(method,
                         levels = c("healy", "deangelo", "jones", "mj",
                                    "pm", "dd", "mcn", "stb", "rm")))

g <- ggplot(case_avg, aes(method, rank, fill = company)) +
  geom_col(position = position_dodge(width = 0.8), width = 0.7) +
  geom_hline(yintercept = 0.5, linetype = "dashed", colour = "grey40") +
  coord_cartesian(ylim = c(0, 1)) +
  scale_fill_manual(values = c(
    "Enron" = em_colors$em,
    "Sunbeam" = "#984EA3",
    "Computer Associates" = em_colors$normal
  )) +
  labs(x = "方法", y = "舞弊年份平均同年分位",
       title = "三家 AAER 案例公司在九种方法下的舞弊年份平均分位",
       subtitle = "0.5 代表中位，越接近 1 越被排到分布右尾",
       fill = "公司") +
  theme_book()
save_fig(g, "ch10_case_ranks_bar.png", w = 8.4, h = 4.6)

cat("所有图已生成。\n")
