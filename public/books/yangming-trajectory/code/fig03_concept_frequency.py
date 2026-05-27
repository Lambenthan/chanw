"""图 3: 核心概念在六时段的频率演化

衡量"思想漂移"最直白的指标: 每个概念在该时段每千字出现多少次.

选词原则:
  - 心学纲领性术语 (良知 / 致良知 / 心即理 / 知行合一)
  - 阳明改造的传统术语 (格物 / 致知 / 诚意 / 天理 / 人欲)
  - 阳明独特表达 (事上 / 心外无 / 立志)
"""
import json
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme, PERIOD_COLORS

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]
period_meta = json.loads((ROOT / "data" / "analysis" / "period_meta.json").read_text(encoding="utf-8"))

PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]

# 待追踪概念
CONCEPTS = [
    ("良知",    "心学纲领"),
    ("致良知",  "心学纲领"),
    ("心即理",  "心学纲领"),
    ("知行合一", "心学纲领"),
    ("格物",    "传统改造"),
    ("致知",    "传统改造"),
    ("诚意",    "传统改造"),
    ("天理",    "传统改造"),
    ("人欲",    "传统改造"),
    ("事上",    "阳明特色"),
    ("心外无",  "阳明特色"),
    ("立志",    "阳明特色"),
]

# 按时段聚合: chars 总数 + 每个概念出现次数
period_stats = {p: {"chars": 0, **{c: 0 for c, _ in CONCEPTS}} for p in PERIODS}
for r in records:
    p = r["time_period"]
    period_stats[p]["chars"] += r["char_count"]
    for concept, _ in CONCEPTS:
        period_stats[p][concept] += r["text"].count(concept)

# 计算"每千字出现频率"
freq_matrix = np.zeros((len(CONCEPTS), len(PERIODS)))
for j, p in enumerate(PERIODS):
    chars = period_stats[p]["chars"]
    for i, (c, _) in enumerate(CONCEPTS):
        freq_matrix[i, j] = period_stats[p][c] / chars * 1000  # 每千字

# 画图: 上下两部分
fig, axes = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw={"height_ratios": [1, 2.2]})

# ===========================================================================
# (a) 六时段字数概览
# ===========================================================================
ax = axes[0]
counts = [period_stats[p]["chars"] for p in PERIODS]
entries = [sum(1 for r in records if r["time_period"] == p) for p in PERIODS]
colors = [PERIOD_COLORS[p] for p in PERIODS]

x = np.arange(len(PERIODS))
bars = ax.bar(x, counts, color=colors, alpha=0.85, edgecolor="white", lw=0.5)
for i, (c, n) in enumerate(zip(counts, entries)):
    ax.text(i, c + 400, f"{c:,} 字\n{n} 条",
            ha="center", va="bottom", fontsize=9, color="#222222")

ax.set_xticks(x)
ax.set_xticklabels([f"{p}\n{period_meta[p]['name']}\n{period_meta[p]['year_min']}–{period_meta[p]['year_max']}"
                    for p in PERIODS], fontsize=9)
ax.set_ylabel("字数")
ax.set_ylim(0, max(counts) * 1.25)
ax.set_title("(a)  六时段字数与条目数", loc="left", fontsize=11)

# ===========================================================================
# (b) 概念在六时段的频率 (heatmap + 标注首次出现)
# ===========================================================================
ax = axes[1]

# heatmap
im = ax.imshow(freq_matrix, aspect="auto", cmap="YlOrRd",
               vmin=0, vmax=max(freq_matrix.max(), 1.0))

# 在每格写数值
for i in range(freq_matrix.shape[0]):
    for j in range(freq_matrix.shape[1]):
        v = freq_matrix[i, j]
        if v > 0:
            color = "white" if v > freq_matrix.max() * 0.5 else "#222222"
            ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                    fontsize=9, color=color)
        else:
            ax.text(j, i, "0", ha="center", va="center",
                    fontsize=8.5, color="#aaaaaa")

# 用边框圈出"首次出现"那一格 (前面时段为0, 这一时段开始有)
for i, (concept, _) in enumerate(CONCEPTS):
    row = freq_matrix[i]
    first_j = None
    for j, v in enumerate(row):
        if v > 0:
            first_j = j
            break
    if first_j is not None and first_j > 0:
        # 用粗黑框圈出
        rect = plt.Rectangle((first_j - 0.45, i - 0.45), 0.9, 0.9,
                             fill=False, edgecolor="black", lw=2.0, zorder=5)
        ax.add_patch(rect)

ax.set_xticks(np.arange(len(PERIODS)))
ax.set_xticklabels([f"{p}\n{period_meta[p]['year_min']}–{period_meta[p]['year_max']}"
                    for p in PERIODS], fontsize=9.5)
ax.set_yticks(np.arange(len(CONCEPTS)))
ax.set_yticklabels([c for c, _ in CONCEPTS], fontsize=10)

# (重复的分组标签代码已删除, 见下方居中版)

# 改用 axhline 分隔概念分组
group_boundaries = []
prev_g = None
for i, (c, g) in enumerate(CONCEPTS):
    if g != prev_g and i > 0:
        group_boundaries.append(i - 0.5)
    prev_g = g
for yb in group_boundaries:
    ax.axhline(yb, color="white", lw=2.5)

# 概念分组标签 (在右侧)
group_centers = {}
for g in set(grp for _, grp in CONCEPTS):
    indices = [i for i, (_, gx) in enumerate(CONCEPTS) if gx == g]
    group_centers[g] = sum(indices) / len(indices)
for g, center in group_centers.items():
    ax.text(5.55, center, g, ha="left", va="center",
            fontsize=9, color="#444444", style="italic")

ax.set_title("(b)  核心概念在六时段的频率 (每千字出现次数; 黑框 = 该概念首次进入正高频段)",
             loc="left", fontsize=11)

# colorbar
cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.08)
cbar.set_label("每千字出现次数", fontsize=9)
cbar.ax.tick_params(labelsize=8)

plt.suptitle("图 3  六时段字数概览与核心概念的频率演化",
             fontsize=13.5, x=0.05, y=0.98, ha="left", fontweight="bold")
plt.subplots_adjust(top=0.93, bottom=0.06, left=0.10, right=0.94, hspace=0.32)

out = ROOT / "figure" / "fig03_concept_frequency.png"
plt.savefig(out, bbox_inches="tight", pad_inches=0.25, facecolor="white")
print(f"saved: {out}")

# 同时打印数据表 (供后续核对)
print("\n=== 核心概念六时段频率 (每千字出现次数) ===")
print(f"{'概念':<10} | " + " | ".join(f"{p:>6}" for p in PERIODS))
print("-" * 60)
for i, (c, _) in enumerate(CONCEPTS):
    row = " | ".join(f"{freq_matrix[i, j]:>6.2f}" for j in range(len(PERIODS)))
    print(f"{c:<10} | {row}")
