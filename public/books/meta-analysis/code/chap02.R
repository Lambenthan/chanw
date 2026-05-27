# =========================================================
# Chapter 2: PRISMA 与系统综述流程
# 用 PRISMA2020 包生成 PRISMA 2020 流程图模板
# 中间阶段用 "?" 占位，最终纳入用 dat.bcg 真实数 13
# =========================================================

library(PRISMA2020)
library(here)

# ---------- 读取 PRISMA2020 自带的模板 ----------
csv_path  <- system.file("extdata", "PRISMA.csv", package = "PRISMA2020")
prisma_df <- read.csv(csv_path, stringsAsFactors = FALSE)

# ---------- 把数字填进模板 ----------
fill_n <- function(df, key, val) {
  df$n[!is.na(df$data) & df$data == key] <- val
  df
}

# 识别阶段：保留 "?" 占位
prisma_df <- fill_n(prisma_df, "database_results",          "n = ?")
prisma_df <- fill_n(prisma_df, "database_specific_results",
                    "Database 1, ?; Database 2, ?")
prisma_df <- fill_n(prisma_df, "register_results",          "0")
prisma_df <- fill_n(prisma_df, "register_specific_results", "")

prisma_df <- fill_n(prisma_df, "website_results",      "0")
prisma_df <- fill_n(prisma_df, "organisation_results", "0")
prisma_df <- fill_n(prisma_df, "citations_results",    "0")

prisma_df <- fill_n(prisma_df, "duplicates",         "n = ?")
prisma_df <- fill_n(prisma_df, "excluded_automatic", "0")
prisma_df <- fill_n(prisma_df, "excluded_other",     "0")

# 筛选阶段
prisma_df <- fill_n(prisma_df, "records_screened", "n = ?")
prisma_df <- fill_n(prisma_df, "records_excluded", "n = ?")

# 全文检索阶段
prisma_df <- fill_n(prisma_df, "dbr_sought_reports",       "n = ?")
prisma_df <- fill_n(prisma_df, "dbr_notretrieved_reports", "0")
prisma_df <- fill_n(prisma_df, "other_sought_reports",       "0")
prisma_df <- fill_n(prisma_df, "other_notretrieved_reports", "0")

# 合格性评估阶段
prisma_df <- fill_n(prisma_df, "dbr_assessed", "n = ?")
prisma_df <- fill_n(prisma_df, "dbr_excluded", "Reason 1, ?; Reason 2, ?")
prisma_df <- fill_n(prisma_df, "other_assessed", "0")
prisma_df <- fill_n(prisma_df, "other_excluded", "")

# 没有以前版本的综述
prisma_df <- fill_n(prisma_df, "previous_studies", "0")
prisma_df <- fill_n(prisma_df, "previous_reports", "0")

# 最终纳入：dat.bcg 真实数据
prisma_df <- fill_n(prisma_df, "new_studies",   "13")
prisma_df <- fill_n(prisma_df, "new_reports",   "13")
prisma_df <- fill_n(prisma_df, "total_studies", "13")
prisma_df <- fill_n(prisma_df, "total_reports", "13")

# ---------- 构造 PRISMA 对象并绘图 ----------
prisma_obj <- PRISMA_data(prisma_df)

plot <- PRISMA_flowdiagram(
  prisma_obj,
  interactive       = FALSE,
  previous          = FALSE,
  other             = FALSE,
  detail_databases  = TRUE,
  detail_registers  = FALSE,
  fontsize          = 10,
  font              = "Times",
  side_boxes        = TRUE
)

# ---------- 保存为 PDF ----------
PRISMA_save(
  plot,
  filename  = here::here("figure", "chap02_prisma_flow.pdf"),
  filetype  = "PDF",
  overwrite = TRUE
)

cat("===== Chapter 2 PRISMA 流程图模板生成完毕 =====\n")
