"""探针实验 Step 2: 计算相邻时段的概念分布散度.

核心思想:
  如果阳明思想是"连续渐变"的, 那 T_i 和 T_{i+1} 的概念分布应该高度相似 → 散度小.
  如果某个 T_i → T_{i+1} 出现"思想跳跃", 散度会显著高于其他过渡.

三个互补的指标:
  1. L1 距离 (即 2 倍 Total Variation Distance)
       L1 = sum_c |p_i(c) - p_{i+1}(c)|
     直观, 不需要平滑, 对零概率友好.
  2. Jensen-Shannon Divergence
       JS = 0.5 * KL(p || m) + 0.5 * KL(q || m), m = 0.5*(p+q)
     对称、有界 [0, 1] (用 log_2), 比 KL 数值更稳定.
  3. New / Retired Concepts
       New:     在 T_{i+1} 中频率 > threshold, 但在 T_i 中 < eps
       Retired: 反过来
     这俩数值有明确的语义解读: 真正"出现 / 消失"了几个概念.

输出:
  data/analysis/probe_divergence.json
  data/analysis/probe_new_retired.json
"""
import json
import math
from pathlib import Path
from collections import defaultdict

import numpy as np

from concept_vocabulary import CONCEPTS

ROOT = Path(__file__).resolve().parent.parent
freq = json.loads((ROOT / "data" / "analysis" / "concept_freq_per_period.json").read_text(encoding="utf-8"))
PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]
TRANSITIONS = [(PERIODS[i], PERIODS[i+1]) for i in range(len(PERIODS) - 1)]

CONCEPT_TERMS = [c for c, _ in CONCEPTS]

# 阈值
NEW_THRESHOLD     = 0.5   # 每千字 > 0.5 才算"显著出现"
RETIRED_THRESHOLD = 0.5   # 同上
EPS_ZERO          = 0.1   # 每千字 < 0.1 视为"近似不存在"


def build_distribution(period_code):
    """把一个时段的概念频率归一化成概率分布 (over 概念集合 + '其他').

    '其他'吸收所有非概念字符, 防止全为零的情况.
    """
    period_data = freq[period_code]
    total_chars = period_data["total_chars"]
    counts = np.array([period_data["concept_freqs"][c]["count"] for c in CONCEPT_TERMS], dtype=float)
    # '其他' = 该时段总字数 - 所有概念出现的总字数 (用字数, 不是次数)
    # 用次数近似归一化也可以, 这里用字数级别让总和稳定.
    concept_chars = sum(counts[i] * len(CONCEPT_TERMS[i]) for i in range(len(CONCEPT_TERMS)))
    other_chars = max(total_chars - concept_chars, 1.0)
    # 拼接: 51 个概念 + 1 个 '其他'
    vec = np.concatenate([counts * np.array([len(c) for c in CONCEPT_TERMS]),
                          [other_chars]])
    return vec / vec.sum()


def kl_divergence(p, q, base=2):
    """KL(p || q), 跳过 p_i = 0 的项, q_i = 0 的项加 tiny epsilon 防爆炸."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    eps = 1e-12
    q = np.where(q < eps, eps, q)
    mask = p > 0
    return float(np.sum(p[mask] * np.log(p[mask] / q[mask])) / math.log(base))


def js_divergence(p, q, base=2):
    """对称的 Jensen-Shannon, 用 log_2 时上界 1.0."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    m = 0.5 * (p + q)
    return 0.5 * kl_divergence(p, m, base) + 0.5 * kl_divergence(q, m, base)


def l1_distance(p, q):
    return float(np.abs(np.asarray(p) - np.asarray(q)).sum())


# 主循环
results = []
for src, dst in TRANSITIONS:
    p = build_distribution(src)
    q = build_distribution(dst)
    results.append({
        "from":           src,
        "to":             dst,
        "L1":             l1_distance(p, q),
        "JS":             js_divergence(p, q),
        "KL_forward":     kl_divergence(p, q),
        "KL_backward":    kl_divergence(q, p),
    })

# New / Retired 概念检测
new_retired = []
for src, dst in TRANSITIONS:
    new_concepts = []
    retired_concepts = []
    src_freqs = freq[src]["concept_freqs"]
    dst_freqs = freq[dst]["concept_freqs"]
    for c in CONCEPT_TERMS:
        src_kc = src_freqs[c]["per_kc"]
        dst_kc = dst_freqs[c]["per_kc"]
        if src_kc < EPS_ZERO and dst_kc >= NEW_THRESHOLD:
            new_concepts.append({"concept": c, "src_per_kc": src_kc, "dst_per_kc": dst_kc,
                                 "category": dst_freqs[c]["category"]})
        if src_kc >= RETIRED_THRESHOLD and dst_kc < EPS_ZERO:
            retired_concepts.append({"concept": c, "src_per_kc": src_kc, "dst_per_kc": dst_kc,
                                     "category": src_freqs[c]["category"]})
    new_retired.append({
        "from":     src,
        "to":       dst,
        "new":      sorted(new_concepts,     key=lambda x: -x["dst_per_kc"]),
        "retired":  sorted(retired_concepts, key=lambda x: -x["src_per_kc"]),
        "new_count":     len(new_concepts),
        "retired_count": len(retired_concepts),
    })

# 保存
out_div = ROOT / "data" / "analysis" / "probe_divergence.json"
with out_div.open("w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

out_nr = ROOT / "data" / "analysis" / "probe_new_retired.json"
with out_nr.open("w", encoding="utf-8") as f:
    json.dump(new_retired, f, ensure_ascii=False, indent=2)

# 打印结果
print("=" * 70)
print("时段过渡散度 (Divergence between adjacent periods)")
print("=" * 70)
print(f"{'过渡':<10} {'L1':>8} {'JS (log2)':>12} {'新现概念':>10} {'退场概念':>10}")
print("-" * 70)
for div, nr in zip(results, new_retired):
    print(f"{div['from']} → {div['to']}    {div['L1']:>8.4f}  {div['JS']:>10.4f}   "
          f"  {nr['new_count']:>4}        {nr['retired_count']:>4}")

print("\n=== 新现概念 (T_{i+1} 才显著出现的概念) ===")
for nr in new_retired:
    if nr["new"]:
        print(f"\n{nr['from']} → {nr['to']}:")
        for c in nr["new"]:
            print(f"  + {c['concept']:<10} ({c['category']:<8}) "
                  f"{c['src_per_kc']:>5.2f} → {c['dst_per_kc']:>5.2f} /千字")

print("\n=== 退场概念 (T_i 显著出现但 T_{i+1} 几近消失) ===")
for nr in new_retired:
    if nr["retired"]:
        print(f"\n{nr['from']} → {nr['to']}:")
        for c in nr["retired"]:
            print(f"  - {c['concept']:<10} ({c['category']:<8}) "
                  f"{c['src_per_kc']:>5.2f} → {c['dst_per_kc']:>5.2f} /千字")

print(f"\n输出: {out_div}")
print(f"      {out_nr}")
