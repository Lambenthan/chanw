"""图 9: 鲁棒性检验汇总

(a) 体裁控制: 原始 vs 语录体 only, 断点位置对比
(b) 记录者 FE 识别问题示意 (说明为什么不能跑标准 FE)
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
orig = json.loads((ROOT / "data" / "analysis" / "breakpoints.json").read_text(encoding="utf-8"))
ctrl = json.loads((ROOT / "data" / "analysis" / "control_genre_breakpoints.json").read_text(encoding="utf-8"))

KEY_CONCEPTS = [
    "致良知", "良知", "心即理", "知行合一",
    "格物", "天理", "人欲",
    "朱子", "立志", "事上", "工夫", "用功",
]

fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1.5, 1]})

# ============================================================================
# (a) 原始 vs 控制 断点位置对比
# ============================================================================
ax = axes[0]

# 原始: 全 343 条
orig_results = orig["results"]
ctrl_results = ctrl["results"]

y = np.arange(len(KEY_CONCEPTS))
orig_years = []
ctrl_years = []
orig_r2 = []
ctrl_r2 = []
for c in KEY_CONCEPTS:
    r1 = orig_results.get(c, {})
    r2 = ctrl_results.get(c, {})
    orig_years.append(r1.get("binseg_break_year"))
    ctrl_years.append(r2.get("break_year"))
    orig_r2.append(r1.get("binseg_r2", 0))
    ctrl_r2.append(r2.get("r2", 0))

# 画两个散点
for i in range(len(KEY_CONCEPTS)):
    if orig_years[i] is None or ctrl_years[i] is None:
        continue
    color_o = "#c0392b" if 1520 <= orig_years[i] <= 1522 else "#888888"
    color_c = "#27ae60" if 1520 <= ctrl_years[i] <= 1522 else "#888888"
    ax.scatter(orig_years[i], i - 0.18, s=orig_r2[i] * 600 + 30,
               color=color_o, alpha=0.65, edgecolor="black", lw=0.5,
               label="原始 (全 343 条)" if i == 0 else None)
    ax.scatter(ctrl_years[i], i + 0.18, s=ctrl_r2[i] * 600 + 30,
               color=color_c, marker="s", alpha=0.65, edgecolor="black", lw=0.5,
               label="控制 (语录体 273 条)" if i == 0 else None)
    # 连线
    ax.plot([orig_years[i], ctrl_years[i]], [i - 0.18, i + 0.18],
            color="#aaa", lw=0.6, alpha=0.6, zorder=1)

# 1520-1522 阴影
ax.axvspan(1520, 1522, color="#f4d03f", alpha=0.18, zorder=0)

ax.set_yticks(y)
ax.set_yticklabels(KEY_CONCEPTS, fontsize=10.5)
ax.invert_yaxis()
ax.set_xlim(1515, 1530)
ax.set_xticks(range(1515, 1530, 2))
ax.set_xlabel("断点年份")
ax.set_title("(a)  体裁控制前后断点位置对比  (圆点 = 原始, 方块 = 控制, 大小 ∝ R²)",
             loc="left", fontsize=11)
ax.legend(loc="lower right", fontsize=9)
ax.grid(axis="x", alpha=0.25, lw=0.4)

# ============================================================================
# (b) 记录者 - 时段共线性示意
# ============================================================================
ax = axes[1]

# 每个时段的记录者构成
PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]
RECORDERS_BY_PERIOD = {
    "T1": [("徐爱", 1.0)],
    "T2": [("陆澄", 1.0)],
    "T3": [("薛侃", 1.0)],
    "T4": [("顾东桥", 0.19), ("聂文蔚", 0.24), ("陆原静", 0.24),
           ("欧阳崇一", 0.06), ("罗整庵", 0.09), ("周道通", 0.10),
           ("(其他)", 0.09)],
    "T5": [("黄省曾", 1.0)],   # 简化
    "T6": [("黄省曾", 0.6), ("黄以方", 0.4)],
}

RECORDER_COLORS = {
    "徐爱": "#3a7a4e", "陆澄": "#5fa39a", "薛侃": "#5b8db8",
    "顾东桥": "#c0392b", "聂文蔚": "#c08a3e", "陆原静": "#8b3d6f",
    "欧阳崇一": "#7c3a3a", "罗整庵": "#a87a7a", "周道通": "#888888",
    "(其他)": "#cccccc", "黄省曾": "#5b2e7a", "黄以方": "#b86b4a",
}

for i, p in enumerate(PERIODS):
    left = 0
    for rec, prop in RECORDERS_BY_PERIOD[p]:
        c = RECORDER_COLORS.get(rec, "#cccccc")
        ax.barh(i, prop, left=left, height=0.6, color=c, edgecolor="white", lw=0.6)
        if prop > 0.10:
            ax.text(left + prop/2, i, rec, ha="center", va="center",
                    fontsize=8.5, color="white", fontweight="bold")
        left += prop

ax.set_yticks(range(len(PERIODS)))
ax.set_yticklabels(PERIODS, fontsize=11)
ax.invert_yaxis()
ax.set_xlim(0, 1)
ax.set_xlabel("记录者构成比例")
ax.set_title("(b)  时段 × 记录者完美共线  →  无法分离两种效应",
             loc="left", fontsize=11)

# 在图下方加说明 (用 axes coords, 不溢出)
ax.text(0.02, -0.15, "T1-T3 + T5 都是单一记录者主导, 与时段一一对应,\n"
                     "在数据结构上记录者与时段无法区分.",
        fontsize=8.5, color="#666", style="italic",
        transform=ax.transAxes, va="top")

plt.suptitle("图 9  鲁棒性检验: 体裁控制 + 记录者识别问题诚实交代",
             fontsize=13, x=0.04, y=0.98, ha="left", fontweight="bold")
plt.subplots_adjust(top=0.91, bottom=0.14, left=0.06, right=0.97, wspace=0.30)

out = ROOT / "figure" / "fig09_controls.png"
plt.savefig(out)
print(f"saved: {out}")
