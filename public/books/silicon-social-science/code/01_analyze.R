# 01_analyze.R —— silicon vs 真实回答的全套分析
# 输入：data/gss_personas.csv + data/silicon_answers.csv + data/gss_full.csv
# 输出：figure/chap*.png + data/numbers_summary.csv

suppressPackageStartupMessages({
  library(dplyr); library(tidyr); library(ggplot2)
  library(here); library(readr); library(stringr)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

# 数据
personas <- read_csv(here("data", "gss_personas.csv"), show_col_types = FALSE)
silicon  <- read_csv(here("data", "silicon_answers.csv"), show_col_types = FALSE)
gss_full <- read_csv(here("data", "gss_full.csv"), show_col_types = FALSE)

# 把 silicon 加到 personas
stopifnot(nrow(silicon) == nrow(personas))
personas$persona_id <- seq_len(nrow(personas))
silicon$persona_id  <- seq_len(nrow(silicon))
df <- left_join(personas, silicon, by = "persona_id")

cat("=== Join 后维度：", dim(df), "===\n")

# 顺序定义（用于 ordered factor）
happy_levels    <- c("Very Happy", "Pretty Happy", "Not Too Happy")
polviews_levels <- c("Extremely Liberal", "Liberal", "Slightly Liberal", "Moderate",
                     "Slightly Conservative", "Conservative", "Extremely Conservative")
partyid_levels  <- c("Strong Democrat", "Not Str Democrat", "Ind,near Dem", "Independent",
                     "Ind,near Rep", "Not Str Republican", "Strong Republican", "Other Party")

# ========== 分析 1：边际分布对比（真实 vs silicon vs 全 GSS）==========
make_marginal <- function(real_col, silicon_col, lvls, label) {
  real <- factor(df[[real_col]], levels = lvls)
  silicon <- factor(df[[silicon_col]], levels = lvls)
  full <- factor(gss_full[[real_col]], levels = lvls)
  bind_rows(
    data.frame(option = lvls, source = "真实 (n=100 subset)", pct = as.numeric(prop.table(table(real, useNA="no"))) * 100),
    data.frame(option = lvls, source = "硅基 (n=100 Claude)", pct = as.numeric(prop.table(table(silicon, useNA="no"))) * 100),
    data.frame(option = lvls, source = "GSS 全样本 (n=2867)", pct = as.numeric(prop.table(table(full, useNA="no"))) * 100)
  ) |> mutate(question = label,
              option = factor(option, levels = lvls))
}

m_happy    <- make_marginal("happy",    "happy_silicon",    happy_levels,    "happy")
m_polviews <- make_marginal("polviews", "polviews_silicon", polviews_levels, "polviews")
m_partyid  <- make_marginal("partyid",  "partyid_silicon",  partyid_levels,  "partyid")

marginal_all <- bind_rows(m_happy, m_polviews, m_partyid)
write_csv(marginal_all, here("data", "marginal_distributions.csv"))

# 图 1：三题边际分布
plot_marginal <- function(d, title) {
  ggplot(d, aes(x = option, y = pct, fill = source)) +
    geom_col(position = position_dodge(0.8), width = 0.7) +
    scale_fill_manual(values = c(COLOR_REAL, COLOR_SILICON, COLOR_GRAY)) +
    labs(title = title, x = NULL, y = "比例 (%)", fill = NULL) +
    theme_book() +
    theme(axis.text.x = element_text(angle = 30, hjust = 1, family = "Heiti TC"))
}

p1 <- plot_marginal(m_happy, "happy 题边际分布")
ggsave(here("figure", "chap03_marginal_happy.png"), p1,
       width = 8, height = 4.5, dpi = 300, device = ragg::agg_png)

p2 <- plot_marginal(m_polviews, "polviews 题边际分布（政治立场 7 档）")
ggsave(here("figure", "chap03_marginal_polviews.png"), p2,
       width = 9, height = 4.5, dpi = 300, device = ragg::agg_png)

p3 <- plot_marginal(m_partyid, "partyid 题边际分布（党派 8 档）")
ggsave(here("figure", "chap03_marginal_partyid.png"), p3,
       width = 9, height = 4.5, dpi = 300, device = ragg::agg_png)

cat("\n=== 三题边际分布图已写入 ===\n")

# ========== 分析 2：silicon vs 真实回答的格-到-格准确率（confusion-like）==========
compute_accuracy <- function(real_col, silicon_col, lvls) {
  real <- factor(df[[real_col]], levels = lvls)
  sil  <- factor(df[[silicon_col]], levels = lvls)
  ok   <- !is.na(real) & !is.na(sil)
  exact <- mean(real[ok] == sil[ok])
  # 顺序距离（仅对 polviews / happy 有意义）
  real_n <- as.numeric(real[ok])
  sil_n  <- as.numeric(sil[ok])
  mae <- mean(abs(real_n - sil_n))
  list(exact = exact, mae = mae, n_compared = sum(ok))
}

acc_happy    <- compute_accuracy("happy",    "happy_silicon",    happy_levels)
acc_polviews <- compute_accuracy("polviews", "polviews_silicon", polviews_levels)
acc_partyid  <- compute_accuracy("partyid",  "partyid_silicon",  partyid_levels)

cat("\n=== 个体级准确率 ===\n")
cat(sprintf("happy:    exact = %.1f%%  ordinal MAE = %.2f  (n = %d)\n",
            acc_happy$exact*100, acc_happy$mae, acc_happy$n_compared))
cat(sprintf("polviews: exact = %.1f%%  ordinal MAE = %.2f  (n = %d)\n",
            acc_polviews$exact*100, acc_polviews$mae, acc_polviews$n_compared))
cat(sprintf("partyid:  exact = %.1f%%  ordinal MAE = %.2f  (n = %d)\n",
            acc_partyid$exact*100, acc_partyid$mae, acc_partyid$n_compared))

# 图 4：confusion-like heatmap (polviews)
make_confusion <- function(real_col, silicon_col, lvls, fname, title) {
  d <- df |>
    mutate(real = factor(.data[[real_col]], levels = lvls),
           sil  = factor(.data[[silicon_col]], levels = lvls)) |>
    filter(!is.na(real), !is.na(sil)) |>
    count(real, sil, .drop = FALSE) |>
    group_by(real) |>
    mutate(pct = n / sum(n) * 100) |>
    ungroup()
  g <- ggplot(d, aes(x = sil, y = real, fill = pct)) +
    geom_tile() +
    geom_text(aes(label = ifelse(n > 0, n, "")), color = "white",
              family = "Times New Roman", size = 3) +
    scale_fill_gradient(low = "white", high = COLOR_SILICON, name = "% within true") +
    labs(title = title, x = "硅基 silicon 回答", y = "真实 real 回答") +
    theme_book() +
    theme(axis.text.x = element_text(angle = 30, hjust = 1, family = "Heiti TC"),
          axis.text.y = element_text(family = "Heiti TC"))
  ggsave(here("figure", fname), g, width = 8, height = 5.5, dpi = 300, device = ragg::agg_png)
}
make_confusion("polviews", "polviews_silicon", polviews_levels,
               "chap04_confusion_polviews.png", "polviews confusion matrix")
make_confusion("partyid", "partyid_silicon", partyid_levels,
               "chap04_confusion_partyid.png", "partyid confusion matrix")
make_confusion("happy", "happy_silicon", happy_levels,
               "chap04_confusion_happy.png", "happy confusion matrix")

# ========== 分析 3：按 demographic 分组的 representation gap ==========
# 看 silicon 在哪些 demographic 子群上更准 / 更偏
df$polviews_ord    <- as.numeric(factor(df$polviews, levels = polviews_levels))
df$polviews_si_ord <- as.numeric(factor(df$polviews_silicon, levels = polviews_levels))
df$partyid_ord     <- as.numeric(factor(df$partyid, levels = partyid_levels))
df$partyid_si_ord  <- as.numeric(factor(df$partyid_silicon, levels = partyid_levels))

# 按 race × sex 算两题平均 ordinal bias
group_bias <- df |>
  filter(!is.na(polviews_ord), !is.na(polviews_si_ord),
         !is.na(partyid_ord),  !is.na(partyid_si_ord)) |>
  group_by(race, sex) |>
  summarise(n = n(),
            pol_bias = mean(polviews_si_ord - polviews_ord),
            party_bias = mean(partyid_si_ord - partyid_ord),
            .groups = "drop")
cat("\n=== Race × Sex 子群偏差（正值 = silicon 偏保守 / 共和） ===\n")
print(group_bias)
write_csv(group_bias, here("data", "group_bias.csv"))

g_bias <- group_bias |>
  pivot_longer(c(pol_bias, party_bias), names_to = "metric", values_to = "bias") |>
  mutate(metric = recode(metric, pol_bias = "polviews", party_bias = "partyid"))
p_bias <- ggplot(g_bias, aes(x = interaction(race, sex, sep = " · "), y = bias, fill = metric)) +
  geom_col(position = position_dodge(0.7), width = 0.6) +
  geom_hline(yintercept = 0, color = "black", linewidth = 0.3) +
  scale_fill_manual(values = c(polviews = COLOR_SILICON, partyid = COLOR_REAL)) +
  labs(title = "silicon - real ordinal bias，按 race × sex 子群",
       x = NULL, y = "ordinal bias（正 = silicon 估高）", fill = NULL) +
  theme_book() +
  theme(axis.text.x = element_text(angle = 30, hjust = 1, family = "Heiti TC"))
ggsave(here("figure", "chap05_group_bias.png"), p_bias,
       width = 9, height = 4.5, dpi = 300, device = ragg::agg_png)

# ========== 分析 4：中心收缩诊断（central-collapse） ==========
# 真实 polviews 标准差 vs silicon polviews 标准差
sd_real <- sd(df$polviews_ord, na.rm = TRUE)
sd_sil  <- sd(df$polviews_si_ord, na.rm = TRUE)
cat(sprintf("\n=== 中心收缩诊断 ===\n真实 polviews 标准差 = %.2f\nsilicon polviews 标准差 = %.2f\n收缩比 = %.2f\n",
            sd_real, sd_sil, sd_sil/sd_real))

# 极端档（Extremely Liberal + Extremely Conservative + Liberal + Conservative）占比
extreme_real <- mean(df$polviews_ord %in% c(1, 2, 6, 7), na.rm = TRUE)
extreme_sil  <- mean(df$polviews_si_ord %in% c(1, 2, 6, 7), na.rm = TRUE)
cat(sprintf("真实极端档占比 = %.1f%%\nsilicon 极端档占比 = %.1f%%\n",
            extreme_real*100, extreme_sil*100))

# 中位 Moderate 档占比
mod_real <- mean(df$polviews_ord == 4, na.rm = TRUE)
mod_sil  <- mean(df$polviews_si_ord == 4, na.rm = TRUE)
cat(sprintf("真实 Moderate 占比 = %.1f%%\nsilicon Moderate 占比 = %.1f%%\n",
            mod_real*100, mod_sil*100))

# ========== 输出数字汇总 ==========
nums <- data.frame(
  metric = c("acc_happy_exact",  "acc_polviews_exact", "acc_partyid_exact",
             "mae_happy",        "mae_polviews",       "mae_partyid",
             "sd_polviews_real", "sd_polviews_silicon", "shrinkage_ratio",
             "extreme_real_pct", "extreme_silicon_pct",
             "moderate_real_pct","moderate_silicon_pct"),
  value  = c(acc_happy$exact, acc_polviews$exact, acc_partyid$exact,
             acc_happy$mae,   acc_polviews$mae,   acc_partyid$mae,
             sd_real, sd_sil, sd_sil/sd_real,
             extreme_real, extreme_sil, mod_real, mod_sil)
)
write_csv(nums, here("data", "numbers_summary.csv"))
cat("\n=== numbers_summary.csv ===\n")
print(nums)

cat("\nDONE 01_analyze.R\n")
