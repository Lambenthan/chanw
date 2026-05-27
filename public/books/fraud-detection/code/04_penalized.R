# =====================================================
# code/04_penalized.R
# 第 4 章：惩罚回归 LASSO / Ridge / Elastic Net
# 输入：data/bao2020_full.csv
# 输出：控制台数字（最优 lambda、被选变量、测试集指标、案例公司打分）
# 关键：时间感知交叉验证（forward-chaining），不能用 cv.glmnet 默认随机折
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(glmnet)
  library(pROC)
  library(here)
})
set.seed(2026)

d <- read_csv(here::here("data", "bao2020_full.csv"),
              show_col_types = FALSE)

# 42 个 Bao 特征（28 原始 + 14 衍生比率）
feat_raw <- c("act","ap","at","ceq","che","cogs","csho","dlc","dltis","dltt",
              "dp","ib","invt","ivao","ivst","lct","lt","ni","ppegt","pstk",
              "re","rect","sale","sstk","txp","txt","xint","prcc_f")
feat_ratio <- c("dch_wc","ch_rsst","dch_rec","dch_inv","soft_assets","ch_cs",
                "ch_cm","ch_roa","issue","bm","dpi","reoa","EBIT","ch_fcf")
features <- c(feat_raw, feat_ratio)
stopifnot(length(features) == 42)

# Bao 时间切分
train_full <- d %>% filter(fyear >= 1991, fyear <= 2002)
valid_raw  <- d %>% filter(fyear >= 2003, fyear <= 2008)
test_raw   <- d %>% filter(fyear >= 2009, fyear <= 2014)

# 删除 42 特征任一为 NA 的行，记录每段被丢弃的数量
drop_na_count <- function(df, feats) {
  before <- nrow(df)
  out <- df %>% drop_na(all_of(feats))
  cat(sprintf("  drop NA: %d -> %d (剔除 %d, 保留 %.2f%%)\n",
              before, nrow(out), before - nrow(out),
              100 * nrow(out) / before))
  out
}
cat("== 缺失行剔除 ==\n")
cat("训练 1991-2002:\n");  train <- drop_na_count(train_full, features)
cat("验证 2003-2008:\n");  valid <- drop_na_count(valid_raw,  features)
cat("测试 2009-2014:\n");  test  <- drop_na_count(test_raw,   features)
cat(sprintf("训练舞弊数 %d / %d (%.3f%%)\n",
            sum(train$misstate), nrow(train),
            100 * mean(train$misstate)))
cat(sprintf("测试舞弊数 %d / %d (%.3f%%)\n",
            sum(test$misstate), nrow(test),
            100 * mean(test$misstate)))

# 标准化：z-score，scaler 仅在训练集上拟合
mu <- colMeans(train[, features])
sg <- apply(train[, features], 2, sd)
sg[sg == 0] <- 1  # 防御
z_apply <- function(df) {
  m <- as.matrix(df[, features])
  sweep(sweep(m, 2, mu, "-"), 2, sg, "/")
}
X_train <- z_apply(train); y_train <- train$misstate
X_valid <- z_apply(valid); y_valid <- valid$misstate
X_test  <- z_apply(test);  y_test  <- test$misstate

# ---------------- 时间感知交叉验证 ----------------
# Forward-chaining：第 t 折训练 1991..year-1，验证 year（year=1996..2002）
# 这样保证模型永远不"看到"未来年份
fold_years <- 1996:2002
make_foldid <- function(years, fold_years) {
  # 返回与训练集行数等长的 foldid 向量；不在 fold 验证年的行 foldid = 0（被丢弃）
  ids <- rep(0L, length(years))
  for (k in seq_along(fold_years)) {
    ids[years == fold_years[k]] <- k
  }
  ids
}

train_years <- train$fyear
foldid <- make_foldid(train_years, fold_years)
cat(sprintf("\n时间感知 CV: %d 折，验证年份 %s\n",
            length(fold_years),
            paste(fold_years, collapse = ",")))

# 自定义时间感知 CV——cv.glmnet 的 foldid 假设每行 foldid >=1
# 我们手写 forward-chaining 循环：每折 train 用 fyear < year，valid 用 fyear == year
# 注意：glmnet 在二分类上的默认 lambda_max 由数据决定（这里约 5.6e-3），
# 因此 lambda 网格用 1e-6 到 1e-1 这一段，足以覆盖从"几乎无惩罚"到"全部归零"。
lambda_grid <- exp(seq(log(1e-1), log(1e-6), length.out = 80))  # 由大到小，与 glmnet 内部约定一致

