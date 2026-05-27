"""图 7: 阳明 5 个人格维度随 6 时段演化, 标注 4 个事件年份"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
scores = json.loads((ROOT / "data" / "analysis" / "personality_scores.json").read_text(encoding="utf-8"))
period_meta = json.loads((ROOT / "data" / "analysis" / "period_meta.json").read_text(encoding="utf-8"))

PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]
DIMENSIONS = ["教学耐心", "反权威", "自我修正", "同理心", "实践导向"]

# 颜色 (5 维度)
DIM_COLORS = {
    "教学耐心":  "#3a7a4e",
    "反权威":    "#c0392b",
    "自我修正":  "#5b8db8",
    "同理心":    "#c08a3e",
    "实践导向":  "#8b3d6f",
}

# 5 个子图  (放大 figsize, 留出标题 + 注释空间)
fig, axes = plt.subplots(2, 3, figsize=(18, 11))
axes = axes.flatten()
plt.subplots_adjust(hspace=0.40, wspace=0.30, top=0.92, bottom=0.06, left=0.05, right=0.97)

# 事件
EVENTS = [
    ("1517 徐爱卒", 1517, "#7c3a3a"),
    ("1519 宁王",   1519, "#c8651b"),
    ("1521 致良知", 1521, "#7b3f8e"),
    ("1522 父卒",   1522, "#444444"),
]

# 时段中点年份, 给 x 轴定位
period_x = [(period_meta[p]["year_min"] + period_meta[p]["year_max"]) / 2 for p in PERIODS]

for i, dim in enumerate(DIMENSIONS):
    ax = axes[i]
    means = [scores["period_summary"][p][dim]["mean"] for p in PERIODS]
    ses   = [scores["period_summary"][p][dim]["se"]   for p in PERIODS]
    ns    = [scores["period_summary"][p][dim]["n"]    for p in PERIODS]

    color = DIM_COLORS[dim]
    # 阴影带
    ax.fill_between(period_x,
                    [m - s for m, s in zip(means, ses)],
                    [m + s for m, s in zip(means, ses)],
                    color=color, alpha=0.15)
    # 主线
    ax.plot(period_x, means, marker="o", lw=2.0, markersize=8,
            color=color, zorder=5)

    # 数值标注
    for x, m, n in zip(period_x, means, ns):
        ax.annotate(f"{m:.2f}", (x, m), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8.5, color="#333333")

    # 标注时段 ID
    for x, p in zip(period_x, PERIODS):
        ax.text(x, ax.get_ylim()[0], p, ha="center", va="top",
                fontsize=8, color="#888888")

    # 事件线
    for label, year, ec in EVENTS:
        ax.axvline(year, color=ec, alpha=0.35, lw=1.2, ls="--", zorder=1)

    ax.set_title(dim, fontsize=12, color=color, fontweight="bold", loc="left")
    ax.set_xlim(1510, 1530)
    ax.set_xticks(range(1512, 1530, 3))
    ax.tick_params(axis="x", labelsize=9)
    ax.grid(axis="y", alpha=0.2, lw=0.4)

# 第 6 子图: 事件 → 维度效应 heatmap
ax = axes[5]
event_effects = scores["event_effects"]
event_names = list(event_effects.keys())
n_events = len(event_names)
n_dims = len(DIMENSIONS)

mat = np.zeros((n_events, n_dims))
sig_mat = [[""] * n_dims for _ in range(n_events)]
for i, ev in enumerate(event_names):
    for j, dim in enumerate(DIMENSIONS):
        d = event_effects[ev][dim]
        if d is None:
            continue
        mat[i, j] = d["diff"]
        t = d["t"]
        if abs(t) > 2.58:
            sig_mat[i][j] = "★★★"
        elif abs(t) > 1.96:
            sig_mat[i][j] = "★★"
        elif abs(t) > 1.64:
            sig_mat[i][j] = "★"

vmax = max(abs(mat.min()), abs(mat.max()))
im = ax.imshow(mat, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
for i in range(n_events):
    for j in range(n_dims):
        v = mat[i, j]
        text_color = "white" if abs(v) > vmax * 0.5 else "#222"
        ax.text(j, i, f"{v:+.2f}\n{sig_mat[i][j]}",
                ha="center", va="center", fontsize=9, color=text_color)

ax.set_xticks(range(n_dims))
ax.set_xticklabels(DIMENSIONS, fontsize=9, rotation=20, ha="right")
ax.set_yticks(range(n_events))
ax.set_yticklabels(event_names, fontsize=9)
ax.set_title("事件 → 维度 平均净分变化  (★ p<.10, ★★ p<.05, ★★★ p<.01)",
             fontsize=11, loc="left", pad=8)

plt.colorbar(im, ax=ax, shrink=0.85, label="post − pre 均值差")

plt.suptitle("图 7  阳明 5 个人格维度随时段演化 + 4 个事件的 pre/post 效应",
             fontsize=14, x=0.03, y=0.98, ha="left", fontweight="bold")

out = ROOT / "figure" / "fig07_personality_evolution.png"
plt.savefig(out)
print(f"saved: {out}")
