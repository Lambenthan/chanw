"""探针实验 Step 3: 同时段内部基线散度

问题: T3→T4 的 L1=0.0685 是大还是小?
我们需要一个 baseline: 把同一个时段内部的条目随机分成两半, 算这两半之间的散度.
这个 baseline 表示"没有任何思想漂移时, 仅由抽样波动造成的最大散度".

把每个时段做 100 次随机切分, 取平均与 95% 上界, 和实际的 5 个过渡散度对比.

如果某个过渡的散度 > 内部基线的 95% 上界, 说明这个过渡是统计意义上的"真跳跃",
不是抽样波动.
"""
import json
import math
from pathlib import Path

import numpy as np

from concept_vocabulary import CONCEPTS

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]

CONCEPT_TERMS = [c for c, _ in CONCEPTS]
PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]


def build_distribution_from_records(recs):
    if not recs:
        return None
    total_chars = sum(r["char_count"] for r in recs)
    if total_chars == 0:
        return None
    counts = np.zeros(len(CONCEPT_TERMS))
    for r in recs:
        for i, c in enumerate(CONCEPT_TERMS):
            counts[i] += r["text"].count(c)
    concept_chars = counts * np.array([len(c) for c in CONCEPT_TERMS])
    other = max(total_chars - concept_chars.sum(), 1.0)
    vec = np.concatenate([concept_chars, [other]])
    return vec / vec.sum()


def kl(p, q, base=2):
    eps = 1e-12
    q = np.where(q < eps, eps, q)
    mask = p > 0
    return float(np.sum(p[mask] * np.log(p[mask] / q[mask])) / math.log(base))


def js(p, q):
    m = 0.5 * (p + q)
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def l1(p, q):
    return float(np.abs(p - q).sum())


RNG = np.random.default_rng(2026)
N_REPEAT = 200

baselines = {}
for p in PERIODS:
    recs = [r for r in records if r["time_period"] == p]
    if len(recs) < 4:
        baselines[p] = {"n_entries": len(recs), "note": "条目太少, 跳过"}
        continue

    l1_samples = []
    js_samples = []
    for _ in range(N_REPEAT):
        idx = RNG.permutation(len(recs))
        half = len(recs) // 2
        a = [recs[i] for i in idx[:half]]
        b = [recs[i] for i in idx[half:]]
        pa = build_distribution_from_records(a)
        pb = build_distribution_from_records(b)
        if pa is None or pb is None:
            continue
        l1_samples.append(l1(pa, pb))
        js_samples.append(js(pa, pb))

    l1_arr = np.array(l1_samples)
    js_arr = np.array(js_samples)
    baselines[p] = {
        "n_entries":   len(recs),
        "L1_mean":     float(l1_arr.mean()),
        "L1_p95":      float(np.percentile(l1_arr, 95)),
        "L1_p99":      float(np.percentile(l1_arr, 99)),
        "JS_mean":     float(js_arr.mean()),
        "JS_p95":      float(np.percentile(js_arr, 95)),
        "JS_p99":      float(np.percentile(js_arr, 99)),
    }

# 加载实际过渡散度
trans = json.loads((ROOT / "data" / "analysis" / "probe_divergence.json").read_text(encoding="utf-8"))

# 打印对照: 每个过渡 vs 两端时段内部基线
print("=" * 88)
print(f"{'过渡':<10} {'L1 实际':>9} {'L1 baseline 95%':>20} {'L1 baseline 99%':>20} {'是否显著':>10}")
print("=" * 88)
for t in trans:
    src, dst = t["from"], t["to"]
    bsrc = baselines[src]
    bdst = baselines[dst]
    # 用两端 baseline 的最大值作为对比基线
    bl_95 = max(bsrc["L1_p95"], bdst["L1_p95"])
    bl_99 = max(bsrc["L1_p99"], bdst["L1_p99"])
    sig = "★★★" if t["L1"] > bl_99 else "★★" if t["L1"] > bl_95 else "—"
    print(f"{src} → {dst}    {t['L1']:>9.4f}  "
          f"  {bl_95:>14.4f}    {bl_99:>14.4f}      {sig}")

print(f"\n说明: ★★ 显著高于内部基线 95% 上界 (p<.05), ★★★ 显著高于 99% 上界 (p<.01)")
print(f"      内部基线 = 同一时段内随机切两半重复 {N_REPEAT} 次的 L1 分布的分位数")

# 保存
out = ROOT / "data" / "analysis" / "probe_baselines.json"
out.write_text(json.dumps({"baselines": baselines, "n_repeat": N_REPEAT},
                          ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")

# 同时打印每个时段的 baseline 详细数值
print(f"\n=== 各时段内部基线 (随机切两半 {N_REPEAT} 次) ===")
print(f"{'时段':<6} {'条目':>5} {'L1 均值':>10} {'L1 95%':>10} {'L1 99%':>10}")
for p in PERIODS:
    b = baselines[p]
    if "L1_mean" in b:
        print(f"{p:<6} {b['n_entries']:>5} {b['L1_mean']:>10.4f} "
              f"{b['L1_p95']:>10.4f} {b['L1_p99']:>10.4f}")
    else:
        print(f"{p:<6} {b['n_entries']:>5}    (条目太少)")
