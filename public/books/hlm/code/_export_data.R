# =========================================================
# 从 mlmRev::star 导出 CSV 数据，用于本书全程分析
# =========================================================

library(mlmRev)
library(tidyverse)
library(here)

data(star)

# 转 factor 为 character / numeric 以便保存 CSV
df <- star |>
  as_tibble() |>
  mutate(
    id      = as.character(id),
    sch     = as.integer(as.character(sch)),
    gr      = as.character(gr),       # K, 1, 2, 3
    cltype  = as.character(cltype),   # small, reg, reg+A
    hdeg    = as.character(hdeg),
    clad    = as.character(clad),
    trace   = as.character(trace),
    ses     = as.character(ses),
    schtype = as.character(schtype),
    sx      = as.character(sx),
    eth     = as.character(eth),
    birthq  = as.character(birthq),
    birthy  = as.character(birthy),
    tch     = as.character(tch)
  )

cat("总行数:", nrow(df), "\n")
cat("学生数:", length(unique(df$id)), "\n")
cat("班级数:", length(unique(df$tch)), "\n")
cat("学校数:", length(unique(df$sch)), "\n")

write_csv(df, here::here("data", "star.csv"))
cat("写入: data/star.csv\n")

# ---------- 衍生子集：仅幼儿园 K 年级 ----------
# 全书主要用 K 年级横截面（最干净的 3 层结构）
df_k <- df |>
  filter(gr == "K") |>
  filter(!is.na(math), !is.na(read), !is.na(cltype),
         !is.na(sch), !is.na(tch))

cat("\nK 年级（干净样本）:\n")
cat("  行数:", nrow(df_k), "\n")
cat("  学生数:", length(unique(df_k$id)), "\n")
cat("  班级数:", length(unique(df_k$tch)), "\n")
cat("  学校数:", length(unique(df_k$sch)), "\n")

write_csv(df_k, here::here("data", "star_k.csv"))
cat("写入: data/star_k.csv\n")
