"""图 6: T4 内部分裂

T4 涵盖 1518-1527, 但实际是两个不同阳明的合订本:
  T4-早 (1518 训蒙大意 + 教约): 6 条, 1,209 字 —— 致良知尚未提出
  T4-晚 (1521+ 答顾东桥等 8 封书信): 64 条, 25,350 字 —— 致良知已成纲领

对照画 8 个关键概念的频率, 直观展示"同一时段内的两个阳明"
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]

EARLY_CHAPTERS = ["训蒙大意示教读刘伯颂等", "教约"]
LATE_CHAPTERS  = ["答顾东桥书", "答周道通书", "答陆原静书", "又(答陆原静)",
                  "答欧阳崇一", "答罗整庵少宰书", "答聂文蔚一", "答聂文蔚二"]

CONCEPTS_8 = ["致良知", "良知", "心即理", "知行合一",
              "人欲", "天理", "朱子", "格物"]

def freq_for(period, chapters):
    recs = [r for r in records if r["time_period"] == period and r["chapter"] in chapters]
    chars = sum(r["char_count"] for r in recs)
    n = len(recs)
    out = {"n_entries": n, "chars": chars}
    for c in CONCEPTS_8:
        cnt = sum(r["text"].count(c) for r in recs)
        out[c] = cnt / chars * 1000 if chars > 0 else 0
    return out

# 5 组数据: T3, T4-早 (1518), T4-晚 (1521+), T5, T6
groups = [
    ("T3 薛侃期\n(1519–1522, 35 条)",       "T3", None),
    ("T4-早 训蒙/教约\n(1518, 6 条)",        "T4", EARLY_CHAPTERS),
    ("T4-晚 致良知后书信\n(1521+, 64 条)",   "T4", LATE_CHAPTERS),
    ("T5 中后期门人录\n(1515–1528, 47 条)",  "T5", None),
    ("T6 晚年定型期\n(1521–1528, 96 条)",    "T6", None),
]

freqs = []
for label, period, chapters in groups:
    if chapters is None:
        recs = [r for r in records if r["time_period"] == period]
    else:
        recs = [r for r in records if r["time_period"] == period and r["chapter"] in chapters]
    chars = sum(r["char_count"] for r in recs)
    row = {"label": label}
    for c in CONCEPTS_8:
        cnt = sum(r["text"].count(c) for r in recs)
        row[c] = cnt / chars * 1000 if chars > 0 else 0
    freqs.append(row)

# ============================================================================
# Heatmap-style 显示
# ============================================================================
fig, ax = plt.subplots(figsize=(12, 6))

matrix = np.zeros((len(CONCEPTS_8), len(groups)))
for j, row in enumerate(freqs):
    for i, c in enumerate(CONCEPTS_8):
        matrix[i, j] = row[c]

im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0)

# 数字标注
for i in range(matrix.shape[0]):
    for j in range(matrix.shape[1]):
        v = matrix[i, j]
        color = "white" if v > matrix.max() * 0.5 else "#222222"
        if v > 0:
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=10, color=color)
        else:
            ax.text(j, i, "0", ha="center", va="center",
                    fontsize=10, color="#aaaaaa")

# T4 早晚边界
ax.axvline(2.5, color="#222222", lw=2.5)
ax.axvline(1.5, color="#888888", lw=0.8, ls="--", alpha=0.5)

# 强调 T4 早晚之间的鸿沟 (放在热图下方; imshow y=0 在顶, y=7 在底, 用 y=8 + 进底外)
ax.annotate("", xy=(2, 8.0), xytext=(1, 8.0),
            arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=2.0))
ax.text(1.5, 8.3, "T4 内部的真实裂缝", ha="center", va="top",
        fontsize=11, color="#c0392b", fontweight="bold")
# 扩展 y 轴下界让注释可见
ax.set_ylim(8.7, -0.5)

# 坐标
ax.set_xticks(range(len(groups)))
ax.set_xticklabels([g[0] for g in groups], fontsize=9.5)
ax.set_yticks(range(len(CONCEPTS_8)))
ax.set_yticklabels(CONCEPTS_8, fontsize=10.5)

# colorbar
cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.03)
cbar.set_label("每千字出现次数", fontsize=9.5)

ax.set_title("图 6  T4 内部分裂: 1518 训蒙 vs 1521+ 致良知书信  "
             "(同一时段标签下是两个不同阳明)",
             loc="left", fontsize=12, pad=14)

plt.tight_layout()

out = ROOT / "figure" / "fig06_t4_internal_split.png"
plt.savefig(out)
print(f"saved: {out}")
