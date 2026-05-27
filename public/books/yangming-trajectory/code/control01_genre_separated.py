"""控制 1: 体裁分离的鲁棒性检验

担心: 1520-1522 断点聚类可能由"卷中书信体进入语料"造成的,
      不是真的思想转向. 因为体裁本身就会带来词汇分布的剧变.

控制方式: 只保留语录体条目 (徐爱/陆澄/薛侃/陈九川/黄直/黄修易/黄省曾/黄以方)
          排除卷中所有书信 + 训蒙大意 + 教约
          重新跑断点检测

如果 1520-1522 聚类仍然存在 → 转折是真的, 不是体裁效应
如果 1520-1522 聚类消失   → 之前的发现部分由体裁混淆造成
"""
import json
import csv
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
import ruptures as rpt

from concept_vocabulary import CONCEPT_TERMS

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in
           (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]

# 语录体章节 (排除卷中所有 + 排除卷上的"训蒙大意/教约" 实际它们在卷中)
DIALOGUE_CHAPTERS = {
    "徐爱录", "陆澄录", "薛侃录",
    "陈九川录", "黄直录", "黄修易录", "黄省曾录", "黄以方录",
}

# 章节中位年份 (沿用 probe05)
CHAPTER_MID_YEAR = {
    "徐爱录": 1515, "陆澄录": 1518, "薛侃录": 1521,
    "陈九川录": 1520, "黄直录": 1526, "黄修易录": 1526,
    "黄省曾录": 1524, "黄以方录": 1527,
}

# 过滤
dialogue_records = [r for r in records if r["chapter"] in DIALOGUE_CHAPTERS]
print(f"原 343 条 → 语录体 {len(dialogue_records)} 条")
print(f"  (排除卷中 70 条书信 + 教约 + 训蒙大意 = 排除 70 条, 保留 273 条)")
print()

# 按年聚合
by_year = defaultdict(lambda: {"chars": 0, "n": 0, "counts": defaultdict(int)})
for r in dialogue_records:
    y = CHAPTER_MID_YEAR[r["chapter"]]
    by_year[y]["chars"] += r["char_count"]
    by_year[y]["n"]     += 1
    for c in CONCEPT_TERMS:
        by_year[y]["counts"][c] += r["text"].count(c)

years = sorted(by_year.keys())
print(f"语录体覆盖年份: {years}")
print(f"  ({len(years)} 个时间点)")
print()
for y in years:
    d = by_year[y]
    print(f"  {y}: {d['n']:>3} 条, {d['chars']:>6,} 字")
print()


def detect_binseg_1break(s):
    s = np.asarray(s, dtype=float).reshape(-1, 1)
    n = len(s)
    if n < 4:
        return None
    algo = rpt.Binseg(model="l2", min_size=2, jump=1).fit(s)
    try:
        breaks = algo.predict(n_bkps=1)
        for b in breaks:
            if b < n:
                return b
    except Exception:
        return None
    return None


def r_squared(s, idx):
    s = np.asarray(s, dtype=float)
    if idx is None or idx <= 0 or idx >= len(s):
        return 0.0
    tv = float(np.var(s))
    if tv < 1e-9:
        return 0.0
    n1, n2 = idx, len(s) - idx
    v1 = float(np.var(s[:idx])) if n1 > 1 else 0.0
    v2 = float(np.var(s[idx:])) if n2 > 1 else 0.0
    wv = (n1 * v1 + n2 * v2) / len(s)
    return 1 - wv / tv


# 跑同样 12 个概念
KEY_CONCEPTS = [
    "致良知", "良知", "心即理", "知行合一",
    "格物", "天理", "人欲",
    "朱子", "立志", "事上", "工夫", "用功",
]

print("=" * 78)
print("语录体单独分析 — Binary Segmentation 断点检测")
print("=" * 78)
print(f"{'概念':<8} {'断点年份':<12} {'R²':<8} {'前段':<8} {'后段':<8}")
print("-" * 78)

results = {}
break_counter = Counter()

for c in KEY_CONCEPTS:
    series = []
    for y in years:
        chars = by_year[y]["chars"]
        cnt = by_year[y]["counts"].get(c, 0)
        series.append(cnt / chars * 1000 if chars > 0 else 0)
    idx = detect_binseg_1break(series)
    if idx is None:
        print(f"{c:<8} {'(无)':<12}")
        continue
    yr = years[idx]
    r2 = r_squared(series, idx)
    pre  = float(np.mean(series[:idx]))
    post = float(np.mean(series[idx:]))
    results[c] = {"break_year": yr, "r2": r2, "pre": pre, "post": post,
                  "series": series}
    break_counter[yr] += 1
    print(f"{c:<8} {yr:<12} {r2:<8.2f} {pre:<8.2f} {post:<8.2f}")

print()
print("=== 断点位置聚合 (语录体 only) ===")
for yr, n in sorted(break_counter.items(), key=lambda x: -x[1]):
    bar = "█" * n
    print(f"  {yr}: {n} 个序列  {bar}")

# ============================================================================
# 对比: 原始(全部343条) vs 控制(语录体273条)
# ============================================================================
original = json.loads((ROOT / "data" / "analysis" / "breakpoints.json").read_text(encoding="utf-8"))
orig_results = original["results"]

print()
print("=" * 90)
print("对比: 原始 (全 343 条) vs 控制 (语录体 273 条)")
print("=" * 90)
print(f"{'概念':<8} {'原断点':<8} {'原 R²':<8} {'控制断点':<10} {'控制 R²':<8} {'断点是否变化':<10}")
print("-" * 90)
for c in KEY_CONCEPTS:
    orig = orig_results.get(c, {})
    orig_yr = orig.get("binseg_break_year")
    orig_r2 = orig.get("binseg_r2", 0)
    new = results.get(c)
    new_yr = new["break_year"] if new else None
    new_r2 = new["r2"] if new else 0
    if orig_yr is None and new_yr is None:
        change = "—"
    elif orig_yr is None or new_yr is None:
        change = "出现/消失"
    elif abs(orig_yr - new_yr) <= 1:
        change = "稳定"
    elif abs(orig_yr - new_yr) <= 2:
        change = "略偏移"
    else:
        change = "显著偏移"
    print(f"{c:<8} {str(orig_yr):<8} {orig_r2:<8.2f} {str(new_yr):<10} {new_r2:<8.2f} {change:<10}")

# 保存
out = ROOT / "data" / "analysis" / "control_genre_breakpoints.json"
out.write_text(json.dumps({
    "filter":           "dialogue_only",
    "n_entries":        len(dialogue_records),
    "years":            years,
    "results":          {c: {**r, "series": [float(x) for x in r["series"]]} for c, r in results.items()},
    "break_clustering": dict(break_counter),
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")
