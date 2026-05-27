# =====================================================
# code/ch01_overview.R
# 第 1 章数字：样本概览、TA 描述统计、案例公司切片
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

cat("======== 1.1 样本规模 ========\n")
cat(sprintf("firm-year 总数：           %d\n", nrow(p)))
cat(sprintf("公司数：                    %d\n", n_distinct(p$gvkey)))
cat(sprintf("时间跨度：                  %d-%d\n",
            min(p$fyear), max(p$fyear)))
cat(sprintf("AAER 涉案 firm-year：       %d (%.2f%%)\n",
            sum(p$misstate == 1),
            100 * mean(p$misstate == 1)))
cat(sprintf("AAER 涉案公司数：           %d\n",
            n_distinct(p$gvkey[p$misstate == 1])))

cat("\n======== 1.2 年份分布（前后 5 年）========\n")
yr_count <- p |> count(fyear)
print(rbind(head(yr_count, 5), tail(yr_count, 5)))
cat(sprintf("年均 firm-year：%.0f\n", mean(yr_count$n)))

cat("\n======== 1.3 总应计 TA 描述统计 ========\n")
ta_stats <- p |>
  summarise(
    mean   = mean(TA, na.rm = TRUE),
    median = median(TA, na.rm = TRUE),
    sd     = sd(TA, na.rm = TRUE),
    q1     = quantile(TA, 0.25, na.rm = TRUE),
    q3     = quantile(TA, 0.75, na.rm = TRUE),
    p10    = quantile(TA, 0.10, na.rm = TRUE),
    p90    = quantile(TA, 0.90, na.rm = TRUE)
  )
print(ta_stats, digits = 4)

cat("\n======== 1.4 案例公司切片 ========\n")
case_slice <- p |>
  filter(!is.na(company)) |>
  select(company, fyear, at, sale, ib, TA, ROA, misstate) |>
  arrange(company, fyear)
print(case_slice, n = Inf, width = Inf)

# ---------- 图：TA 全样本分布 ----------
fig_path <- here::here("figure", "ch01_ta_distribution.png")
g <- p |>
  ggplot(aes(x = TA)) +
  geom_histogram(bins = 80, fill = em_colors$normal,
                 colour = "white", alpha = 0.85) +
  geom_vline(xintercept = ta_stats$median, linetype = "dashed",
             colour = em_colors$em, linewidth = 0.7) +
  annotate("text", x = ta_stats$median + 0.02,
           y = Inf, vjust = 1.5,
           label = sprintf("中位数 = %.3f", ta_stats$median),
           family = "Heiti TC", size = 3.5,
           colour = em_colors$em) +
  scale_x_continuous(limits = c(-0.4, 0.4)) +
  labs(x = "总应计 / 滞后总资产 (TA)",
       y = "firm-year 频数",
       title = "Compustat 全样本 TA 分布",
       subtitle = "1991-2014，剔除金融与公用事业，1% / 99% winsorize") +
  theme_book()
ggsave(fig_path, plot = g, width = 7, height = 4.2,
       dpi = 300, device = ragg::agg_png)
cat(sprintf("\n图已写出：%s\n", fig_path))

# ---------- 图：案例公司 TA 时间序列 ----------
fig_path2 <- here::here("figure", "ch01_cases_ta.png")
g2 <- p |>
  filter(!is.na(company), fyear <= 2003) |>
  ggplot(aes(x = fyear, y = TA, colour = company)) +
  geom_line(linewidth = 0.8) +
  geom_point(aes(shape = factor(misstate)), size = 2.2) +
  scale_shape_manual(values = c(`0` = 16, `1` = 17),
                     labels = c(`0` = "未标记", `1` = "AAER"),
                     name = "标签") +
  scale_colour_manual(values = c(
    "Enron" = em_colors$em,
    "Sunbeam" = "#984EA3",
    "Computer Associates" = em_colors$normal
  )) +
  labs(x = "财年", y = "TA",
       title = "三家 AAER 案例公司的 TA 时间路径",
       colour = "公司") +
  theme_book()
ggsave(fig_path2, plot = g2, width = 7.5, height = 4.5,
       dpi = 300, device = ragg::agg_png)
cat(sprintf("图已写出：%s\n", fig_path2))

# ---------- 关键变量缺失率 ----------
cat("\n======== 1.5 关键变量缺失率 ========\n")
key_vars <- c("at", "sale", "ib", "cogs", "rect", "invt", "ppegt",
              "act", "lct", "che", "dlc", "dp")
miss_tbl <- p |>
  select(all_of(key_vars)) |>
  summarise(across(everything(), ~mean(is.na(.x)) * 100)) |>
  pivot_longer(everything(), names_to = "var", values_to = "miss_pct") |>
  arrange(desc(miss_pct))
print(miss_tbl, n = Inf)
