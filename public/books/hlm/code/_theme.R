# =========================================================
# 共用主题：英文/数字 = Times New Roman；中文 = 系统黑体（fallback）
#
# 关键机制：
# - base_family = "Times New Roman" 让 ragg 按字符自动 fallback
# - 英文 / 数字字符在 Times 字体里 → 渲染为 Times 衬线
# - 中文字符 Times 没有 → ragg fallback 到系统中文字体（macOS 默认走
#   PingFang / Heiti TC 这一档现代黑体），视觉上是端正黑体
# - 不需要 ts() 包裹、不需要 element_markdown 切字体
# - 经测试：element_markdown 在 axis.text 上不解析 markdown，
#   ggtext 也不能在单个 grob 内做字体切换；ragg 内置 fallback 才是正解
# =========================================================

theme_book <- function(base_size = 11) {
  ggplot2::theme_minimal(base_size = base_size,
                         base_family = "Times New Roman") +
    ggplot2::theme(
      panel.grid.minor = ggplot2::element_blank(),
      plot.title       = ggplot2::element_text(size = base_size + 1),
      plot.subtitle    = ggplot2::element_text(),
      plot.caption     = ggplot2::element_text(),
      axis.title.x     = ggplot2::element_text(),
      axis.title.y     = ggplot2::element_text(),
      legend.title     = ggplot2::element_text(),
      legend.text      = ggplot2::element_text(),
      strip.text       = ggplot2::element_text()
    )
}

# 兼容旧脚本：保留 ts() 占位，返回原字符串（不再包 HTML span）
ts <- function(x) x
