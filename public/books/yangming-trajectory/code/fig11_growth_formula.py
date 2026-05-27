"""图 11: 阳明成长公式核心图

3 个子图:
  (a) 8 维度时间轨迹: 1496-1528, 标三步法分界 + 6 事件
  (b) 事件扰动条形图: 哪个事件扰动最大
  (c) 1506 ITS 详图: 8 维度在 1506 前后的反事实对比
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _theme import apply_theme

apply_theme()

ROOT = Path(__file__).resolve().parent.parent
year_summary = json.loads((ROOT / "data" / "analysis" / "personality_full_by_year.json").read_text(encoding="utf-8"))
its_results = json.loads((ROOT / "data" / "analysis" / "its_full_corpus.json").read_text(encoding="utf-8"))
val = json.loads((ROOT / "data" / "analysis" / "three_step_validation.json").read_text(encoding="utf-8"))

DIMENSIONS = ["教学耐心", "反权威", "自我修正", "同理心", "实践导向",
              "处变能力", "决断力", "情感深度"]
DIM_COLORS = {
    "教学耐心": "#3a7a4e", "反权威": "#c0392b", "自我修正": "#5b8db8",
    "同理心":   "#c08a3e", "实践导向": "#8b3d6f",
    "处变能力": "#7c3a3a", "决断力":  "#c8651b", "情感深度": "#5b2e7a",
}

EVENTS = [
    (1506, "廷杖贬龙场", "#c0392b"),
    (1508, "龙场悟道",   "#7b3f8e"),
    (1517, "徐爱卒",     "#5b8db8"),
    (1519, "平宁王之乱", "#c8651b"),
    (1521, "致良知",     "#3a7a4e"),
    (1527, "天泉证道",   "#444444"),
]

fig = plt.figure(figsize=(17, 13))
gs = fig.add_gridspec(3, 1, height_ratios=[1.6, 1, 1.6], hspace=0.50)

# ============================================================================
# (a) 8 维度时间轨迹 + 三步法分期
# ============================================================================
ax_a = fig.add_subplot(gs[0])

# 三步法背景 (沉默期标签放左下角, 后期稳定放右下角, 1506 callout 放右上角)
ax_a.axvspan(1495, 1506, color="#cccccc", alpha=0.30, zorder=0)
ax_a.text(1500.5, 1.04, "① 沉默期 (1496-1506)", ha="center", va="bottom",
          fontsize=10.5, color="#444", fontweight="bold",
          transform=ax_a.get_xaxis_transform())
ax_a.axvspan(1506, 1508, color="#c0392b", alpha=0.25, zorder=0)
# 1506 危机注释 callout 移到右上角, 避开沉默期标签
ax_a.annotate("② 1506 危机触发\n廷杖几死 → 贬龙场",
              xy=(1507, 1.01), xytext=(1525, 1.22),
              xycoords=ax_a.get_xaxis_transform(),
              ha="center", va="top",
              fontsize=9.5, color="#c0392b", fontweight="bold",
              arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.0,
                              connectionstyle="arc3,rad=-0.25"),
              bbox=dict(boxstyle="round,pad=0.25", fc="white",
                        ec="#c0392b", lw=0.7, alpha=0.95))
ax_a.axvspan(1508, 1530, color="#5fa39a", alpha=0.15, zorder=0)
ax_a.text(1518, 1.04, "③ 后期稳定 (1508-1528)", ha="center", va="bottom",
          fontsize=10.5, color="#1e7a3b", fontweight="bold",
          transform=ax_a.get_xaxis_transform())

# 画 8 条维度时间序列 (归一化)
all_years = sorted(int(y) for y in year_summary.keys())
for dim in DIMENSIONS:
    color = DIM_COLORS[dim]
    vals = []
    ys = []
    for y in all_years:
        d = year_summary[str(y)].get(dim)
        if d is None: continue
        vals.append(d["mean"])
        ys.append(y)
    vals = np.array(vals)
    # 归一化: 减均值除最大绝对值, 让所有线在同一尺度可比
    vmax = max(np.abs(vals).max(), 0.01)
    vals_norm = vals / vmax
    ax_a.plot(ys, vals_norm, marker="o", lw=1.5, markersize=4,
              color=color, alpha=0.85, label=dim)

# 事件竖线
for yr, name, c in EVENTS:
    ax_a.axvline(yr, color=c, lw=0.7, ls=":", alpha=0.5, zorder=1)

ax_a.set_xlim(1494, 1530)
ax_a.set_xticks(range(1496, 1530, 2))
ax_a.set_ylim(-1.1, 1.1)
ax_a.set_ylabel("各维度归一化净分", fontsize=10.5)
ax_a.set_xlabel("公元年份", fontsize=10.5)
ax_a.legend(loc="lower right", fontsize=8, ncol=4, frameon=True, framealpha=0.92)
ax_a.set_title("(a)  阳明 8 维度人格随年份演化  (1496-1528, 28 个时间点)",
               loc="left", fontsize=12, pad=8)

# ============================================================================
# (b) 事件扰动 bar chart
# ============================================================================
ax_b = fig.add_subplot(gs[1])
edt = val["event_total_disturbance"]
# 排序
sorted_events = sorted(edt.items(), key=lambda x: -x[1][0])
labels = [k for k, _ in sorted_events]
totals = [v[0] for _, v in sorted_events]
sigs   = [v[1] for _, v in sorted_events]

colors = []
for ev in labels:
    if "1506" in ev:
        colors.append("#c0392b")  # 突出 1506
    elif "1508" in ev:
        colors.append("#7b3f8e")
    elif "1521" in ev:
        colors.append("#cccccc")  # 凸显 1521 反而很弱
    else:
        colors.append("#888888")

y = np.arange(len(labels))
bars = ax_b.barh(y, totals, color=colors, alpha=0.88, edgecolor="white", lw=0.6)
for i, (t, s) in enumerate(zip(totals, sigs)):
    ax_b.text(t + 0.5, i, f"扰动 = {t:.1f}, {s} 维显著",
              va="center", fontsize=9.5, color="#222")

ax_b.set_yticks(y)
ax_b.set_yticklabels(labels, fontsize=10.5)
ax_b.invert_yaxis()
ax_b.set_xlim(0, max(totals) * 1.35)
ax_b.set_xlabel("总人格扰动 (8 维度 |effect| 之和)")
ax_b.axvline(np.mean(totals[1:]), color="#888", lw=0.7, ls="--", alpha=0.6)
ax_b.text(np.mean(totals[1:]) + 0.4, len(labels) - 0.3,
          f"后期平均 = {np.mean(totals[1:]):.1f}",
          fontsize=8.5, color="#666", style="italic")
ax_b.set_title(f"(b)  1506 廷杖是人格史上最大重组事件,"
               f" 扰动是后期平均的 {val['ratio_1506_to_avg_post']:.1f} 倍",
               loc="left", fontsize=11.5, pad=8)

# ============================================================================
# (c) 1506 ITS 详图: 8 维度在 1506 前后的实际 vs 反事实
# ============================================================================
ax_c = fig.add_subplot(gs[2])

# 8 维度的 1506 ITS, x = 维度索引, y = 实际 vs 反事实 偏离
its_1506 = its_results["results"].get("1506 廷杖贬龙场", {})
x = np.arange(len(DIMENSIONS))
actuals = []
cfs = []
effects = []
ts = []
for dim in DIMENSIONS:
    r = its_1506.get(dim, {})
    actuals.append(r.get("actual_post", 0))
    cfs.append(r.get("cf_post", 0))
    effects.append(r.get("effect", 0))
    ts.append(r.get("t", 0))

width = 0.35
ax_c.bar(x - width/2, cfs, width, color="#aaaaaa", alpha=0.7,
         label="反事实预测 (pre-trend 外推)", edgecolor="white", lw=0.4)
ax_c.bar(x + width/2, actuals, width, color="#c0392b", alpha=0.85,
         label="1506 后实际", edgecolor="white", lw=0.4)

# 标 effect + 显著性
for i, (eff, t) in enumerate(zip(effects, ts)):
    sig = "★★★" if abs(t) > 2.58 else "★★" if abs(t) > 1.96 else "★" if abs(t) > 1.64 else ""
    color_eff = "#1e7a3b" if eff > 0 else "#7c3a3a"
    top_y    = max(actuals[i], cfs[i])
    bottom_y = min(actuals[i], cfs[i])
    # 正向标在顶部上方; 负向标在底部下方
    if eff >= 0:
        ax_c.text(i, top_y + 0.4, f"{eff:+.2f}\n{sig}", ha="center", va="bottom",
                  fontsize=9.5, color=color_eff, fontweight="bold")
    else:
        ax_c.text(i, bottom_y - 0.4, f"{eff:+.2f}\n{sig}", ha="center", va="top",
                  fontsize=9.5, color=color_eff, fontweight="bold")

# 扩 y 范围确保 +10.28 和 -7.05 标注都能显示
ax_c_ymin = min(actuals + cfs) - 2.5
ax_c_ymax = max(actuals + cfs) + 2.5
ax_c.set_ylim(ax_c_ymin, ax_c_ymax)

ax_c.set_xticks(x)
ax_c.set_xticklabels(DIMENSIONS, fontsize=10)
ax_c.set_ylabel("每千字净分", fontsize=10.5)
ax_c.axhline(0, color="#888", lw=0.5)
ax_c.legend(loc="upper left", fontsize=9.5, frameon=True, framealpha=0.93)
ax_c.set_title("(c)  1506 廷杖前后 8 维度实际 vs 反事实  (★★★ p<.01, ★★ p<.05)",
               loc="left", fontsize=11.5, pad=8)

plt.suptitle("图 11  阳明成长公式: 沉默期 (1496-1506) → 1506 危机 → 后期稳定 (1508-1528)",
             fontsize=14, x=0.04, y=0.985, ha="left", fontweight="bold")
plt.subplots_adjust(top=0.93, bottom=0.06, left=0.06, right=0.97)

out = ROOT / "figure" / "fig11_growth_formula.png"
plt.savefig(out, bbox_inches="tight", pad_inches=0.25, facecolor="white")
print(f"saved: {out}")