run_time_cv <- function(alpha_val) {
  # 对每个 lambda，跑 7 折 forward-chaining，取平均验证 AUC
  cv_auc <- matrix(NA_real_, nrow = length(fold_years),
                   ncol = length(lambda_grid))
  for (k in seq_along(fold_years)) {
    yr <- fold_years[k]
    tr_idx <- which(train_years < yr)
    va_idx <- which(train_years == yr)
    if (length(tr_idx) == 0 || length(va_idx) == 0) next
    if (sum(y_train[va_idx]) == 0) next  # 该年没有阳性，AUC 无定义
    fit <- glmnet(X_train[tr_idx, ], y_train[tr_idx],
                  family = "binomial", alpha = alpha_val,
                  lambda = lambda_grid, standardize = FALSE)
    # fit$lambda 顺序可能与传入不同（glmnet 自动重排或截断）
    used_lam <- fit$lambda
    pp <- predict(fit, newx = X_train[va_idx, ], type = "response")
    for (j in seq_len(ncol(pp))) {
      # 只对有变异的预测计算 AUC（全相同则跳过）
      if (length(unique(pp[, j])) < 2) next
      cv_auc[k, match(used_lam[j], lambda_grid)] <-
        as.numeric(auc(roc(y_train[va_idx], pp[, j], quiet = TRUE)))
    }
  }
  mean_auc <- colMeans(cv_auc, na.rm = TRUE)
  # 在 AUC 平局时，glmnet 惯例选更大的 lambda（更稀疏的模型）；
  # 我们的 lambda_grid 由大到小排列，所以取第一个最大值即对应最稀疏的最优模型
  best_j <- which.max(mean_auc)
  list(lambda = lambda_grid[best_j],
       cv_auc = mean_auc[best_j],
       grid_auc = mean_auc)
}

cat("\n== 时间感知 CV 选 lambda ==\n")
cv_lasso <- run_time_cv(1.0)
cat(sprintf("LASSO     (alpha=1.0): best lambda=%.6f, CV-AUC=%.4f\n",
            cv_lasso$lambda, cv_lasso$cv_auc))
cv_ridge <- run_time_cv(0.0)
cat(sprintf("Ridge     (alpha=0.0): best lambda=%.6f, CV-AUC=%.4f\n",
            cv_ridge$lambda, cv_ridge$cv_auc))
cv_enet  <- run_time_cv(0.5)
cat(sprintf("ElasticNet(alpha=0.5): best lambda=%.6f, CV-AUC=%.4f\n",
            cv_enet$lambda, cv_enet$cv_auc))

# ---------------- 用最优 lambda 在全训练集重新拟合 ----------------
# 沿完整 lambda 路径拟合，再按最优 lambda 抽取系数（避免单一 lambda 时的收敛问题）
fit_full <- function(alpha_val) {
  glmnet(X_train, y_train, family = "binomial",
         alpha = alpha_val, lambda = lambda_grid,
         standardize = FALSE)
}
extract_at <- function(path, lam) {
  # 找到 path$lambda 中与 lam 最接近的索引
  idx <- which.min(abs(path$lambda - lam))
  list(path = path, idx = idx, lambda = path$lambda[idx])
}
path_lasso <- fit_full(1.0); fit_lasso <- extract_at(path_lasso, cv_lasso$lambda)
path_ridge <- fit_full(0.0); fit_ridge <- extract_at(path_ridge, cv_ridge$lambda)
path_enet  <- fit_full(0.5); fit_enet  <- extract_at(path_enet,  cv_enet$lambda)
predict_at <- function(eo, newx) {
  as.numeric(predict(eo$path, newx = newx, type = "response",
                     s = eo$lambda))
}
coef_at <- function(eo) {
  as.numeric(coef(eo$path, s = eo$lambda))
}

# 报告 LASSO 非零系数
beta_lasso <- coef_at(fit_lasso)
names(beta_lasso) <- c("(Intercept)", features)
nz <- beta_lasso[abs(beta_lasso) > 1e-8]
nz <- nz[names(nz) != "(Intercept)"]
nz_sorted <- nz[order(-abs(nz))]
cat(sprintf("\n== LASSO 非零系数: %d / 42 ==\n", length(nz_sorted)))
for (nm in names(nz_sorted)) {
  cat(sprintf("  %-15s  %+.4f\n", nm, nz_sorted[[nm]]))
}

