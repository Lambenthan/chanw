# =====================================================
# code/03_logistic_fscore.R
# 第 3 章：逻辑回归 + Dechow F-Score
# Model A：42 个特征全集（28 原始 + 14 衍生比率）
# Model B：Dechow et al. 2011 Table 7 Model 1 的 7 变量
# 输出：测试集 AUC / NDCG@100 / Recall@1% / Precision@1%
#       Enron (gvkey=6127) 与 Tyco (gvkey=10787) 在 fyear=2000 的打分
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
  library(pROC)
})

set.seed(2026)

# ---------- 数据加载 ----------
d <- read_csv(here::here("data", "bao2020_full.csv"),
              show_col_types = FALSE)

cat(sprintf("原始数据: %d firm-years\n", nrow(d)))

# 28 原始 Compustat + 14 衍生比率 = 42 特征
raw_vars <- c("act","ap","at","ceq","che","cogs","csho","dlc","dltis","dltt",
              "dp","ib","invt","ivao","ivst","lct","lt","ni","ppegt","pstk",
              "re","rect","sale","sstk","txp","txt","xint","prcc_f")
ratio_vars <- c("dch_wc","ch_rsst","dch_rec","dch_inv","soft_assets",
                "ch_cs","ch_cm","ch_roa","issue","bm","dpi","reoa","EBIT","ch_fcf")
all_vars  <- c(raw_vars, ratio_vars)

# Dechow 2011 Table 7 Model 1 的 7 个变量
dechow_vars <- c("ch_rsst","dch_rec","dch_inv","soft_assets",
                 "ch_cs","ch_roa","issue")

# ---------- 切分前先过滤可用样本 ----------
d_full <- d %>% drop_na(all_of(all_vars))
d_dech <- d %>% drop_na(all_of(dechow_vars))

cat(sprintf("Model A 可用 (42 特征无 NA): %d 行 (丢 %d)\n",
            nrow(d_full), nrow(d) - nrow(d_full)))
cat(sprintf("Model B 可用 (7 特征无 NA): %d 行 (丢 %d)\n",
            nrow(d_dech), nrow(d) - nrow(d_dech)))

split_set <- function(df) {
  list(
    train = df %>% filter(fyear >= 1991, fyear <= 2002),
    valid = df %>% filter(fyear >= 2003, fyear <= 2008),
    test  = df %>% filter(fyear >= 2009, fyear <= 2014)
  )
}

sA <- split_set(d_full)
sB <- split_set(d_dech)

cat(sprintf("Model A 切分: train=%d (fraud=%d), valid=%d (fraud=%d), test=%d (fraud=%d)\n",
            nrow(sA$train), sum(sA$train$misstate),
            nrow(sA$valid), sum(sA$valid$misstate),
            nrow(sA$test),  sum(sA$test$misstate)))
cat(sprintf("Model B 切分: train=%d (fraud=%d), valid=%d (fraud=%d), test=%d (fraud=%d)\n",
            nrow(sB$train), sum(sB$train$misstate),
            nrow(sB$valid), sum(sB$valid$misstate),
            nrow(sB$test),  sum(sB$test$misstate)))

# ---------- 评估函数 ----------
eval_metrics <- function(scores, labels, k = 100, p = 0.01) {
  ord <- order(-scores)
  s_ord <- scores[ord]; y_ord <- labels[ord]
  n <- length(labels); n_pos <- sum(labels)
  # AUC
  auc <- as.numeric(pROC::auc(pROC::roc(labels, scores,
                                        quiet = TRUE, direction = "<")))
  # NDCG@k
  rel <- y_ord[seq_len(min(k, n))]
  dcg <- sum(rel / log2(seq_along(rel) + 1))
  ideal <- c(rep(1, min(k, n_pos)), rep(0, max(k - n_pos, 0)))
  idcg <- sum(ideal / log2(seq_along(ideal) + 1))
  ndcg <- if (idcg > 0) dcg / idcg else 0
  # Recall@p / Precision@p
  k_p <- ceiling(n * p)
  hit <- sum(y_ord[seq_len(k_p)])
  recall_p <- hit / n_pos
  prec_p   <- hit / k_p
  list(AUC = auc, NDCG = ndcg, RecallP = recall_p, PrecP = prec_p,
       k_p = k_p, hit = hit, n = n, n_pos = n_pos)
}

