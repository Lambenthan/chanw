"""图 4: 五个过渡的散度对比 (探针主图)

横轴: 5 个过渡 (T1→T2, ..., T5→T6)
纵轴 (左): L1 距离 + 内部基线 95% 上界 (灰带)
纵轴 (右): 新现 + 退场概念数 (柱)
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme, PERIOD_COLORS

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
trans = json.loads((ROOT / "data" / "analysis" / "probe_divergence.json").read_text(encoding="utf-8"))
nr    = json.loads((ROOT / "data" / "analysis" / "probe_new_retired.json").read_text(encoding="utf-8"))
bl    = json.loads((ROOT / "data" / "analysis" / "probe_baselines.json").read_text(encoding="utf-8"))["baselines"]

fig, ax_l = plt.subplots(figsize=(11, 6))

x = np.arange(len(trans))
labels = [f"{t['from']} → {t['to']}" for t in trans]

# ============================================================================
# 左轴: 实际散度 + 内部基线带
# ============================================================================
l1_vals = [t["L1"] for t in trans]
js_vals = [t["JS"] for t in trans]

# 内部基线 (两端时段 L1_p95 的最大值, 作为 noise band 上界)
bl_p95 = []
bl_mean = []
for t in trans:
    bsrc = bl[t["from"]]; bdst = bl[t["to"]]
    bl_p95.append(max(bsrc["L1_p95"], bdst["L1_p95"]))
    bl_mean.append(max(bsrc["L1_mean"], bdst["L1_mean"]))

# 阴影带: mean → p95
ax_l.fill_between(x, bl_mean, bl_p95, color="#cccccc", alpha=0.5,
                  label="内部基线 (同时段随机切两半: 均值-95%)")
ax_l.plot(x, bl_p95, color="#888888", lw=0.7, ls="--", alpha=0.7)
ax_l.plot(x, bl_mean, color="#aaaaaa", lw=0.7, ls=":", alpha=0.7)

# 实际散度: 主线
line, = ax_l.plot(x, l1_vals, marker="o", lw=2.2, markersize=10,
                  color="#c0392b", label="实际散度 (L1)", zorder=5)
# 标数值
for i, v in enumerate(l1_vals):
    ax_l.text(i, v + 0.005, f"{v:.4f}", ha="center", va="bottom",
              fontsize=10, fontweight="bold", color="#c0392b")

# 高亮 T3→T4
peak_idx = int(np.argmax(l1_vals))
ax_l.plot(peak_idx, l1_vals[peak_idx], marker="o", markersize=16,
          markerfacecolor="none", markeredgecolor="#8b0000",
          markeredgewidth=2.5, zorder=4)
ax_l.annotate("最大跳跃", xy=(peak_idx, l1_vals[peak_idx]),
              xytext=(peak_idx + 0.3, l1_vals[peak_idx] + 0.015),
              fontsize=10, color="#8b0000", fontweight="bold",
              arrowprops=dict(arrowstyle="->", color="#8b0000", lw=1.2))

ax_l.set_xticks(x)
ax_l.set_xticklabels(labels, fontsize=11)
ax_l.set_ylabel("L1 散度 (概念分布)", fontsize=11)
ax_l.set_ylim(0, max(bl_p95 + l1_vals) * 1.15)
ax_l.set_xlabel("相邻时段过渡", fontsize=11, labelpad=8)

# ============================================================================
# 右轴: 新现 + 退场概念数
# ============================================================================
ax_r = ax_l.twinx()
new_counts = [n["new_count"] for n in nr]
ret_counts = [n["retired_count"] for n in nr]

bar_width = 0.32
ax_r.bar(x - bar_width/2, new_counts, bar_width,
         color="#27ae60", alpha=0.55, label="新现概念", edgecolor="white", lw=0.5)
ax_r.bar(x + bar_width/2, ret_counts, bar_width,
         color="#8e44ad", alpha=0.55, label="退场概念", edgecolor="white", lw=0.5)

# 柱顶标数
for i, (n, r) in enumerate(zip(new_counts, ret_counts)):
    if n > 0:
        ax_r.text(i - bar_width/2, n + 0.1, str(n), ha="center", va="bottom",
                  fontsize=9.5, color="#1e7a3b")
    if r > 0:
        ax_r.text(i + bar_width/2, r + 0.1, str(r), ha="center", va="bottom",
                  fontsize=9.5, color="#5b2e7a")

ax_r.set_ylabel("概念事件计数", fontsize=11)
ax_r.set_ylim(0, max(new_counts + ret_counts + [1]) * 1.6)
ax_r.spines["right"].set_visible(True)
ax_r.spines["right"].set_color("#888888")

# ============================================================================
# 注释 T3→T4 新现概念
# ============================================================================
t34_nr = nr[2]  # T3→T4
note = "新现: " + "、".join(c["concept"] for c in t34_nr["new"]) + "\n"
note += "退场: " + "、".join(c["concept"] for c in t34_nr["retired"])
ax_l.text(peak_idx, 0.005, note, ha="center", va="bottom", fontsize=8.5,
          color="#444444",
          bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#aaaaaa", lw=0.5, alpha=0.95))

# 双轴图例
lines_l, labs_l = ax_l.get_legend_handles_labels()
lines_r, labs_r = ax_r.get_legend_handles_labels()
ax_l.legend(lines_l + lines_r, labs_l + labs_r,
            loc="upper left", fontsize=9, frameon=True, framealpha=0.95,
            ncol=2)

ax_l.set_title("图 4  反事实预测探针: 五个时段过渡的概念分布散度",
               loc="left", fontsize=12.5, pad=14)

out = ROOT / "figure" / "fig04_probe_divergence.png"
plt.savefig(out)
print(f"saved: {out}")