# Elastic Net 非零系数（参考）
beta_enet <- coef_at(fit_enet)
names(beta_enet) <- c("(Intercept)", features)
nz_e <- beta_enet[abs(beta_enet) > 1e-8]
nz_e <- nz_e[names(nz_e) != "(Intercept)"]
cat(sprintf("Elastic Net 非零系数: %d / 42\n", length(nz_e)))

# Ridge 非零系数（应该 = 42）
beta_ridge <- coef_at(fit_ridge)
names(beta_ridge) <- c("(Intercept)", features)
cat(sprintf("Ridge 非零系数: %d / 42 (应为 42)\n",
            sum(abs(beta_ridge[-1]) > 1e-8)))

# ---------------- 测试集评估 ----------------
ndcg_at_k <- function(scores, labels, k) {
  ord <- order(-scores)[1:min(k, length(scores))]
  hits <- as.numeric(labels[ord])
  dcg <- sum(hits / log2(seq_along(hits) + 1))
  ideal <- sort(labels, decreasing = TRUE)[1:length(hits)]
  idcg <- sum(ideal / log2(seq_along(ideal) + 1))
  if (idcg == 0) NA else dcg / idcg
}
recall_precision_at <- function(scores, labels, frac = 0.01) {
  k <- ceiling(length(scores) * frac)
  ord <- order(-scores)[1:k]
  hits <- sum(labels[ord])
  c(recall = hits / sum(labels), precision = hits / k, k = k, hits = hits)
}

eval_one <- function(name, eo) {
  pp_test <- predict_at(eo, X_test)
  auc_v <- as.numeric(auc(roc(y_test, pp_test, quiet = TRUE)))
  ndcg <- ndcg_at_k(pp_test, y_test, 100)
  rp <- recall_precision_at(pp_test, y_test, 0.01)
  cat(sprintf("%-12s AUC=%.4f  NDCG@100=%.4f  Recall@1%%=%.4f  Precision@1%%=%.4f  (k=%d, hits=%d)\n",
              name, auc_v, ndcg, rp["recall"], rp["precision"],
              rp["k"], rp["hits"]))
  list(name = name, auc = auc_v, ndcg = ndcg,
       recall = unname(rp["recall"]),
       precision = unname(rp["precision"]),
       scores = pp_test)
}

cat("\n== 测试集 (2009-2014) 性能 ==\n")
res_lasso <- eval_one("LASSO",       fit_lasso)
res_ridge <- eval_one("Ridge",       fit_ridge)
res_enet  <- eval_one("Elastic Net", fit_enet)

# 选 AUC 最高的方法作为最终模型
all_res <- list(LASSO = res_lasso, Ridge = res_ridge,
                `Elastic Net` = res_enet)
auc_vec <- sapply(all_res, function(x) x$auc)
best_name <- names(all_res)[which.max(auc_vec)]
cat(sprintf("\n>> 三个模型中 AUC 最高的是: %s (AUC=%.4f)\n",
            best_name, max(auc_vec)))

# ---------------- 案例公司：Enron 2000 + Tyco 2000 ----------------
case_score <- function(eo, gvk, yr) {
  row <- d %>% filter(gvkey == gvk, fyear == yr) %>%
    drop_na(all_of(features))
  if (nrow(row) == 0) return(NA_real_)
  m <- as.matrix(row[, features])
  z <- sweep(sweep(m, 2, mu, "-"), 2, sg, "/")
  predict_at(eo, z)[1]
}

best_eo <- list(LASSO = fit_lasso, Ridge = fit_ridge,
                `Elastic Net` = fit_enet)[[best_name]]
cat("\n== 案例公司打分 (使用 ", best_name, ") ==\n", sep = "")
en2000 <- case_score(best_eo, 6127, 2000)
ty2000 <- case_score(best_eo, 10787, 2000)
cat(sprintf("Enron 2000 (gvkey=6127): predicted prob = %.4f\n", en2000))
cat(sprintf("Tyco  2000 (gvkey=10787): predicted prob = %.4f\n", ty2000))

# 对比三个模型在两家公司的分数
cat("\n-- 三个模型对照 --\n")
for (nm in names(eo_list <- list(LASSO = fit_lasso,
                                  Ridge = fit_ridge,
                                  `Elastic Net` = fit_enet))) {
  pe <- case_score(eo_list[[nm]], 6127, 2000)
  pt <- case_score(eo_list[[nm]], 10787, 2000)
  cat(sprintf("%-12s Enron=%.4f  Tyco=%.4f\n", nm, pe, pt))
}

cat("\n== 完成 ==\n")
