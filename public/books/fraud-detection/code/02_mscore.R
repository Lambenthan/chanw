# =====================================================
# code/02_mscore.R
# 第 2 章：Beneish M-Score（八变量规则基线）
# 输入：data/bao2020_full.csv
# 输出：测试集 AUC / NDCG@100 / Recall@1% / Precision@1%
#       Enron 2000 / Tyco 2000 的 M-Score
#
# 八变量公式（Beneish 1999）：
#   M = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI
#       + 0.892*SGI + 0.115*DEPI - 0.172*SGAI
#       + 4.679*TATA - 0.327*LVGI
#
# Bao 28 变量集对 M-Score 的覆盖：
#   - 缺失 xsga（销售管理费用），SGAI 项无法直接计算 -> 置为 1（中性值，
#     使该项贡献等同于 SGAI=1 时的 -0.172），并在 interpretation 中说明
#   - 缺失 oancf（经营现金流），TATA 项采用应计制近似：
#     TATA ≈ (ib - 营运资本变动) / at
#     其中营运资本变动 ≈ Δ(act - lct - che + dlc)，是 Beneish 1999
#     原文在缺乏 oancf 时使用的资产负债表近似
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
  library(pROC)
})
set.seed(2026)

# ---------- 1. 读数据 ----------
d <- read_csv(here::here("data", "bao2020_full.csv"),
              show_col_types = FALSE)

cat(sprintf("[原始] firm-years = %d\n", nrow(d)))

# ---------- 2. 按 gvkey 取上一年 lag ----------
need_cols <- c("rect", "sale", "cogs", "act", "ppegt", "at",
               "dp", "dlc", "dltt", "lct", "che", "ib")

d <- d %>%
  arrange(gvkey, fyear) %>%
  group_by(gvkey) %>%
  mutate(
    lag_fyear = lag(fyear),
    across(all_of(need_cols), lag, .names = "lag_{.col}")
  ) %>%
  ungroup() %>%
  filter(!is.na(lag_fyear), lag_fyear == fyear - 1)

cat(sprintf("[有连续上一年] firm-years = %d\n", nrow(d)))

# ---------- 3. 构造八个 Beneish 变量 ----------
safe_div <- function(num, den) {
  ifelse(is.na(num) | is.na(den) | den == 0, NA_real_, num / den)
}

d <- d %>%
  mutate(
    DSRI = safe_div(rect / sale, lag_rect / lag_sale),
    GMI  = safe_div((lag_sale - lag_cogs) / lag_sale,
                    (sale - cogs) / sale),
    AQI  = safe_div(1 - (act + ppegt) / at,
                    1 - (lag_act + lag_ppegt) / lag_at),
    SGI  = safe_div(sale, lag_sale),
    DEPI = safe_div(lag_dp / (lag_dp + lag_ppegt),
                    dp / (dp + ppegt)),
    SGAI = 1,  # xsga 不在 Bao 28 变量集中，置为中性值
    LVGI = safe_div((dlc + dltt) / at,
                    (lag_dlc + lag_dltt) / lag_at),
    # TATA：用资产负债表近似营运资本变动
    wc_t      = act - lct - che + dlc,
    wc_lag    = lag_act - lag_lct - lag_che + lag_dlc,
    delta_wc  = wc_t - wc_lag,
    TATA = safe_div(ib - delta_wc, at)
  )

# ---------- 4. M-Score 加权求和 ----------
d <- d %>%
  mutate(
    mscore = -4.84 +
      0.920 * DSRI +
      0.528 * GMI  +
      0.404 * AQI  +
      0.892 * SGI  +
      0.115 * DEPI -
      0.172 * SGAI +
      4.679 * TATA -
      0.327 * LVGI
  )

# 删除任一变量缺失的行
d_score <- d %>%
  filter(!is.na(mscore),
         is.finite(mscore))

cat(sprintf("[可打分] firm-years = %d\n", nrow(d_score)))
cat(sprintf("[被丢弃] firm-years = %d\n",
            nrow(d) - nrow(d_score)))

# Winsorize 极值（Beneish 原文操作）：1% / 99% 截尾
qs <- quantile(d_score$mscore, c(0.005, 0.995), na.rm = TRUE)
d_score <- d_score %>%
  mutate(mscore = pmin(pmax(mscore, qs[1]), qs[2]))

# ---------- 5. 时间切分（Bao 协议） ----------
test <- d_score %>% filter(fyear >= 2009, fyear <= 2014)
cat(sprintf("[测试集] firm-years = %d, fraud = %d\n",
            nrow(test), sum(test$misstate)))

# ---------- 6. 测试集性能 ----------
roc_obj <- roc(response = test$misstate,
               predictor = test$mscore,
               quiet = TRUE,
               direction = "<")
auc_val <- as.numeric(auc(roc_obj))

# Recall@1% 与 Precision@1%
n_test <- nrow(test)
k_top  <- ceiling(n_test * 0.01)
top_idx <- order(test$mscore, decreasing = TRUE)[1:k_top]
hits    <- sum(test$misstate[top_idx])
recall_1pct    <- hits / sum(test$misstate)
precision_1pct <- hits / k_top

# NDCG@100
ndcg_at_k <- function(rel, k) {
  rel <- as.numeric(rel)
  k   <- min(k, length(rel))
  ideal <- sort(rel, decreasing = TRUE)[1:k]
  disc  <- 1 / log2(seq_len(k) + 1)
  dcg   <- sum(rel[1:k] * disc)
  idcg  <- sum(ideal * disc)
  if (idcg == 0) return(0)
  dcg / idcg
}
ord100  <- order(test$mscore, decreasing = TRUE)
ndcg100 <- ndcg_at_k(test$misstate[ord100], 100)

cat("\n========== 测试集性能（M-Score） ==========\n")
cat(sprintf("AUC          = %.4f\n", auc_val))
cat(sprintf("NDCG@100     = %.4f\n", ndcg100))
cat(sprintf("Recall@1%%    = %.4f  (前 %d 名命中 %d / %d)\n",
            recall_1pct, k_top, hits, sum(test$misstate)))
cat(sprintf("Precision@1%% = %.4f\n", precision_1pct))

# ---------- 7. 案例公司打分 ----------
cat("\n========== 案例公司 ==========\n")
cases <- d_score %>%
  filter((gvkey == 6127  & fyear == 2000) |
         (gvkey == 10787 & fyear == 2000)) %>%
  select(gvkey, fyear, misstate, mscore, DSRI, GMI, SGI, TATA, LVGI)
print(cases)

# Beneish 阈值：M > -2.22 视为可疑
threshold <- -2.22
flag_rate <- mean(test$mscore > threshold, na.rm = TRUE)
flag_recall <- mean(test$mscore[test$misstate == 1] > threshold,
                    na.rm = TRUE)
cat(sprintf("\n[阈值 M > -2.22] 测试集 flag 率 = %.3f%%, ",
            100 * flag_rate))
cat(sprintf("舞弊样本被 flag 的比例 = %.3f%%\n",
            100 * flag_recall))
