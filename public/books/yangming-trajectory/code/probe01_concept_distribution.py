"""探针实验 Step 1: 计算每个时段在 51 个概念上的频率分布.

输出:
  data/analysis/concept_freq_per_period.json
  data/analysis/concept_freq_matrix.csv  (51 x 6 + meta cols)
"""
import json
from pathlib import Path
from collections import defaultdict

from concept_vocabulary import CONCEPTS

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]

PERIODS = ["T1", "T2", "T3", "T4", "T5", "T6"]

# 聚合各时段的总字数 + 每个概念出现次数
period_stats = {p: {"chars": 0, "counts": defaultdict(int), "n_entries": 0}
                for p in PERIODS}

for r in records:
    p = r["time_period"]
    period_stats[p]["chars"]     += r["char_count"]
    period_stats[p]["n_entries"] += 1
    for concept, _ in CONCEPTS:
        c = r["text"].count(concept)
        if c > 0:
            period_stats[p]["counts"][concept] += c

# 计算"每千字频率"
result = {}
for p in PERIODS:
    chars = period_stats[p]["chars"]
    freqs = {}
    for concept, cat in CONCEPTS:
        cnt = period_stats[p]["counts"].get(concept, 0)
        freqs[concept] = {
            "count": cnt,
            "per_kc": (cnt / chars * 1000) if chars > 0 else 0.0,  # 每千字
            "category": cat,
        }
    result[p] = {
        "total_chars":   chars,
        "n_entries":     period_stats[p]["n_entries"],
        "concept_freqs": freqs,
    }

# 保存 JSON
out_json = ROOT / "data" / "analysis" / "concept_freq_per_period.json"
with out_json.open("w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 保存 CSV (方便查表)
out_csv = ROOT / "data" / "analysis" / "concept_freq_matrix.csv"
with out_csv.open("w", encoding="utf-8") as f:
    f.write("concept,category," + ",".join(f"{p}_count" for p in PERIODS) + ","
            + ",".join(f"{p}_per_kc" for p in PERIODS) + "\n")
    for concept, cat in CONCEPTS:
        cnts  = [result[p]["concept_freqs"][concept]["count"]  for p in PERIODS]
        freqs = [result[p]["concept_freqs"][concept]["per_kc"] for p in PERIODS]
        f.write(f"{concept},{cat}," + ",".join(str(c) for c in cnts) + ","
                + ",".join(f"{x:.4f}" for x in freqs) + "\n")

# 打印总览
print("=== 各时段总字数 / 条数 ===")
for p in PERIODS:
    print(f"  {p}: {period_stats[p]['chars']:>6,} 字 / {period_stats[p]['n_entries']:>3} 条")

print(f"\n输出: {out_json}")
print(f"      {out_csv}")
