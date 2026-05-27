# =====================================================
# code/00_load_data.R
# 加载本书使用的盈余管理面板数据并派生必要字段
#
# 数据来源：Bao, Ke, Li, Yu, Zhang (2020) JAR 公开数据
#   https://github.com/JarFraud/FraudDetection
# 该数据由作者从 WRDS Compustat North America 抽取，含 1991-2014 年
# 美国上市公司 firm-year 财务字段与 AAER 舞弊标签，剔除金融业。
#
# 因 Bao 数据不含 sich 与 oancf，本脚本：
#   - 用 Hribar-Collins 资产负债表法构造总应计 TA_BS
#   - 用 CFO = NI - TA_BS 倒推经营现金流
#   - 行业控制改为按 fyear pooled（书中第 3 章正文说明该简化）
# =====================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(here)
})

set.seed(2026)

src_path <- "/Users/han/Desktop/AI_Plan/2026LLM/Media_Paper/FraudDetectionBook/data/bao2020_full.csv"
out_dir  <- here::here("data")
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)

raw <- read_csv(src_path, show_col_types = FALSE)

# 标识案例公司（gvkey 来自 Compustat 官方编号；AAER 来自 SEC 公告）
# 三家公司均为 SEC AAER 处罚的会计舞弊案，覆盖小、中、大三种规模
case_companies <- tibble(
  gvkey   = c(1278, 25495, 6127),
  company = c("Sunbeam", "Computer Associates", "Enron"),
  aaer_id = c(1393, 1631, 1821),
  fraud_window_start = c(1996, 1998, 1998),
  fraud_window_end   = c(1997, 2000, 2001)
)

# 派生 lag_at，过滤极端值并构造 Hribar-Collins 资产负债表 TA
panel <- raw |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(
    lag_at  = lag(at),
    lag_act = lag(act),
    lag_che = lag(che),
    lag_lct = lag(lct),
    lag_dlc = lag(dlc),
    lag_txp = lag(txp),
    lag_rect = lag(rect),
    lag_sale = lag(sale)
  ) |>
  ungroup() |>
  mutate(
    dCA   = act - lag_act,
    dCash = che - lag_che,
    dCL   = lct - lag_lct,
    dSTD  = dlc - lag_dlc,
    dTP   = txp - lag_txp,
    # Healy 1985 / Jones 1991 原文式资产负债表 TA
    TA_BS = (dCA - dCash) - (dCL - dSTD - dTP) - dp,
    # 用 TA_BS 倒推经营现金流（Hribar-Collins 思路）
    CFO_synth = ib - TA_BS,
    dSale = sale - lag_sale,
    dRect = rect - lag_rect,
    ROA   = ib / lag_at
  ) |>
  filter(
    !is.na(lag_at), lag_at > 0,
    !is.na(TA_BS),
    !is.na(sale), sale > 0,
    !is.na(at),   at   > 0
  ) |>
  mutate(
    TA       = TA_BS / lag_at,        # 缩放后的总应计
    inv_lag_at = 1 / lag_at,
    dSale_s  = dSale / lag_at,
    dRect_s  = dRect / lag_at,
    PPE_s    = ppegt / lag_at,
    Sale_s   = sale  / lag_at,
    COGS_s   = cogs  / lag_at,
    Inv_s    = invt  / lag_at,
    CFO_s    = CFO_synth / lag_at,
    WC_accr  = (TA_BS + dp) / lag_at
  ) |>
  arrange(gvkey, fyear) |>
  group_by(gvkey) |>
  mutate(
    dInv   = invt - lag(invt),
    PROD_s = (cogs + dInv) / lag_at
  ) |>
  ungroup() |>
  left_join(case_companies, by = "gvkey")

# 1% / 99% winsorize 关键比率，控制极端 firm-year 影响
winsor <- function(x, p = 0.01) {
  q <- quantile(x, probs = c(p, 1 - p), na.rm = TRUE)
  pmin(pmax(x, q[1]), q[2])
}

panel <- panel |>
  mutate(
    TA      = winsor(TA),
    ROA     = winsor(ROA),
    dSale_s = winsor(dSale_s),
    dRect_s = winsor(dRect_s),
    PPE_s   = winsor(PPE_s),
    CFO_s   = winsor(CFO_s),
    Sale_s  = winsor(Sale_s),
    WC_accr = winsor(WC_accr),
    PROD_s  = winsor(PROD_s)
  )

out_path <- file.path(out_dir, "em_panel.csv")
write_csv(panel, out_path)

cat(sprintf("已写出 %s\n  行数 %d  公司数 %d  年份 %d-%d\n",
            out_path,
            nrow(panel),
            n_distinct(panel$gvkey),
            min(panel$fyear), max(panel$fyear)))
