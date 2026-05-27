"""图 10: 合成控制法结果

四个 treated 概念各画一张子图: 实际 vs 反事实轨迹
附加: placebo 偏离分布 + 4 个 treated 偏离的位置
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
sc = json.loads((ROOT / "data" / "analysis" / "synthetic_control.json").read_text(encoding="utf-8"))

TREATED = ["致良知", "良知", "人欲", "天理"]
treatment_year = sc["treatment_year"]
years = sc["years"]

fig = plt.figure(figsize=(15, 8))
gs = fig.add_gridspec(2, 5, width_ratios=[1, 1, 1, 1, 1.2], hspace=0.32, wspace=0.32)

# ============================================================================
# 4 个子图: 各 treated 序列
# ============================================================================
for k, concept in enumerate(TREATED):
    ax = fig.add_subplot(gs[k // 2, (k % 2) * 2:(k % 2) * 2 + 2])
    r = sc["results"][concept]

    pre_y, pre_a, pre_c = r["pre_years"], r["pre_actual"], r["pre_cf"]
    post_y, post_a, post_c = r["post_years"], r["post_actual"], r["post_cf"]

    # 实际线
    actual_y = pre_y + post_y
    actual_v = pre_a + post_a
    ax.plot(actual_y, actual_v, marker="o", color="#c0392b", lw=2.2,
            markersize=7, label="实际", zorder=5)

    # 反事实线
    cf_y = pre_y + post_y
    cf_v = pre_c + post_c
    ax.plot(cf_y, cf_v, marker="s", color="#5b8db8", lw=2.0,
            markersize=6, ls="--", label="合成反事实", zorder=4)

    # 灰色填充表示差距
    post_y_arr = np.array(post_y)
    ax.fill_between(post_y_arr, post_a, post_c, alpha=0.18,
                    color="#c0392b" if r["post_effect"] > 0 else "#5b8db8")

    # treatment 线
    ax.axvline(treatment_year, color="#888", lw=1.2, ls=":", alpha=0.7)
    ax.text(treatment_year + 0.1, ax.get_ylim()[1] * 0.92,
            "1521 致良知", fontsize=8.5, color="#666", style="italic")

    ax.set_title(f"{concept}    偏离 = {r['post_effect']:+.2f}/千字",
                 loc="left", fontsize=11, fontweight="bold")
    ax.set_xlabel("年份", fontsize=9.5)
    ax.set_ylabel("每千字频率", fontsize=9.5)
    if k == 0:
        ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.2, lw=0.4)

# ============================================================================
# 第 5 列: Placebo 偏离分布 vs Treated 偏离
# ============================================================================
ax = fig.add_subplot(gs[:, 4])

placebo_effects = sc["placebo_effects"]
placebo_array = np.array(list(placebo_effects.values()))
placebo_names = list(placebo_effects.keys())

# Placebo 散点 (横轴 = 0)
ax.scatter([0] * len(placebo_array), placebo_array,
           s=80, color="#aaaaaa", alpha=0.6, label="Placebo (donor 当 treated)",
           edgecolor="white", lw=0.5)
for n, e in zip(placebo_names, placebo_array):
    ax.text(0.05, e, n, fontsize=8, va="center", color="#666")

# Treated 散点 (横轴 = 1)
treated_effects = [sc["results"][c]["post_effect"] for c in TREATED]
colors_t = ["#c0392b", "#c0392b", "#5b8db8", "#5b8db8"]
ax.scatter([1] * len(treated_effects), treated_effects,
           s=150, color=colors_t, alpha=0.85, edgecolor="black", lw=0.8,
           label="Treated (真正 treated)")
for n, e in zip(TREATED, treated_effects):
    ax.text(1.08, e, n, fontsize=10, va="center", color="#222", fontweight="bold")

# Placebo 95% 区间
p_low, p_high = np.percentile(placebo_array, [2.5, 97.5])
ax.axhspan(p_low, p_high, color="#aaaaaa", alpha=0.18,
           label="Placebo 95% 区间")
ax.axhline(0, color="#888", lw=0.6, ls="--", alpha=0.6)

ax.set_xlim(-0.4, 1.5)
ax.set_xticks([0, 1])
ax.set_xticklabels(["Placebo", "Treated"], fontsize=10)
ax.set_ylabel("Post 期实际 vs 反事实偏离 (每千字)", fontsize=10)
ax.set_title("(c)  Placebo 检验:\n良知 +5.27 显著超出\n placebo 区间, 是真信号",
             loc="left", fontsize=10.5)
ax.legend(loc="lower right", fontsize=8.5)

plt.suptitle("图 10  合成控制法: 用稳定概念作 donor 池构造致良知诞生 (1521) 的反事实世界",
             fontsize=12.5, x=0.05, y=1.00, ha="left")

out = ROOT / "figure" / "fig10_synthetic_control.png"
plt.savefig(out)
print(f"saved: {out}")
