# =====================================================
# code/00_download_bao_data.R
# 下载 Bao et al. (2020 JAR) 公开复制包到 data/
#
# 数据源：JarFraud/FraudDetection 官方 GitHub
# 输出：data/bao2020_full.csv
# =====================================================

library(here)

dest_dir <- here::here("data")
if (!dir.exists(dest_dir)) dir.create(dest_dir, recursive = TRUE)

dest_path <- file.path(dest_dir, "bao2020_full.csv")

bao_repo <- "https://raw.githubusercontent.com/JarFraud/FraudDetection"
bao_file <- "data_FraudDetection_JAR2020.csv"
candidate_urls <- c(paste(bao_repo, "master", bao_file, sep = "/"))

success <- FALSE
for (url in candidate_urls) {
  message("尝试下载：", url)
  status <- try(download.file(url, dest_path, mode = "wb"), silent = TRUE)
  if (!inherits(status, "try-error") && file.exists(dest_path)) {
    success <- TRUE
    break
  }
}

if (!success) {
  stop("下载失败，请手动放入 data/bao2020_full.csv")
}

message("数据已保存到：", dest_path)
