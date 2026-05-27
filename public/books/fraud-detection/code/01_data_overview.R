# =====================================================
# code/01_data_overview.R
# 第 1 章：数据概览与零模型基线
# 输入：data/bao2020_full.csv
# 输出：控制台数字（写入 _NUMBERS.md Chap 1 节）
# =====================================================

library(tidyverse)
library(here)
set.seed(2026)

d <- read_csv(here::here("data", "bao2020_full.csv"),
              show_col_types = FALSE)

# 全样本规模
cat(sprintf("全样本: %d firm-years, %d 公司, fyear %d-%d\n",
            nrow(d), n_distinct(d$gvkey),
            min(d$fyear), max(d$fyear)))

cat(sprintf("misstate=1: %d (%.4f%%)\n",
            sum(d$misstate), 100 * mean(d$misstate)))

# Bao 时间切分
splits <- list(
  train = d %>% filter(fyear >= 1991, fyear <= 2002),
  valid = d %>% filter(fyear >= 2003, fyear <= 2008),
  test  = d %>% filter(fyear >= 2009, fyear <= 2014)
)
for (name in names(splits)) {
  s <- splits[[name]]
  cat(sprintf("%s: n=%d, fraud=%d, rate=%.3f%%\n",
              name, nrow(s), sum(s$misstate),
              100 * mean(s$misstate)))
}

# Enron (gvkey=6127) 关键年度
cat("\n--- Enron (gvkey=6127) ---\n")
d %>% filter(gvkey == 6127) %>%
  arrange(fyear) %>%
  select(fyear, misstate, p_aaer, at, sale, ni) %>%
  print(n = Inf)

# 零模型在测试集上的指标
test <- splits$test
n_test <- nrow(test)
n_pos  <- sum(test$misstate)
cat(sprintf("\n零模型: AUC=0.500, Recall@1%%=0, Precision@1%%=0\n"))
cat(sprintf("测试集 n=%d, 阳性=%d, 1%% 名额=%d\n",
            n_test, n_pos, ceiling(n_test * 0.01)))
