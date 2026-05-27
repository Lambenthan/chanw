# =====================================================
# code/05_rf.R
# 第 5 章：决策树与随机森林
# 输入：data/bao2020_full.csv
# 输出：单棵 rpart 树（depth=5）+ ranger 随机森林（500 棵，mtry=6）
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(rpart)
  library(ranger)
  library(pROC)
  library(here)
})

set.seed(2026)

# ---------- 1. 数据 ----------

d <- read_csv(here::here("data", "bao2020_full.csv"),
              show_col_types = FALSE)

# 28 个原始 + 14 个衍生比率 = 42 个特征
features_raw <- c("act","ap","at","ceq","che","cogs","csho","dlc","dltis",
                  "dltt","dp","ib","invt","ivao","ivst","lct","lt","ni",
                  "ppegt","pstk","re","rect","sale","sstk","txp","txt",
                  "xint","prcc_f")
features_ratio <- c("dch_wc","ch_rsst","dch_rec","dch_inv","soft_assets",
                    "ch_cs","ch_cm","ch_roa","issue","bm","dpi","reoa",
                    "EBIT","ch_fcf")
features <- c(features_raw, features_ratio)
stopifnot(length(features) == 42)

# 时间分割
train <- d %>% filter(fyear >= 1991, fyear <= 2002)
valid <- d %>% filter(fyear >= 2003, fyear <= 2008)
test  <- d %>% filter(fyear >= 2009, fyear <= 2014)

# 丢弃任意特征列含 NA 的行（rpart / ranger 不接受 NA）
n_train_before <- nrow(train)
n_test_before  <- nrow(test)

train_c <- train %>%
  drop_na(any_of(features)) %>%
  mutate(misstate = factor(misstate, levels = c(0, 1)))
test_c  <- test %>%
  drop_na(any_of(features)) %>%
  mutate(misstate = factor(misstate, levels = c(0, 1)))

cat(sprintf("训练集: %d -> %d (drop %d NA-rows), fraud %d\n",
            n_train_before, nrow(train_c),
            n_train_before - nrow(train_c),
            sum(as.integer(as.character(train_c$misstate)))))
cat(sprintf("测试集: %d -> %d (drop %d NA-rows), fraud %d\n",
            n_test_before, nrow(test_c),
            n_test_before - nrow(test_c),
            sum(as.integer(as.character(test_c$misstate)))))

# 拼公式
fml <- as.formula(paste("misstate ~", paste(features, collapse = " + ")))

# ---------- 2. 单棵决策树（depth = 5） ----------

cat("\n========== 单棵决策树 rpart, maxdepth=5 ==========\n")
t0 <- Sys.time()
tree_fit <- rpart(
  fml,
  data    = train_c,
  method  = "class",
  control = rpart.control(maxdepth = 5, cp = 0.001, minsplit = 30)
)
t1 <- Sys.time()
tree_time <- as.numeric(difftime(t1, t0, units = "secs"))
cat(sprintf("单棵树训练时间: %.3f 秒\n", tree_time))

# 打印树结构（截断版）
cat("\n--- 树结构 ---\n")
print(tree_fit)

# 取前几条 split（变量重要性 + 节点）
cat("\n--- splits 摘要（按变量重要性） ---\n")
print(round(tree_fit$variable.importance, 2))

# 测试集预测概率
tree_prob_test <- predict(tree_fit, newdata = test_c, type = "prob")[, "1"]

# ---------- 3. 随机森林（ranger, 500 trees, mtry=6） ----------

cat("\n========== 随机森林 ranger, 500 trees, mtry=6 ==========\n")
t0 <- Sys.time()
rf_fit <- ranger(
  formula        = fml,
  data           = train_c,
  num.trees      = 500,
  mtry           = 6,
  min.node.size  = 5,
  classification = TRUE,
  probability    = TRUE,
  importance     = "impurity",      # MDI
  seed           = 2026,
  num.threads    = 4
)
t1 <- Sys.time()
rf_time <- as.numeric(difftime(t1, t0, units = "secs"))
cat(sprintf("随机森林训练时间: %.2f 秒\n", rf_time))
cat(sprintf("OOB prediction error: %.6f\n", rf_fit$prediction.error))

# 测试集预测概率
rf_prob_test <- predict(rf_fit, data = test_c)$predictions[, "1"]

