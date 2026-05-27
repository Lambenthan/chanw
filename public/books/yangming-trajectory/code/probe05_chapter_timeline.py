"""把 343 条按章节聚合成时间序列, 给断点检测用.

每个章节有一个估计的中位年份 (基于学界共识的年份范围).
同年份多个章节合并.

输出: data/analysis/chapter_timeline.csv  (一列年份 + 多列概念频率)
"""
import json
from pathlib import Path
from collections import defaultdict

import numpy as np

from concept_vocabulary import CONCEPT_TERMS

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]

# 章节中位年份 (基于 enrich_time_periods 里的 year_range)
CHAPTER_MID_YEAR = {
    "徐爱录":               1515,   # 1512-1517
    "陆澄录":               1518,   # 1515-1521
    "薛侃录":               1521,   # 1519-1522 ↓后半段, 阳明开始讲致良知前夜
    "答顾东桥书":           1525,   # 1525 嘉靖四年明确
    "答周道通书":           1525,   # 1525-1526
    "答陆原静书":           1522,   # 1521-1522 嘉靖元年明确
    "又(答陆原静)":         1522,   # 1521-1523
    "答欧阳崇一":           1524,   # 1524 明确
    "答罗整庵少宰书":       1525,   # 1525 明确
    "答聂文蔚一":           1526,   # 嘉靖五年
    "答聂文蔚二":           1527,   # 嘉靖六年
    "训蒙大意示教读刘伯颂等": 1518,   # 1518 赣州时期
    "教约":                 1518,   # 1518 赣州时期
    "陈九川录":             1520,   # 1515-1525 取中位
    "黄直录":               1526,   # 1524-1528 取中位
    "黄修易录":             1526,   # 1524-1528 取中位
    "黄省曾录":             1524,   # 1521-1528 取中位
    "黄以方录":             1527,   # 1526-1528 取中位
}

# 给每条贴章节中位年份
for r in records:
    if r["chapter"] not in CHAPTER_MID_YEAR:
        raise ValueError(f"未映射章节: {r['chapter']}")
    r["chapter_mid_year"] = CHAPTER_MID_YEAR[r["chapter"]]

# 按年份聚合: 同年所有条目的总字数 + 各概念出现总次数
by_year = defaultdict(lambda: {"chars": 0, "n_entries": 0,
                               "counts": defaultdict(int)})
for r in records:
    y = r["chapter_mid_year"]
    by_year[y]["chars"]     += r["char_count"]
    by_year[y]["n_entries"] += 1
    for c in CONCEPT_TERMS:
        n = r["text"].count(c)
        if n > 0:
            by_year[y]["counts"][c] += n

# 排序的年份列表
years = sorted(by_year.keys())
print(f"覆盖年份: {years}")
print(f"共 {len(years)} 个时间点")
print()
print(f"{'年份':>4} | {'条目':>4} | {'字数':>6}")
print("-" * 25)
for y in years:
    d = by_year[y]
    print(f"{y:>4} | {d['n_entries']:>4} | {d['chars']:>6,}")

# 生成 CSV: 一列 year, 一列 chars, 一列 n_entries, 然后每个概念一列 (per kc)
out_csv = ROOT / "data" / "analysis" / "chapter_timeline.csv"
with out_csv.open("w", encoding="utf-8") as f:
    header = ["year", "chars", "n_entries"] + [c for c in CONCEPT_TERMS]
    f.write(",".join(header) + "\n")
    for y in years:
        d = by_year[y]
        row = [str(y), str(d["chars"]), str(d["n_entries"])]
        for c in CONCEPT_TERMS:
            cnt = d["counts"].get(c, 0)
            per_kc = cnt / d["chars"] * 1000 if d["chars"] > 0 else 0
            row.append(f"{per_kc:.4f}")
        f.write(",".join(row) + "\n")

# 同时存 JSON, 方便后续脚本读
out_json = ROOT / "data" / "analysis" / "chapter_timeline.json"
with out_json.open("w", encoding="utf-8") as f:
    json.dump({
        "years":     years,
        "by_year":   {str(y): dict(d) for y, d in by_year.items()},
        "chapter_mid_year": CHAPTER_MID_YEAR,
    }, f, ensure_ascii=False, indent=2, default=lambda x: dict(x) if isinstance(x, defaultdict) else x)

print(f"\n输出: {out_csv}")
print(f"      {out_json}")
