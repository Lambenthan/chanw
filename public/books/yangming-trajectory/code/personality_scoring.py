"""人格维度概念验证: 给 343 条逐条打 5 维分, 聚合到时段, 跑事件 pre/post"""
import json
from pathlib import Path
from collections import defaultdict

import numpy as np

from personality_markers import DIMENSIONS

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]


def score_text(text, positive_markers, negative_markers):
    """返回 (正向密度, 反向密度, 净分数). 密度 = 每千字出现次数."""
    n_chars = max(len(text), 1)
    pos = sum(text.count(m) for m in positive_markers)
    neg = sum(text.count(m) for m in negative_markers)
    pos_per_kc = pos / n_chars * 1000
    neg_per_kc = neg / n_chars * 1000
    return pos_per_kc, neg_per_kc, pos_per_kc - neg_per_kc


# 给每条打分
for r in records:
    r["scores"] = {}
    for dim, (pos, neg) in DIMENSIONS.items():
        p, n, net = score_text(r["text"], pos, neg)
        r["scores"][dim] = {"pos": p, "neg": n, "net": net}

# ============================================================================
# 时段层面聚合
# ============================================================================
PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]
period_scores = {p: {dim: {"pos": [], "neg": [], "net": []}
                     for dim in DIMENSIONS}
                 for p in PERIODS}

for r in records:
    for dim in DIMENSIONS:
        for k in ["pos", "neg", "net"]:
            period_scores[r["time_period"]][dim][k].append(r["scores"][dim][k])

# 计算每个 (时段, 维度) 的均值与标准误
period_summary = {p: {} for p in PERIODS}
for p in PERIODS:
    for dim in DIMENSIONS:
        net_vals = period_scores[p][dim]["net"]
        if net_vals:
            period_summary[p][dim] = {
                "mean": float(np.mean(net_vals)),
                "se":   float(np.std(net_vals, ddof=1) / np.sqrt(len(net_vals))),
                "n":    len(net_vals),
                "pos_mean": float(np.mean(period_scores[p][dim]["pos"])),
                "neg_mean": float(np.mean(period_scores[p][dim]["neg"])),
            }

print("=" * 78)
print("时段 × 维度 平均净分 (每千字, 正-反)")
print("=" * 78)
header = f"{'时段':<6} {'条目':>4}  " + "  ".join(f"{d:>10}" for d in DIMENSIONS)
print(header)
print("-" * len(header))
for p in PERIODS:
    n = period_summary[p][list(DIMENSIONS)[0]]["n"]
    vals = [period_summary[p][dim]["mean"] for dim in DIMENSIONS]
    print(f"{p:<6} {n:>4}  " + "  ".join(f"{v:>10.3f}" for v in vals))

# ============================================================================
# 事件 pre/post 分析
# ============================================================================
# 4 个外生事件 + 各自的 pre / post 时段集合
EVENTS = [
    ("1517 徐爱卒",   ["T1"],          ["T2", "T3", "T4"]),
    ("1519 宁王之乱", ["T1", "T2"],    ["T3", "T4", "T5"]),
    ("1521 致良知",   ["T1", "T2", "T3"], ["T4", "T5", "T6"]),
    ("1522 父王华卒", ["T1", "T2", "T3"], ["T4", "T5", "T6"]),
]

print("\n" + "=" * 78)
print("事件 pre/post 分析: 每个维度在事件前后的均值差")
print("=" * 78)
print(f"{'事件':<15} | " + " | ".join(f"{d:>8}" for d in DIMENSIONS))
print("-" * 78)

event_effects = {}
for event_name, pre_periods, post_periods in EVENTS:
    effects = {}
    pre_recs  = [r for r in records if r["time_period"] in pre_periods]
    post_recs = [r for r in records if r["time_period"] in post_periods]
    row = []
    for dim in DIMENSIONS:
        pre_vals  = [r["scores"][dim]["net"] for r in pre_recs]
        post_vals = [r["scores"][dim]["net"] for r in post_recs]
        if not pre_vals or not post_vals:
            row.append("—")
            effects[dim] = None
            continue
        diff = float(np.mean(post_vals) - np.mean(pre_vals))
        # 简易 Welch's t 检验
        n1, n2 = len(pre_vals), len(post_vals)
        v1 = float(np.var(pre_vals, ddof=1)) if n1 > 1 else 0.0
        v2 = float(np.var(post_vals, ddof=1)) if n2 > 1 else 0.0
        se = (v1/n1 + v2/n2) ** 0.5 if (v1+v2) > 0 else 1e-9
        t = diff / se if se > 0 else 0.0
        mark = "★★★" if abs(t) > 2.58 else "★★" if abs(t) > 1.96 else "★" if abs(t) > 1.64 else ""
        effects[dim] = {"diff": diff, "t": t, "n_pre": n1, "n_post": n2}
        row.append(f"{diff:+.2f}{mark}")
    event_effects[event_name] = effects
    print(f"{event_name:<15} | " + " | ".join(f"{x:>8}" for x in row))

print("\n标记说明: ★ |t| > 1.64 (p < .10), ★★ |t| > 1.96 (p < .05), ★★★ |t| > 2.58 (p < .01)")

# ============================================================================
# 保存
# ============================================================================
out_scores = ROOT / "data" / "analysis" / "personality_scores.json"
with out_scores.open("w", encoding="utf-8") as f:
    json.dump({
        "period_summary":  period_summary,
        "event_effects":   event_effects,
        "n_total":         len(records),
    }, f, ensure_ascii=False, indent=2)

# 每条得分单独保存, 供后续画图
out_entry = ROOT / "data" / "analysis" / "personality_per_entry.jsonl"
with out_entry.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps({
            "id":           r["id"],
            "item_no":      r["item_no"],
            "time_period":  r["time_period"],
            "chapter":      r["chapter"],
            "char_count":   r["char_count"],
            "scores":       r["scores"],
        }, ensure_ascii=False) + "\n")

print(f"\n输出: {out_scores}")
print(f"      {out_entry}")
