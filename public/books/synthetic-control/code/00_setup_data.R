# 00_setup_data.R —— 从 tidysynth 包导出 California Prop 99 完整数据
# 数据来源：Abadie, Diamond & Hainmueller (2010) JASA 公开复制包
# tidysynth 包内置 smoking 数据集（同源，含完整协变量）

suppressPackageStartupMessages({
  library(tidysynth)
  library(dplyr)
  library(here)
})

data("smoking", package = "tidysynth")
smoking <- as.data.frame(smoking)

cat("=== 数据维度 ===\n")
cat("行数：", nrow(smoking), "\n")
cat("唯一 state 数：", length(unique(smoking$state)), "\n")
cat("年份范围：", min(smoking$year), "—", max(smoking$year), "\n")
cat("处理州：California（treatment_year = 1989）\n\n")

cat("=== 字段 ===\n")
str(smoking)

cat("\n=== California 时间序列 (1985-2000 节选) ===\n")
ca <- smoking |> filter(state == "California") |> arrange(year)
print(ca |> filter(year >= 1985, year <= 2000) |> select(year, cigsale, lnincome, beer, age15to24, retprice))

cat("\n=== 1988 (treatment 前一年) 全样本统计 ===\n")
all_1988 <- smoking |> filter(year == 1988)
cat("California cigsale:", all_1988 |> filter(state == "California") |> pull(cigsale), "\n")
non_ca <- all_1988 |> filter(state != "California")
cat("其余 38 州 cigsale: mean=", round(mean(non_ca$cigsale), 2),
    " sd=", round(sd(non_ca$cigsale), 2),
    " min=", round(min(non_ca$cigsale), 2),
    " max=", round(max(non_ca$cigsale), 2), "\n")

# 保存
out_csv <- here::here("data", "smoking.csv")
write.csv(smoking, out_csv, row.names = FALSE)
cat("\n写入：", out_csv, "\n")

# Pre/post 加州平均
ca_pre  <- mean(ca |> filter(year <= 1988) |> pull(cigsale))
ca_post <- mean(ca |> filter(year >= 1989) |> pull(cigsale))
cat("\n=== 加州 pre/post 朴素均值差 ===\n")
cat("pre  (1970-1988) mean cigsale =", round(ca_pre, 2), "\n")
cat("post (1989-2000) mean cigsale =", round(ca_post, 2), "\n")
cat("naive within-CA diff          =", round(ca_post - ca_pre, 2), "\n")

# 朴素 DiD
non_ca_pre  <- smoking |> filter(state != "California", year <= 1988) |> summarise(m=mean(cigsale)) |> pull(m)
non_ca_post <- smoking |> filter(state != "California", year >= 1989) |> summarise(m=mean(cigsale)) |> pull(m)
cat("\n=== 朴素 DiD (二阶段差分) ===\n")
cat("CA pre-post diff       =", round(ca_post - ca_pre, 2), "\n")
cat("non-CA pre-post diff   =", round(non_ca_post - non_ca_pre, 2), "\n")
cat("DiD (ATT under DiD)    =", round((ca_post - ca_pre) - (non_ca_post - non_ca_pre), 2), "\n")
