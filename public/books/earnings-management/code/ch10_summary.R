# =====================================================
# code/ch10_summary.R
# 第 10 章：十方法终极对比
#   - 把各章 firm-year 级 DA 估计合并到一张面板
#   - F-Score（Dechow et al. 2011）线性概率模型基础版
#   - 方法间 Pearson / Spearman 相关矩阵
#   - 三家案例公司在十种方法下的排名汇总
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(broom)
  library(here)
})

set.seed(2026)
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

# 收集每章 DA（按 fyear pooled 重跑）
make_da_jones <- function(df) {
  out <- df |> filter(!is.na(TA), !is.na(dSale_s), !is.na(PPE_s))
  out |> group_by(fyear) |>
    mutate(DA_jones = resid(lm(TA ~ 0 + inv_lag_at + dSale_s + PPE_s))) |>
    ungroup() |> select(gvkey, fyear, DA_jones)
}
make_da_mj <- function(df) {
  df2 <- df |> mutate(dSaleRect_s = dSale_s - dRect_s) |>
    filter(!is.na(TA), !is.na(dSaleRect_s), !is.na(PPE_s))
  df2 |> group_by(fyear) |>
    mutate(DA_mj = resid(lm(TA ~ 0 + inv_lag_at + dSaleRect_s + PPE_s))) |>
    ungroup() |> select(gvkey, fyear, DA_mj)
}
make_da_healy <- function(df) {
  df |> group_by(fyear) |>
    mutate(DA_healy = TA - mean(TA, na.rm = TRUE)) |>
    ungroup() |> select(gvkey, fyear, DA_healy)
}
make_da_deangelo <- function(df) {
  df |> arrange(gvkey, fyear) |>
    group_by(gvkey) |>
    mutate(DA_deangelo = TA - lag(TA)) |>
    ungroup() |> select(gvkey, fyear, DA_deangelo)
}
make_da_stb <- function(df) {
  out <- df |> filter(!is.na(dRect_s), !is.na(dSale_s))
  out |> group_by(fyear) |>
    mutate(DA_stb = resid(lm(dRect_s ~ dSale_s))) |>
    ungroup() |> select(gvkey, fyear, DA_stb)
}

cat("各章 DA 计算...\n")
da_jones    <- make_da_jones(p)
da_mj       <- make_da_mj(p)
da_healy    <- make_da_healy(p)
da_deangelo <- make_da_deangelo(p)
da_stb      <- make_da_stb(p)

# Performance-matched
pm_match <- function(df) {
  df |> arrange(ROA) |>
    mutate(near_DA = if_else(
      is.na(lead(DA_mj)) | (!is.na(lag(DA_mj)) &
                              abs(lag(ROA) - ROA) <= abs(lead(ROA) - ROA)),
      lag(DA_mj), lead(DA_mj)),
      DA_pm = DA_mj - near_DA) |>
    select(-near_DA)
}
da_pm <- p |>
  filter(!is.na(TA), !is.na(dSale_s), !is.na(PPE_s),
         !is.na(dRect_s), !is.na(ROA)) |>
  mutate(dSaleRect_s = dSale_s - dRect_s) |>
  group_by(fyear) |>
  mutate(DA_mj = resid(lm(TA ~ 0 + inv_lag_at + dSaleRect_s + PPE_s))) |>
  group_modify(~ pm_match(.x)) |>
  ungroup() |>
  select(gvkey, fyear, DA_pm)

# DD & McNichols
p_dd <- p |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(CFO_lag = lag(CFO_s), CFO_lead = lead(CFO_s)) |>
  ungroup() |>
  filter(!is.na(WC_accr), !is.na(CFO_lag), !is.na(CFO_s), !is.na(CFO_lead))

fit_dd <- lm(WC_accr ~ CFO_lag + CFO_s + CFO_lead, data = p_dd)
da_dd <- p_dd |> mutate(DA_dd = resid(fit_dd)) |>
  select(gvkey, fyear, DA_dd)

p_mcn <- p_dd |> filter(!is.na(dSale_s), !is.na(PPE_s))
fit_mcn <- lm(WC_accr ~ CFO_lag + CFO_s + CFO_lead + dSale_s + PPE_s,
              data = p_mcn)
