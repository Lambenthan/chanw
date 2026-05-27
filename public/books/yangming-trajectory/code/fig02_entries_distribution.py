"""图 2: 传习录 343 条按记录者/时段分布

两个子图:
  左: 343 条按顺序排列, 每条画成一个垂直短线, 高度按字数, 颜色按时段
  右: 各记录者贡献条目数 + 字数双轴条形图
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

fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), gridspec_kw={"width_ratios": [2.2, 1]})

# ===========================================================================
# 左图: 343 条按编号顺序排列, 垂直条高度 = 字数, 颜色 = 时段
# ===========================================================================
ax = axes[0]
for r in records:
    color = PERIOD_COLORS[r["time_period"]]
    ax.vlines(r["item_no"], 0, r["char_count"], color=color, lw=0.9, alpha=0.85)

# 卷与卷之间的边界线
ax.axvline(130.5, color="#888888", lw=0.5, ls="--", alpha=0.7)
ax.axvline(200.5, color="#888888", lw=0.5, ls="--", alpha=0.7)
ax.text(65,  2500, "卷上",  ha="center", va="center", fontsize=11, color="#555555", fontweight="bold")
ax.text(165, 2500, "卷中",  ha="center", va="center", fontsize=11, color="#555555", fontweight="bold")
ax.text(271, 2500, "卷下",  ha="center", va="center", fontsize=11, color="#555555", fontweight="bold")

# 几个标志条目用箭头标出
HIGHLIGHTS = [
    (1,   "徐爱录开篇", 0.7),
    (132, "知行并进", 0.55),
    (315, "天泉证道\n四句教", 0.55),
]
for itno, label, ypos in HIGHLIGHTS:
    rec = next(r for r in records if r["item_no"] == itno)
    h = rec["char_count"]
    ax.annotate(label, xy=(itno, h), xytext=(itno, 2100),
                ha="center", va="bottom", fontsize=8.5, color="#222222",
                fontweight="bold",
                arrowprops=dict(arrowstyle="-", lw=0.5, color="#555"),
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="#888", lw=0.5, alpha=0.92))

ax.set_xlim(0, 350)
ax.set_ylim(0, 2600)         # 加高顶部, 给标签和图例腾空间
ax.set_xlabel("传习录条目编号 (1-343)")
ax.set_ylabel("每条字数")
ax.set_title("(a)  343 条按编号顺序的字数分布", loc="left", fontsize=11)

# 时段图例 (放到 axes 顶部, 不挡条目)
from matplotlib.lines import Line2D
legend_items = [Line2D([0], [0], color=PERIOD_COLORS[p], lw=3,
                       label=f"{p} {period_meta[p]['name']} ({period_meta[p]['year_min']}–{period_meta[p]['year_max']})")
                for p in ["T1", "T2", "T3", "T4", "T5", "T6"]]
ax.legend(handles=legend_items, loc="upper center", fontsize=8, ncol=6,
          bbox_to_anchor=(0.5, -0.10), framealpha=0.95, frameon=False)

# ===========================================================================
# 右图: 各记录者 / 收信人贡献统计
# ===========================================================================
ax = axes[1]

# 聚合
by_rec = defaultdict(lambda: {"n": 0, "chars": 0, "period": None})
for r in records:
    rec = r["recorder_or_addressee"] or "(无)"
    by_rec[rec]["n"]      += 1
    by_rec[rec]["chars"]  += r["char_count"]
    by_rec[rec]["period"]  = r["time_period"]

# 按字数排序
items = sorted(by_rec.items(), key=lambda x: x[1]["chars"], reverse=True)
labels  = [k for k, _ in items]
ns      = [v["n"]     for _, v in items]
charss  = [v["chars"] for _, v in items]
colors  = [PERIOD_COLORS[v["period"]] for _, v in items]

y = np.arange(len(labels))
ax.barh(y, charss, color=colors, alpha=0.85, edgecolor="white", lw=0.5)

# 条目数注在柱子右端
for i, (n, c) in enumerate(zip(ns, charss)):
    ax.text(c + 100, i, f"{c:,} 字 / {n} 条",
            va="center", fontsize=8.5, color="#333333")

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("贡献总字数")
ax.set_xlim(0, max(charss) * 1.32)
ax.set_title("(b)  各记录者 / 收信人贡献量", loc="left", fontsize=11)

plt.suptitle("图 2  传习录 343 条的时序分布与记录者构成",
             fontsize=12.5, x=0.07, y=1.01, ha="left")

out = ROOT / "figure" / "fig02_entries_distribution.png"
plt.savefig(out)
print(f"saved: {out}")
