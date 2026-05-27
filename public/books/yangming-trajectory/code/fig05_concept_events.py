"""图 5: 五个过渡的"新现 / 退场"概念事件全图

横轴: 概念 (按类别分组)
纵轴: 时段过渡 (5 个)
单元格: 该过渡中该概念的频率变化箭头, 绿色 = 新现, 紫色 = 退场, 灰 = 稳定
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
freq = json.loads((ROOT / "data" / "analysis" / "concept_freq_per_period.json").read_text(encoding="utf-8"))

# 按类别排好序的概念
from concept_vocabulary import CONCEPTS
CAT_ORDER = ["心学纲领", "传统改造", "阳明特色", "工夫论", "辩论对象"]
ordered_concepts = sorted(CONCEPTS, key=lambda x: (CAT_ORDER.index(x[1]), x[0]))

PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]
TRANSITIONS = [(PERIODS[i], PERIODS[i+1]) for i in range(len(PERIODS) - 1)]

# 构建矩阵: row = 概念, col = 过渡, value = log(dst/src) (正 = 增长, 负 = 萎缩)
NEW_THRESHOLD = 0.5
EPS_ZERO = 0.1

n_c = len(ordered_concepts)
n_t = len(TRANSITIONS)

log_change = np.zeros((n_c, n_t))
event_type = np.zeros((n_c, n_t), dtype=int)  # 0 stable, 1 new, -1 retired

for j, (src, dst) in enumerate(TRANSITIONS):
    for i, (concept, _) in enumerate(ordered_concepts):
        src_kc = freq[src]["concept_freqs"][concept]["per_kc"]
        dst_kc = freq[dst]["concept_freqs"][concept]["per_kc"]
        # log ratio (加 epsilon 防爆炸)
        eps = 0.05
        log_change[i, j] = np.log((dst_kc + eps) / (src_kc + eps))
        if src_kc < EPS_ZERO and dst_kc >= NEW_THRESHOLD:
            event_type[i, j] = 1
        elif src_kc >= NEW_THRESHOLD and dst_kc < EPS_ZERO:
            event_type[i, j] = -1

# ============================================================================
# 画图
# ============================================================================
fig, ax = plt.subplots(figsize=(13, 11))

# 主色: log-change heatmap 用 diverging
vmax = max(abs(log_change.min()), abs(log_change.max()), 1.0)
im = ax.imshow(log_change.T, aspect="auto", cmap="RdBu_r",
               vmin=-vmax, vmax=vmax, alpha=0.55)

# 在事件单元格上画明显的标记
for j in range(n_t):
    for i in range(n_c):
        et = event_type[i, j]
        if et == 1:  # 新现
            ax.scatter(i, j, marker="^", s=180, color="#1e7a3b",
                       edgecolor="white", lw=1.5, zorder=5)
            kc = freq[TRANSITIONS[j][1]]["concept_freqs"][ordered_concepts[i][0]]["per_kc"]
            ax.text(i, j, f"+{kc:.1f}", ha="center", va="center",
                    fontsize=7.5, color="white", fontweight="bold", zorder=6)
        elif et == -1:  # 退场
            ax.scatter(i, j, marker="v", s=180, color="#5b2e7a",
                       edgecolor="white", lw=1.5, zorder=5)
            kc = freq[TRANSITIONS[j][0]]["concept_freqs"][ordered_concepts[i][0]]["per_kc"]
            ax.text(i, j, f"-{kc:.1f}", ha="center", va="center",
                    fontsize=7.5, color="white", fontweight="bold", zorder=6)

# 类别分组虚线
prev_cat = None
group_starts = []
for i, (_, cat) in enumerate(ordered_concepts):
    if cat != prev_cat:
        if prev_cat is not None:
            ax.axvline(i - 0.5, color="white", lw=2.5)
        group_starts.append((i, cat))
        prev_cat = cat
group_starts.append((n_c, None))

# 顶部类别标签
for k in range(len(group_starts) - 1):
    s, cat = group_starts[k]
    e, _   = group_starts[k+1]
    mid = (s + e - 1) / 2
    ax.text(mid, -0.85, cat, ha="center", va="bottom",
            fontsize=10.5, fontweight="bold", color="#444444")

# 坐标
ax.set_xticks(range(n_c))
ax.set_xticklabels([c for c, _ in ordered_concepts], rotation=70, ha="right",
                   fontsize=9)
ax.set_yticks(range(n_t))
ax.set_yticklabels([f"{src} → {dst}" for src, dst in TRANSITIONS], fontsize=11)
ax.invert_yaxis()  # T1→T2 在顶部

# 标题
ax.set_title("图 5  五个时段过渡的概念事件全景  "
             "(▲ = 新现, ▼ = 退场, 颜色深浅 = log 频率变化幅度)",
             loc="left", fontsize=12, pad=24)

# colorbar
cbar = plt.colorbar(im, ax=ax, shrink=0.6, pad=0.04)
cbar.set_label("log(频率比 dst/src)\n红 = 增长, 蓝 = 萎缩", fontsize=9)
cbar.ax.tick_params(labelsize=8)

plt.tight_layout()

out = ROOT / "figure" / "fig05_concept_events.png"
plt.savefig(out)
print(f"saved: {out}")
