# =====================================================
# code/ch02_healy_deangelo.R
# 第 2 章数字：Healy (1985) 与 DeAngelo (1986) 两个早期模型
#
# Healy:   DA_it = TA_it - mean(TA in same fyear pool)
#          —— 用全样本年度均值作非操纵性应计的估计
# DeAngelo: DA_it = TA_it - TA_{i,t-1}
#          —— 假设上一年应计就是本年非操纵性应计
# 都把 TA 缩放到 lag_at 后计算
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
  library(ragg)
})

set.seed(2026)
source(here::here("code", "_theme.R"))
source(here::here("code", "_load_panel.R"))

p <- load_em_panel()

# ---------- Healy: 同年度均值差 ----------
healy <- p |>
  group_by(fyear) |>
  mutate(TA_year_mean = mean(TA, na.rm = TRUE),
         DA_healy = TA - TA_year_mean) |>
  ungroup()

# ---------- DeAngelo: 上一年 TA 差 ----------
deangelo <- healy |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(lag_TA = lag(TA),
         DA_deangelo = TA - lag_TA) |>
  ungroup()

dat <- deangelo

cat("======== 2.1 Healy DA 描述统计 ========\n")
healy_stats <- dat |>
  summarise(
    n      = sum(!is.na(DA_healy)),
    mean   = mean(DA_healy, na.rm = TRUE),
    median = median(DA_healy, na.rm = TRUE),
    sd     = sd(DA_healy, na.rm = TRUE),
    p10    = quantile(DA_healy, 0.10, na.rm = TRUE),
    p90    = quantile(DA_healy, 0.90, na.rm = TRUE),
    abs_mean = mean(abs(DA_healy), na.rm = TRUE)
  )
print(healy_stats, digits = 4)

cat("\n======== 2.2 DeAngelo DA 描述统计 ========\n")
deangelo_stats <- dat |>
  filter(!is.na(DA_deangelo)) |>
  summarise(
    n      = n(),
    mean   = mean(DA_deangelo, na.rm = TRUE),
    median = median(DA_deangelo, na.rm = TRUE),
    sd     = sd(DA_deangelo, na.rm = TRUE),
    p10    = quantile(DA_deangelo, 0.10, na.rm = TRUE),
    p90    = quantile(DA_deangelo, 0.90, na.rm = TRUE),
    abs_mean = mean(abs(DA_deangelo), na.rm = TRUE)
  )
print(deangelo_stats, digits = 4)

cat("\n======== 2.3 两种方法 Pearson 相关 ========\n")
corr_val <- cor(dat$DA_healy, dat$DA_deangelo,
                use = "pairwise.complete.obs")
cat(sprintf("Pearson(DA_healy, DA_deangelo) = %.4f\n", corr_val))
spear_val <- cor(dat$DA_healy, dat$DA_deangelo,
                 use = "pairwise.complete.obs", method = "spearman")
cat(sprintf("Spearman(DA_healy, DA_deangelo) = %.4f\n", spear_val))

# ---------- 2.4 案例公司打分 ----------
cat("\n======== 2.4 案例公司 DA 估计 ========\n")
case <- dat |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate, TA,
         DA_healy, DA_deangelo)

# 同 fyear 内排名分位
rank_table <- dat |>
  filter(!is.na(DA_healy), !is.na(DA_deangelo)) |>
  group_by(fyear) |>
  mutate(
    rank_healy    = percent_rank(abs(DA_healy)),
    rank_deangelo = percent_rank(abs(DA_deangelo))
  ) |>
  ungroup() |>
  filter(!is.na(company)) |>
  select(company, fyear, misstate,
         DA_healy, rank_healy,
         DA_deangelo, rank_deangelo) |>
  arrange(company, fyear)
print(rank_table, n = Inf, width = Inf)

# 案例公司在舞弊窗口内的平均分位
cat("\n======== 2.5 案例公司舞弊年份平均分位（越接近 1 越像被操纵）========\n")
fraud_rank <- rank_table |>
  filter(misstate == 1) |>
  group_by(company) |>
  summarise(
    n_year         = n(),
    mean_rank_healy    = mean(rank_healy),
    mean_rank_deangelo = mean(rank_deangelo)
  )
print(fraud_rank, digits = 4)

# ---------- 图：两种 DA 散点 ----------
fig_path <- here::here("figure", "ch02_da_scatter.png")
sub <- dat |>
  filter(!is.na(DA_healy), !is.na(DA_deangelo)) |>
  slice_sample(n = 8000)
g <- ggplot(sub, aes(x = DA_healy, y = DA_deangelo)) +
  geom_point(alpha = 0.2, size = 0.5,
             colour = em_colors$normal) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed",
              colour = em_colors$em) +
  coord_cartesian(xlim = c(-0.5, 0.5), ylim = c(-0.5, 0.5)) +
  labs(x = "DA Healy", y = "DA DeAngelo",
       title = "Healy 与 DeAngelo DA 散点（随机 8000 firm-year）",
       subtitle = sprintf("Pearson = %.3f", corr_val)) +
  theme_book()
ggsave(fig_path, plot = g, width = 5.5, height = 5,
       dpi = 300, device = ragg::agg_png)
cat(sprintf("\n图已写出：%s\n", fig_path))

# ---------- 输出案例公司打分到 csv 供累积对比表使用 ----------
out <- rank_table |>
  mutate(method_pair = "Healy/DeAngelo")
write_csv(out,
          here::here("data", "ch02_case_ranks.csv"))
cat("案例公司打分已写出：data/ch02_case_ranks.csv\n")
