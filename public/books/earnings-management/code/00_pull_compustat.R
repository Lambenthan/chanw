# =====================================================
# code/00_pull_compustat.R
# 从 WRDS 拉取 Compustat North America Annual Fundamentals
# 时间跨度 1991--2023, 剔除金融（SIC 6000-6999）与公用事业（SIC 4900-4999）
# 输出：data/compustat_em.csv
#
# 使用前提：~/.pgpass 配好 wrds-pgdata.wharton.upenn.edu:9737:wrds 的密码
# 或在脚本里 prompt 输入
# =====================================================

suppressPackageStartupMessages({
  library(RPostgres)
  library(DBI)
  library(tidyverse)
  library(here)
})

dest_dir <- here::here("data")
if (!dir.exists(dest_dir)) dir.create(dest_dir, recursive = TRUE)
dest_path <- file.path(dest_dir, "compustat_em.csv")

# 连接 WRDS（需要订阅）
wrds <- tryCatch(
  dbConnect(
    Postgres(),
    host = "wrds-pgdata.wharton.upenn.edu",
    port = 9737,
    dbname = "wrds",
    sslmode = "require",
    user = Sys.getenv("WRDS_USER")
  ),
  error = function(e) {
    stop("无法连接 WRDS。请先 export WRDS_USER=<你的用户名> 并配置 ~/.pgpass。",
         "如果你没有 WRDS 订阅，改用 code/00_alt_sample.R。\n",
         "原始错误：", conditionMessage(e))
  }
)

# 主查询：annual fundamentals
sql <- "
  SELECT
    gvkey, fyear, datadate, sich, fyr,
    at, act, lct, che, dlc, dltt, rect, invt, ppegt,
    sale, cogs, xsga, xrd, xad, ib, ni, dp,
    oancf, ivncf, fincf,
    csho, prcc_f
  FROM comp.funda
  WHERE indfmt = 'INDL'
    AND datafmt = 'STD'
    AND popsrc = 'D'
    AND consol = 'C'
    AND fyear BETWEEN 1991 AND 2023
    AND at IS NOT NULL AND at > 0
    AND sale IS NOT NULL AND sale > 0;
"

message("从 WRDS 拉取 Compustat funda（约 30-90 秒）...")
d <- dbGetQuery(wrds, sql) |> as_tibble()
dbDisconnect(wrds)
message("拿到 ", nrow(d), " 行原始数据")

# 剔除金融与公用事业
d <- d |>
  filter(!is.na(sich)) |>
  filter(!(sich >= 6000 & sich <= 6999)) |>   # 金融
  filter(!(sich >= 4900 & sich <= 4999))      # 公用事业

message("剔除金融与公用事业后剩 ", nrow(d), " 行")

# 派生 lag_at（按 gvkey 取上一年总资产）
d <- d |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(lag_at = lag(at)) |>
  ungroup()

write_csv(d, dest_path)
message("数据已保存到：", dest_path,
        "（", nrow(d), " 行，", ncol(d), " 列，",
        n_distinct(d$gvkey), " 家公司）")
