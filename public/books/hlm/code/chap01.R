# =========================================================
# Chapter 1: 问题与数据 —— Tennessee STAR 班额实验
# 数据：mlmRev::star（K 年级横截面，5,786 名学生）
# =========================================================

library(tidyverse)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

d <- read_csv(here::here("data", "star_k.csv"), show_col_types = FALSE)

# ---------- 描述：班级类型分布 ----------
cat("\n===== 班级类型分布（K 年级）=====\n")
tab_cltype <- d |>
  count(cltype) |>
  mutate(pct = round(n / sum(n) * 100, 1))
print(tab_cltype)

# ---------- 班级人数分布（每类的实际人数）----------
cat("\n===== 每个班级的实际学生人数（按类型）=====\n")
class_size <- d |>
  group_by(sch, tch, cltype) |>
  summarise(n_students = n(), .groups = "drop")
size_summary <- class_size |>
  group_by(cltype) |>
  summarise(
    n_classes = n(),
    mean_size = round(mean(n_students), 1),
    sd_size   = round(sd(n_students), 1),
    min_size  = min(n_students),
    max_size  = max(n_students)
  )
print(size_summary)

# ---------- 朴素均值对比：三种班级类型的数学/阅读分数 ----------
cat("\n===== 朴素均值（处理组 vs 对照组）=====\n")
naive <- d |>
  group_by(cltype) |>
  summarise(
    n_students = n(),
    math_mean  = round(mean(math, na.rm = TRUE), 2),
    math_sd    = round(sd(math, na.rm = TRUE),   2),
    read_mean  = round(mean(read, na.rm = TRUE), 2),
    read_sd    = round(sd(read, na.rm = TRUE),   2)
  )
print(naive)

# 朴素差值：small - reg
naive_diff_math <- naive$math_mean[naive$cltype == "small"] -
                   naive$math_mean[naive$cltype == "reg"]
naive_diff_read <- naive$read_mean[naive$cltype == "small"] -
                   naive$read_mean[naive$cltype == "reg"]
cat("\n朴素差值（小班 - 常班，math）:", round(naive_diff_math, 2), "\n")
cat("朴素差值（小班 - 常班，read）:", round(naive_diff_read, 2), "\n")

# 朴素 OLS 标准误（不考虑嵌套）
ols <- lm(math ~ cltype, data = d)
cat("\n===== 朴素 OLS（不考虑嵌套，标准误偏小）=====\n")
print(summary(ols)$coefficients)

# ---------- 学校层面：80 所学校的数学均值分布 ----------
cat("\n===== 学校均值分布 =====\n")
school_means <- d |>
  group_by(sch) |>
  summarise(
    n_students = n(),
    n_classes  = n_distinct(tch),
    math_mean  = mean(math, na.rm = TRUE),
    .groups = "drop"
  )
cat("学校间 math 均值：min =",     round(min(school_means$math_mean), 1),
    "，max =",                     round(max(school_means$math_mean), 1),
    "，跨度 ≈",                    round(diff(range(school_means$math_mean)), 1),
    "分\n")

# ---------- 班级层面：337 个班级的数学均值分布 ----------
class_means <- d |>
  group_by(sch, tch, cltype) |>
  summarise(
    n_students = n(),
    math_mean  = mean(math, na.rm = TRUE),
    .groups = "drop"
  )
cat("班级间 math 均值：min =",     round(min(class_means$math_mean), 1),
    "，max =",                     round(max(class_means$math_mean), 1),
    "，跨度 ≈",                    round(diff(range(class_means$math_mean)), 1),
    "分\n")

# ---------- 图 1.1：三类班级 math 分布 ----------
p1 <- ggplot(d, aes(x = cltype, y = math, fill = cltype)) +
  geom_violin(alpha = 0.6, color = NA) +
  geom_boxplot(width = 0.18, fill = "white",
               outlier.shape = NA, color = "gray30") +
  scale_fill_manual(values = c("small" = "#EF6548",
                               "reg"   = "#4292C6",
                               "reg+A" = "#41AB5D")) +
  labs(x = "班级类型", y = "数学考试分数",
       title = "三类班级 K 年级末数学分数分布",
       fill = NULL) +
  theme_book(base_size = 11) +
  theme(legend.position = "none")

ggsave(here::here("figure", "chap01_math_by_cltype.png"),
       p1, width = 6.5, height = 4.2, dpi = 300, device = ragg::agg_png)

# ---------- 图 1.2：80 所学校的均值分布（学校间差异）----------
p2 <- school_means |>
  arrange(math_mean) |>
  mutate(rank = row_number()) |>
  ggplot(aes(x = rank, y = math_mean)) +
  geom_hline(yintercept = mean(d$math, na.rm = TRUE),
             linetype = "dashed", color = "#EF6548", linewidth = 0.6) +
  geom_point(aes(size = n_students), color = "#4292C6", alpha = 0.85) +
  scale_size_continuous(range = c(1.2, 4.5), guide = "none") +
  labs(x = "学校（按均值排序）",
       y = "学校 math 均值",
       title = "80 所学校 K 年级数学均值的跨校差异",
       subtitle = "红色虚线为全样本总均值；学校之间相差最多约 100 分") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap01_school_means.png"),
       p2, width = 7.2, height = 4.2, dpi = 300, device = ragg::agg_png)

# ---------- 图 1.3：嵌套层级示意（用 ggplot 画三层框）----------
nest_df <- tibble(
  layer_zh = c("学校", "班级", "学生"),
  layer_en = c("school", "class/teacher", "student"),
  n        = c(79, 337, 5786),
  y        = c(3, 2, 1)
) |>
  mutate(label = paste0(layer_zh, " ",
                        ts(sprintf("(%s), n = %d", layer_en, n))))

p3 <- ggplot(nest_df, aes(x = 1, y = y)) +
  geom_tile(aes(fill = layer_zh), width = 0.9, height = 0.7, alpha = 0.85) +
  ggtext::geom_richtext(aes(label = label),
                        family = "Heiti TC", size = 4.2,
                        color = "white", fill = NA, label.color = NA) +
  scale_fill_manual(values = c("学校" = "#08519C",
                               "班级" = "#4292C6",
                               "学生" = "#9ECAE1")) +
  scale_y_continuous(breaks = NULL) +
  scale_x_continuous(breaks = NULL) +
  labs(x = NULL, y = NULL,
       title = paste0(ts("Tennessee STAR"), " 数据的三层嵌套结构")) +
  theme_book(base_size = 11) +
  theme(legend.position = "none",
        panel.grid = element_blank(),
        axis.text = element_blank())

ggsave(here::here("figure", "chap01_nesting.png"),
       p3, width = 6.0, height = 3.6, dpi = 300, device = ragg::agg_png)

cat("\n===== Chapter 1 figures generated =====\n")
