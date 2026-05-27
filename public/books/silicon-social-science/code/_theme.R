# _theme.R —— 全书统一 ggplot2 主题（中文 Heiti TC + 英数 Times New Roman）
suppressPackageStartupMessages({
  library(ggplot2); library(showtext); library(ragg)
})
font_add("Times New Roman", regular = "Times New Roman.ttf")
font_add("Heiti TC", regular = "/System/Library/Fonts/STHeiti Medium.ttc")
showtext_auto()

# 颜色
COLOR_REAL    <- "#7A3A2E"   # 真实受访者 暗赭
COLOR_SILICON <- "#384C6C"   # 硅基受访者 暗蓝灰
COLOR_ACCENT  <- "#3A6C4E"   # 第三色 墨绿
COLOR_GRAY    <- "#888888"

theme_book <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = "Times New Roman") +
    theme(
      plot.title       = element_text(family = "Heiti TC", size = base_size + 2, hjust = 0),
      plot.subtitle    = element_text(family = "Heiti TC", size = base_size, color = "gray30", hjust = 0),
      axis.title       = element_text(family = "Heiti TC", size = base_size, color = "gray20"),
      axis.text        = element_text(family = "Times New Roman", size = base_size - 1, color = "gray20"),
      legend.title     = element_text(family = "Heiti TC", size = base_size - 1),
      legend.text      = element_text(family = "Heiti TC", size = base_size - 1),
      strip.text       = element_text(family = "Heiti TC", size = base_size, color = "gray20"),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = "gray90", linewidth = 0.25),
      panel.background = element_rect(fill = "white", color = NA),
      plot.background  = element_rect(fill = "white", color = NA),
      legend.position  = "bottom"
    )
}