da_mcn <- p_mcn |> mutate(DA_mcn = resid(fit_mcn)) |>
  select(gvkey, fyear, DA_mcn)

# Roychowdhury RM
p_rm <- p |> arrange(gvkey, fyear) |> group_by(gvkey) |>
  mutate(dSale_lag_s = lag(dSale_s),
         PROD_s = (cogs + (invt - lag(invt))) / lag_at) |>
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
da_rm <- abn_cfo |> inner_join(abn_prod, by = c("gvkey", "fyear")) |>
  mutate(DA_rm = -abnCFO + abnPROD) |>
  select(gvkey, fyear, DA_rm)

# 合表
master <- p |> select(gvkey, fyear, company, misstate, TA, ROA) |>
  left_join(da_healy,    by = c("gvkey", "fyear")) |>
  left_join(da_deangelo, by = c("gvkey", "fyear")) |>
  left_join(da_jones,    by = c("gvkey", "fyear")) |>
  left_join(da_mj,       by = c("gvkey", "fyear")) |>
  left_join(da_pm,       by = c("gvkey", "fyear")) |>
  left_join(da_dd,       by = c("gvkey", "fyear")) |>
  left_join(da_mcn,      by = c("gvkey", "fyear")) |>
  left_join(da_stb,      by = c("gvkey", "fyear")) |>
  left_join(da_rm,       by = c("gvkey", "fyear"))

# F-Score 线性概率模型基础版（complete cases）
fs_data <- master |>
  filter(!is.na(DA_mj), !is.na(DA_rm), !is.na(DA_stb),
         !is.na(DA_dd), !is.na(ROA), !is.na(misstate))
cat(sprintf("\nF-Score 训练样本: %d firm-year (其中 misstate=1: %d)\n",
            nrow(fs_data), sum(fs_data$misstate == 1)))

fit_fs <- glm(misstate ~ DA_mj + DA_rm + DA_stb + DA_dd + ROA,
              data = fs_data, family = binomial())
cat("\n======== 10.1 F-Score logit 系数 ========\n")
print(tidy(fit_fs), digits = 4)

fs_data$pred_prob <- predict(fit_fs, type = "response")
fs_data$F_Score   <- fs_data$pred_prob / mean(fs_data$pred_prob)

# AUC
roc_auc <- function(score, label) {
  ord <- order(-score)
  s <- score[ord]; l <- label[ord]
  n_pos <- sum(l == 1); n_neg <- sum(l == 0)
  tpr <- cumsum(l == 1) / n_pos
  fpr <- cumsum(l == 0) / n_neg
  sum(diff(c(0, fpr)) * (tpr + lag(tpr, default = 0)) / 2)
}
cat(sprintf("\nF-Score AUC = %.4f\n",
            roc_auc(fs_data$F_Score, fs_data$misstate)))

# 相关矩阵
methods <- c("DA_healy", "DA_deangelo", "DA_jones", "DA_mj",
             "DA_pm", "DA_dd", "DA_mcn", "DA_stb", "DA_rm")
cat("\n======== 10.2 九种 DA 的 Pearson 相关矩阵 ========\n")
cor_mat <- master |> select(all_of(methods)) |>
  cor(use = "pairwise.complete.obs", method = "pearson")
print(round(cor_mat, 3))

cat("\n======== 10.3 九种 DA 的 Spearman 相关矩阵 ========\n")
cor_mat_sp <- master |> select(all_of(methods)) |>
  cor(use = "pairwise.complete.obs", method = "spearman")
print(round(cor_mat_sp, 3))

# 案例公司汇总
case <- master |> filter(!is.na(company))
cat("\n======== 10.4 案例公司各方法 DA（部分年份）========\n")
print(case |> arrange(company, fyear) |>
        select(company, fyear, misstate, all_of(methods)),
      n = Inf, width = Inf)

write_csv(master, here::here("data", "ch10_master_panel.csv"))
write_csv(case,   here::here("data", "ch10_case_master.csv"))
cat("\n合表已写出：data/ch10_master_panel.csv 与 ch10_case_master.csv\n")
