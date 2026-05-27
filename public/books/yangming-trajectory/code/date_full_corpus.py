"""给 yangming_full.jsonl 的 1283 文档批量贴年份

策略 (按 confidence 从高到低):
  1. 高: date_annotation 含年号 (弘治/正德/嘉靖 X 年) 或干支 → 直接解码
  2. 中: 同一卷里前文若有年号, 本文"X 年" 接续 (上下文)
  3. 中-低: 卷次范围 → 年份范围 (用钱德洪年谱的卷次断代)

输出: data/corpus/yangming_full_dated.jsonl  增加字段 year / month / confidence / source
"""
import json
from pathlib import Path

from date_decoder import decode_annotation

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "data" / "corpus" / "yangming_full.jsonl"
dst = ROOT / "data" / "corpus" / "yangming_full_dated.jsonl"

records = [json.loads(line) for line in src.open(encoding="utf-8")]
print(f"读入 {len(records)} 文档")

# 上下文传递: 同卷里前一篇的年号
current_era = None
current_year = None
current_vol = None

dated = 0
high_conf = 0

for r in records:
    # 跨卷时重置上下文
    if r["vol_id"] != current_vol:
        current_era = None
        current_year = None
        current_vol = r["vol_id"]

    anno = r.get("date_annotation", "")
    decoded = decode_annotation(anno, prev_era=current_era)

    # 如果是 high confidence 且含年号, 记下来作下一篇的 prev_era
    if decoded["confidence"] == "high" and decoded["source"] == "era":
        # 提取实际用的年号
        for era in ["成化", "弘治", "正德", "嘉靖"]:
            if era in anno:
                current_era = era
                break

    if decoded["year"] is not None:
        current_year = decoded["year"]

    r["year"]            = decoded["year"]
    r["month"]           = decoded["month"]
    r["date_confidence"] = decoded["confidence"]
    r["date_source"]     = decoded["source"]

    if decoded["year"] is not None:
        dated += 1
    if decoded["confidence"] == "high":
        high_conf += 1

# 写
with dst.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# 报告
from collections import Counter
print()
print("=" * 60)
print("断代结果")
print("=" * 60)
print(f"  总文档:        {len(records)}")
print(f"  有年份:        {dated} ({dated/len(records)*100:.1f}%)")
print(f"  high confidence: {high_conf} ({high_conf/len(records)*100:.1f}%)")
print()

# 按 genre 看
by_genre = {}
for r in records:
    g = r.get("genre", "未知")
    by_genre.setdefault(g, {"total": 0, "dated": 0, "high": 0})
    by_genre[g]["total"] += 1
    if r["year"] is not None:
        by_genre[g]["dated"] += 1
    if r["date_confidence"] == "high":
        by_genre[g]["high"] += 1

print("按 genre 分布:")
print(f"  {'genre':<8} {'总数':>6} {'有年份':>8} {'high':>6} {'断代率':>8}")
for g, s in sorted(by_genre.items(), key=lambda x: -x[1]["total"]):
    rate = s["dated"]/s["total"]*100 if s["total"] > 0 else 0
    print(f"  {g:<8} {s['total']:>6} {s['dated']:>8} {s['high']:>6} {rate:>7.1f}%")

# 按年份分布
print()
print("按年份分布 (有年份的文档):")
year_counter = Counter(r["year"] for r in records if r["year"] is not None)
for yr in sorted(year_counter.keys()):
    n = year_counter[yr]
    bar = "█" * min(n, 50)
    print(f"  {yr}: {n:>4} {bar}")

print(f"\n输出: {dst}")
