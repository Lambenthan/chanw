# =====================================================
# code/_theme.R
# 全书统一的 ggplot2 主题与配色
# 用法：source("code/_theme.R") 后 ggplot(...) + theme_book()
# =====================================================

library(ggplot2)

# 全书配色
fraud_colors <- list(
  fraud = "#EF6548",   # 舞弊
  normal = "#4292C6",  # 正常
  neutral = "#999999"  # 灰色对照
)

# 中英混排字体
theme_book <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = "Times New Roman") +
    theme(
      plot.title       = element_text(family = "Heiti TC", face = "bold"),
      plot.subtitle    = element_text(family = "Heiti TC"),
      axis.title       = element_text(family = "Heiti TC"),
      axis.text        = element_text(family = "Times New Roman"),
      legend.title     = element_text(family = "Heiti TC"),
      legend.text      = element_text(family = "Heiti TC"),
      strip.text       = element_text(family = "Heiti TC"),
      panel.grid.minor = element_blank()
    )
}