# 再训练一个 permutation importance 模型
cat("\n========== 训练第二个 RF 用于 permutation importance ==========\n")
t0 <- Sys.time()
rf_perm <- ranger(
  formula        = fml,
  data           = train_c,
  num.trees      = 500,
  mtry           = 6,
  min.node.size  = 5,
  classification = TRUE,
  probability    = TRUE,
  importance     = "permutation",   # MDA
  seed           = 2026,
  num.threads    = 4
)
t1 <- Sys.time()
cat(sprintf("permutation importance 训练时间: %.2f 秒\n",
            as.numeric(difftime(t1, t0, units = "secs"))))

# ---------- 4. 评估指标 ----------

eval_metrics <- function(prob, label, name) {
  label <- as.integer(as.character(label))
  # AUC
  roc_obj <- roc(label, prob, quiet = TRUE)
  auc_val <- as.numeric(auc(roc_obj))

  # NDCG@100
  k <- 100
  ord <- order(prob, decreasing = TRUE)
  hits <- label[ord]
  dcg <- sum(hits[1:k] / log2(seq_len(k) + 1))
  ideal_hits <- sort(label, decreasing = TRUE)[1:k]
  idcg <- sum(ideal_hits / log2(seq_len(k) + 1))
  ndcg <- dcg / idcg

  # 1% cutoff
  topk <- max(1, ceiling(0.01 * length(prob)))
  topk_hits <- sum(label[ord][1:topk])
  recall_1 <- topk_hits / sum(label)
  prec_1   <- topk_hits / topk

  cat(sprintf("[%s] AUC=%.4f  NDCG@100=%.4f  Recall@1%%=%.4f  Precision@1%%=%.4f\n",
              name, auc_val, ndcg, recall_1, prec_1))

  list(auc = auc_val, ndcg = ndcg,
       recall1 = recall_1, prec1 = prec_1, topk = topk)
}

cat("\n========== 测试集性能 ==========\n")
m_tree <- eval_metrics(tree_prob_test, test_c$misstate, "单棵树 maxdepth=5")
m_rf   <- eval_metrics(rf_prob_test,   test_c$misstate, "随机森林 ranger")

# ---------- 5. 变量重要性 top-10（MDI 与 MDA） ----------

cat("\n========== RF 变量重要性 Top-10 (MDI = impurity) ==========\n")
imp_mdi <- sort(rf_fit$variable.importance, decreasing = TRUE)
print(round(imp_mdi[1:10], 4))

cat("\n========== RF 变量重要性 Top-10 (MDA = permutation) ==========\n")
imp_mda <- sort(rf_perm$variable.importance, decreasing = TRUE)
print(round(imp_mda[1:10], 6))

# ---------- 6. 案例公司打分 ----------

case_rows <- d %>%
  filter((gvkey == 6127  & fyear == 2000) |
         (gvkey == 10787 & fyear == 2000)) %>%
  drop_na(any_of(features)) %>%
  mutate(misstate = factor(misstate, levels = c(0, 1)))

if (nrow(case_rows) > 0) {
  case_prob <- predict(rf_fit, data = case_rows)$predictions[, "1"]
  cat("\n========== 案例公司 RF 舞弊概率（fyear=2000） ==========\n")
  for (i in seq_len(nrow(case_rows))) {
    name <- if (case_rows$gvkey[i] == 6127) "Enron" else "Tyco International"
    cat(sprintf("%-22s gvkey=%d  fyear=%d  misstate=%s  RF p(misstate=1)=%.4f\n",
                name, case_rows$gvkey[i], case_rows$fyear[i],
                as.character(case_rows$misstate[i]), case_prob[i]))
  }
} else {
  cat("\n[警告] 案例公司行被 NA 过滤掉了\n")
}

# ---------- 7. 汇总打印 ----------

cat("\n========== 汇总 ==========\n")
cat(sprintf("单棵树训练时间: %.3f 秒\n", tree_time))
cat(sprintf("随机森林训练时间: %.2f 秒\n", rf_time))
cat(sprintf("OOB error: %.4f%%\n", 100 * rf_fit$prediction.error))
cat(sprintf("OOB accuracy: %.4f%%\n", 100 * (1 - rf_fit$prediction.error)))
cat(sprintf("[zero baseline 测试集舞弊率: %.4f%%]\n",
            100 * mean(as.integer(as.character(test_c$misstate)))))
