# =====================================================
# code/_theme.R
# 全书统一的 ggplot2 主题与配色
#
# 字体策略：
#   - 基础字体 Times New Roman（英文 / 数字）
#   - 中文字符依赖 ragg 字符级 fallback 到 Heiti TC
#   - 显式 register_font，把 plain / bold / italic / bold_italic
#     四个字重的字体文件都指明，避免 match_fonts 找不到 bold 时
#     fallback 到空字体 unfont.ttf 导致 "No fonts detected" 警告
# =====================================================

suppressPackageStartupMessages({
  library(ggplot2)
  library(systemfonts)
})

# Times New Roman 各字重
.times_dir <- "/System/Library/Fonts/Supplemental"
.times_plain  <- file.path(.times_dir, "Times New Roman.ttf")
.times_bold   <- file.path(.times_dir, "Times New Roman Bold.ttf")
.times_italic <- file.path(.times_dir, "Times New Roman Italic.ttf")
.times_bi     <- file.path(.times_dir, "Times New Roman Bold Italic.ttf")

# Heiti TC 字重（macOS 只有 Light 与 Medium，把 Medium 当 bold）
.heiti_light  <- "/System/Library/Fonts/STHeiti Light.ttc"
.heiti_medium <- "/System/Library/Fonts/STHeiti Medium.ttc"

if (file.exists(.times_plain) && file.exists(.times_bold)) {
  register_font(
    name = "TimesBook",
    plain       = .times_plain,
    bold        = .times_bold,
    italic      = .times_italic,
    bolditalic  = .times_bi
  )
}

# 中文 fallback 字体：plain 用 Light，bold 用 Medium
if (file.exists(.heiti_light) && file.exists(.heiti_medium)) {
  register_font(
    name = "HeitiBook",
    plain  = .heiti_light,
    bold   = .heiti_medium,
    italic = .heiti_light,
    bolditalic = .heiti_medium
  )
}

# 关键：把 HeitiBook 注册为 TimesBook 的中文 fallback
# ragg::agg_png 在渲染时遇到 Times 不含的字符（中文）会按 fallback 链查找
if ("register_font" %in% ls(getNamespace("systemfonts"))) {
  try(systemfonts::register_font(
    name = "TimesBook",
    plain       = .times_plain,
    bold        = .times_bold,
    italic      = .times_italic,
    bolditalic  = .times_bi,
    features    = font_feature(),
    fallback    = "HeitiBook"
  ), silent = TRUE)
}

em_colors <- list(
  em      = "#EF6548",  # 操纵嫌疑
  normal  = "#4292C6",  # 正常
  neutral = "#999999"   # 行业基准
)

theme_book <- function(base_size = 11) {
  theme_minimal(base_size = base_size,
                base_family = "TimesBook") +
    theme(
      plot.title       = element_text(face = "bold"),
      plot.subtitle    = element_text(),
      axis.title       = element_text(),
      axis.text        = element_text(),
      legend.title     = element_text(),
      legend.text      = element_text(),
      strip.text       = element_text(),
      panel.grid.minor = element_blank()
    )
}