# ---------- Model A: 42 特征全集 ----------
cat("\n========== Model A: 42 特征全集 ==========\n")
form_A <- as.formula(paste("misstate ~", paste(all_vars, collapse = " + ")))
mA <- glm(form_A, data = sA$train, family = binomial)

predA_test <- predict(mA, newdata = sA$test, type = "response")
metA <- eval_metrics(predA_test, sA$test$misstate)
cat(sprintf("Model A 测试集: AUC=%.4f  NDCG@100=%.4f  Recall@1%%=%.4f  Precision@1%%=%.4f\n",
            metA$AUC, metA$NDCG, metA$RecallP, metA$PrecP))
cat(sprintf("  测试 n=%d, 阳性=%d, 1%% 名额=%d, 命中=%d\n",
            metA$n, metA$n_pos, metA$k_p, metA$hit))

# ---------- Model B: Dechow 7 变量 ----------
cat("\n========== Model B: Dechow F-Score 7 变量 ==========\n")
form_B <- as.formula(paste("misstate ~", paste(dechow_vars, collapse = " + ")))
mB <- glm(form_B, data = sB$train, family = binomial)

cat("\n--- Dechow 7 变量系数 ---\n")
coef_tbl <- summary(mB)$coefficients
print(round(coef_tbl, 6))

predB_test <- predict(mB, newdata = sB$test, type = "response")
metB <- eval_metrics(predB_test, sB$test$misstate)
cat(sprintf("\nModel B 测试集: AUC=%.4f  NDCG@100=%.4f  Recall@1%%=%.4f  Precision@1%%=%.4f\n",
            metB$AUC, metB$NDCG, metB$RecallP, metB$PrecP))
cat(sprintf("  测试 n=%d, 阳性=%d, 1%% 名额=%d, 命中=%d\n",
            metB$n, metB$n_pos, metB$k_p, metB$hit))

# F-Score = 预测概率 / 无条件舞弊率
uncond_rate <- mean(sB$train$misstate)
cat(sprintf("\nModel B 训练集无条件舞弊率: %.6f\n", uncond_rate))

# ---------- 案例公司：Enron 2000 / Tyco 2000 ----------
cat("\n========== 案例公司 fyear=2000 打分 ==========\n")

case_score <- function(model, df_split_test, src_df, gvkey_v, fyear_v) {
  row <- src_df %>% filter(gvkey == gvkey_v, fyear == fyear_v)
  if (nrow(row) == 0) return(NA_real_)
  predict(model, newdata = row, type = "response")
}

# 用切分前的"可用样本"取案例公司行
enron_A <- case_score(mA, NULL, d_full,  6127, 2000)
tyco_A  <- case_score(mA, NULL, d_full, 10787, 2000)
enron_B <- case_score(mB, NULL, d_dech,  6127, 2000)
tyco_B  <- case_score(mB, NULL, d_dech, 10787, 2000)

cat(sprintf("Enron 2000 (gvkey=6127):  Model A p=%.4f, Model B p=%.4f, F-Score=%.2f\n",
            enron_A, enron_B, enron_B / uncond_rate))
cat(sprintf("Tyco  2000 (gvkey=10787): Model A p=%.4f, Model B p=%.4f, F-Score=%.2f\n",
            tyco_A,  tyco_B,  tyco_B  / uncond_rate))

# ---------- 测试期排名分位 ----------
rank_pos <- function(scores, target) {
  ord <- order(-scores)
  which(ord == target)
}

cat("\n========== 写入汇总 ==========\n")
cat(sprintf("[A] AUC=%.4f  NDCG=%.4f  R@1%%=%.4f  P@1%%=%.4f\n",
            metA$AUC, metA$NDCG, metA$RecallP, metA$PrecP))
cat(sprintf("[B] AUC=%.4f  NDCG=%.4f  R@1%%=%.4f  P@1%%=%.4f\n",
            metB$AUC, metB$NDCG, metB$RecallP, metB$PrecP))
cat("Done.\n")
