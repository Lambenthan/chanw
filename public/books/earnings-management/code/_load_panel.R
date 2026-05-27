# =====================================================
# code/_load_panel.R
# 共享加载函数：所有章节脚本都通过这个函数读 em_panel.csv
# 避免重复指定 col_types
# =====================================================

suppressPackageStartupMessages({
  library(readr)
  library(here)
})

load_em_panel <- function(path = here::here("data", "em_panel.csv")) {
  read_csv(
    path,
    col_types = cols(
      .default = col_double(),
      gvkey = col_double(),
      fyear = col_double(),
      company = col_character()
    ),
    show_col_types = FALSE
  )
}
