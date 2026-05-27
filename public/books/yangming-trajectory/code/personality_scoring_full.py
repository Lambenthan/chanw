"""全集级人格评分: 给 1283 个已断代/未断代文档打 8 维分

输入: data/corpus/yangming_full_dated.jsonl
输出: data/analysis/personality_full_per_doc.jsonl
      data/analysis/personality_full_by_year.json  (按年聚合)
      data/analysis/personality_full_by_genre.json (按 genre 聚合)
"""
import json
from pathlib import Path
from collections import defaultdict

import numpy as np

from personality_markers_v2 import DIMENSIONS

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "corpus" / "yangming_full_dated.jsonl"
records = [json.loads(line) for line in src.open(encoding="utf-8")]
print(f"读入 {len(records)} 文档")


def score_text(text, pos_markers, neg_markers):
    """返回 (正向密度, 反向密度, 净分数). 每千字"""
    n = max(len(text), 1)
    p = sum(text.count(m) for m in pos_markers) / n * 1000
    g = sum(text.count(m) for m in neg_markers) / n * 1000
    return p, g, p - g


# 给每个文档打 8 维分
for r in records:
    r["scores"] = {}
    for dim, (pos, neg) in DIMENSIONS.items():
        p, n, net = score_text(r["text"], pos, neg)
        r["scores"][dim] = {"pos": p, "neg": n, "net": net}

# 保存逐文档分
out_per_doc = ROOT / "data" / "analysis" / "personality_full_per_doc.jsonl"
with out_per_doc.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps({
            "id":     r["id"],
            "vol_id": r["vol_id"],
            "genre":  r["genre"],
            "title":  r["title"],
            "year":   r["year"],
            "month":  r["month"],
            "char_count": r["char_count"],
            "scores": r["scores"],
        }, ensure_ascii=False) + "\n")

# 按年聚合 (只用 high confidence 断代的文档)
by_year = defaultdict(lambda: {dim: [] for dim in DIMENSIONS})
for r in records:
    if r["year"] is None or r["date_confidence"] != "high":
        continue
    if r["char_count"] < 50:  # 太短的文档跳过 (避免噪声)
        continue
    for dim in DIMENSIONS:
        by_year[r["year"]][dim].append(r["scores"][dim]["net"])

year_summary = {}
for y, dims in by_year.items():
    year_summary[str(y)] = {}
    for dim in DIMENSIONS:
        vals = dims[dim]
        if vals:
            year_summary[str(y)][dim] = {
                "mean": float(np.mean(vals)),
                "se":   float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0,
                "n":    len(vals),
            }

out_by_year = ROOT / "data" / "analysis" / "personality_full_by_year.json"
with out_by_year.open("w", encoding="utf-8") as f:
    json.dump(year_summary, f, ensure_ascii=False, indent=2)

# 按 genre 聚合
by_genre = defaultdict(lambda: {dim: [] for dim in DIMENSIONS})
for r in records:
    if r["char_count"] < 50:
        continue
    g = r["genre"]
    for dim in DIMENSIONS:
        by_genre[g][dim].append(r["scores"][dim]["net"])

genre_summary = {}
for g, dims in by_genre.items():
    genre_summary[g] = {}
    for dim in DIMENSIONS:
        vals = dims[dim]
        if vals:
            genre_summary[g][dim] = {
                "mean": float(np.mean(vals)),
                "se":   float(np.std(vals, ddof=1) / np.sqrt(len(vals))) if len(vals) > 1 else 0.0,
                "n":    len(vals),
            }

out_by_genre = ROOT / "data" / "analysis" / "personality_full_by_genre.json"
with out_by_genre.open("w", encoding="utf-8") as f:
    json.dump(genre_summary, f, ensure_ascii=False, indent=2)


# ============================================================================
# 打印关键发现
# ============================================================================
print("\n" + "=" * 80)
print("8 维度按 genre 平均分 (重点看新增 3 维)")
print("=" * 80)
genres = ["奏疏", "公移", "文录", "续编", "语录", "外集"]
dims_to_show = list(DIMENSIONS.keys())
print(f"{'genre':<8} | " + " | ".join(f"{d:>8}" for d in dims_to_show))
print("-" * 100)
for g in genres:
    if g not in genre_summary:
        continue
    row = []
    for d in dims_to_show:
        v = genre_summary[g].get(d, {}).get("mean")
        row.append(f"{v:>8.2f}" if v is not None else "    —   ")
    n = sum(genre_summary[g].get(d, {}).get("n", 0) for d in dims_to_show[:1])
    print(f"{g:<8} | " + " | ".join(row))

print("\n注: 数字 = 每千字净分 (正向密度 - 反向密度)")

print("\n" + "=" * 80)
print(f"年份覆盖: {len(year_summary)} 年 (1496-1528 之间)")
print("=" * 80)
years_sorted = sorted(int(y) for y in year_summary.keys())
print(f"  最早: {min(years_sorted)}  最晚: {max(years_sorted)}")
print(f"  共: {years_sorted}")

print(f"\n输出:")
print(f"  {out_per_doc}")
print(f"  {out_by_year}")
print(f"  {out_by_genre}")
