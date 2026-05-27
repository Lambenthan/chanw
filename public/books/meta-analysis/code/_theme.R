# =========================================================
# 共用主题：英文/数字 = Times New Roman；中文 = 黑体（Heiti TC）
# 通过 ragg::agg_png 设备直接走 systemfonts 找系统字体
# =========================================================

theme_book <- function(base_size = 11) {
  ggplot2::theme_minimal(base_size = base_size,
                         base_family = "Times New Roman") +
    ggplot2::theme(
      panel.grid.minor = ggplot2::element_blank(),
      plot.title       = ggplot2::element_text(family = "Heiti TC", size = base_size + 1),
      plot.subtitle    = ggplot2::element_text(family = "Heiti TC"),
      plot.caption     = ggplot2::element_text(family = "Heiti TC"),
      axis.title.x     = ggplot2::element_text(family = "Heiti TC"),
      axis.title.y     = ggplot2::element_text(family = "Heiti TC"),
      legend.title     = ggplot2::element_text(family = "Heiti TC"),
      legend.text      = ggplot2::element_text(family = "Heiti TC"),
      strip.text       = ggplot2::element_text(family = "Heiti TC")
    )
}
