"""项目统一 matplotlib 主题. 严格遵守 CLAUDE.md 图字体规则."""
import matplotlib.pyplot as plt


def apply_theme():
    plt.rcParams.update({
        "font.family":        ["Times New Roman", "Heiti TC"],
        "font.size":          11,
        "axes.unicode_minus": False,
        "axes.titlesize":     12,
        "axes.labelsize":     11,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.linewidth":     0.6,
        "axes.edgecolor":     "#444444",
        "axes.titleweight":   "normal",
        "xtick.labelsize":    10,
        "ytick.labelsize":    10,
        "xtick.color":        "#444444",
        "ytick.color":        "#444444",
        "figure.dpi":         100,
        "savefig.dpi":        300,
        "savefig.bbox":       "tight",
        "legend.fontsize":    10,
        "legend.frameon":     False,
    })


# 六个时段固定配色 (柔和饱和度, 时段顺序色相由冷到暖)
PERIOD_COLORS = {
    "T1": "#5a78a8",   # 蓝灰
    "T2": "#5fa39a",   # 青绿
    "T3": "#8aa755",   # 草绿
    "T4": "#c08a3e",   # 暗金
    "T5": "#b86b4a",   # 砖红
    "T6": "#8b3d6f",   # 暗紫
}
