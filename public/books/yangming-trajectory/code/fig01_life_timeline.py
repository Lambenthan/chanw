"""图 1: 阳明生平时间轴 (修复版 v3)

修复点:
  1. figsize 从 (15, 7.5) 扩到 (18, 9), 给事件密集区更多横向空间
  2. 事件标签上下交错位置改为 3 档 (近、中、远), 避免 1505-1520 拥挤
  3. 顶部时段轨道单独居上, 不和事件区抢空间
  4. 引导线 (leader line) 帮助识别标签对应的事件点
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from _theme import apply_theme, PERIOD_COLORS

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
bio = json.loads((ROOT / "data" / "corpus" / "yangming_biography.json").read_text(encoding="utf-8"))
period_meta = json.loads((ROOT / "data" / "analysis" / "period_meta.json").read_text(encoding="utf-8"))

events = bio["events"]
colors = bio["color_palette"]

LANE_ORDER = ["思想", "传习录", "军事", "贬谪", "仕宦", "科举", "生平"]
LANE_Y = {cat: i for i, cat in enumerate(LANE_ORDER)}

fig, ax = plt.subplots(figsize=(18, 9))

# ============================================================================
# 顶部时段轨道 (6 行纵向堆叠)
# ============================================================================
TRACK_H = 0.32
TRACK_GAP = 0.10
BAND_BOTTOM = len(LANE_ORDER) + 0.8
for i, (p_code, meta) in enumerate(period_meta.items()):
    color = PERIOD_COLORS[p_code]
    y0 = BAND_BOTTOM + i * (TRACK_H + TRACK_GAP)
    rect = Rectangle((meta["year_min"] - 0.3, y0),
                     meta["year_max"] - meta["year_min"] + 0.6,
                     TRACK_H,
                     facecolor=color, alpha=0.70, edgecolor="white", lw=0.4, zorder=2)
    ax.add_patch(rect)
    mid = (meta["year_min"] + meta["year_max"]) / 2
    ax.text(mid, y0 + TRACK_H / 2,
            f"{p_code}  {meta['name']}  ({meta['year_min']}–{meta['year_max']})",
            ha="center", va="center",
            fontsize=9, fontweight="bold", color="white", zorder=5)
BAND_TOP = BAND_BOTTOM + 6 * (TRACK_H + TRACK_GAP)

ax.text(1467, BAND_BOTTOM + 3 * (TRACK_H + TRACK_GAP),
        "传习录\n六时段", ha="right", va="center",
        fontsize=9, color="#666666")

# ============================================================================
# 泳道 (7 行)
# ============================================================================
for cat, y in LANE_Y.items():
    ax.axhspan(y - 0.4, y + 0.4, color=colors[cat], alpha=0.06, zorder=1)
    ax.text(1467, y, cat, ha="right", va="center", fontsize=10,
            fontweight="bold", color=colors[cat])
    ax.axhline(y, xmin=0.05, xmax=0.996, color=colors[cat], alpha=0.25, lw=0.6, zorder=2)

# ============================================================================
# 事件点 (3 档错位放置标签)
# ============================================================================
events_sorted = sorted(events, key=lambda e: (e["year"], -e["significance"]))

# Significance 5 事件画背景柱
for ev in events:
    if ev["significance"] == 5:
        ax.axvline(ev["year"], color=colors[ev["category"]],
                   alpha=0.10, lw=3.5, zorder=1.5)

# 3 档 stagger: 同 lane 内根据排序 index % 3 决定 y_offset 距离
# 进一步加引导线确保对应关系清晰
prev_in_cat = {}
for ev in events_sorted:
    yr, cat, sig = ev["year"], ev["category"], ev["significance"]
    y = LANE_Y[cat]
    color = colors[cat]

    size = 6 + sig * 2.5
    ax.plot(yr, y, marker="o", color=color, markersize=size,
            markeredgecolor="white", markeredgewidth=1.2, zorder=6)

    # 标签放置策略: 同 lane 上一事件 < 6 年用更远距离, < 3 年用最远
    last_yr = prev_in_cat.get(cat)
    if last_yr is None or yr - last_yr >= 6:
        offset_level = 0   # 近距离
        side = 1           # 默认向上
    elif yr - last_yr >= 3:
        offset_level = 1   # 中距离
        side = -1          # 向下
    else:
        offset_level = 2   # 远距离
        side = 1           # 再向上
    prev_in_cat[cat] = yr

    # 偏移距离 (y 单位)
    y_offsets = [0.32, 0.52, 0.78]
    y_off = y_offsets[offset_level] * side

    # 标签
    label = f"{yr}　{ev['event']}"
    if len(ev["event"]) > 11:
        label = f"{yr}　{ev['event'][:11]}\n　　　　{ev['event'][11:]}"

    va = "bottom" if side > 0 else "top"
    fontsize = 8.2 + (0.6 if sig >= 4 else 0)
    weight = "bold" if sig == 5 else "normal"

    # 引导线 (当 offset_level >= 1 时)
    if offset_level >= 1:
        ax.plot([yr, yr], [y, y + y_off], color=color, lw=0.4, alpha=0.5, zorder=4)

    ax.text(yr, y + y_off, label, ha="center", va=va,
            fontsize=fontsize, color="#222", fontweight=weight, zorder=7,
            bbox=dict(boxstyle="round,pad=0.18", fc="white",
                      ec=color if sig == 5 else "#cccccc",
                      lw=0.5, alpha=0.95) if sig >= 4 else
                 dict(boxstyle="round,pad=0.08", fc="white",
                      ec="none", alpha=0.85))

# ============================================================================
# 轴
# ============================================================================
ax.set_xlim(1465, 1532)
ax.set_ylim(-1.0, BAND_TOP + 0.5)
ax.set_yticks([])
for spine in ["left", "top", "right"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_position(("data", -0.7))
ax.spines["bottom"].set_color("#888888")

ax.set_xticks(list(range(1472, 1531, 5)))
ax.tick_params(axis="x", colors="#555555")

ax2 = ax.secondary_xaxis("top")
ax2.set_xticks(list(range(1472, 1531, 5)))
ax2.set_xticklabels([str(y - 1472) for y in range(1472, 1531, 5)])
ax2.tick_params(axis="x", colors="#888888", labelsize=8.5)
ax2.spines["top"].set_visible(False)

ax.set_xlabel("公元年份  (上轴: 阳明年龄)", fontsize=10, labelpad=5)

ax.set_title("图 1  王阳明 (1472-1529) 生平大事编年与传习录六时段覆盖范围",
             loc="left", fontsize=13, pad=22)

ax.text(1532, BAND_TOP + 0.3, "圆点大小: 思想史重要程度\n引导线: 标签 ↔ 事件",
        ha="right", va="top", fontsize=8, color="#666666", style="italic")

out = ROOT / "figure" / "fig01_life_timeline.png"
plt.savefig(out)
print(f"saved: {out}")
