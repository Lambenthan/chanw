"""断点检测主程序 (修订版)

两种方法并跑:
  方法 1: PELT + 标准 BIC 罚项 (让数据决定有几个断点)
  方法 2: Binary Segmentation 强制找 1 个最优断点 (即使弱也告诉位置)

时间序列只有 9 个年份点, 是小样本探索性分析.
"""
import json
import csv
from pathlib import Path
from collections import Counter

import numpy as np
import ruptures as rpt

from concept_vocabulary import CONCEPT_TERMS
from personality_markers import DIMENSIONS

ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# 读概念时间序列
# ============================================================================
years, chars, freq_by_concept = [], [], {c: [] for c in CONCEPT_TERMS}
with (ROOT / "data" / "analysis" / "chapter_timeline.csv").open(encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        years.append(int(row["year"]))
        chars.append(int(row["chars"]))
        for c in CONCEPT_TERMS:
            freq_by_concept[c].append(float(row[c]))
years_arr = np.array(years)

# 人格维度时间序列
import json as _json
entry_scores = [_json.loads(line) for line in
                (ROOT / "data" / "analysis" / "personality_per_entry.jsonl").open(encoding="utf-8")]
CHAPTER_MID_YEAR = {
    "徐爱录": 1515, "陆澄录": 1518, "薛侃录": 1521,
    "答顾东桥书": 1525, "答周道通书": 1525,
    "答陆原静书": 1522, "又(答陆原静)": 1522,
    "答欧阳崇一": 1524, "答罗整庵少宰书": 1525,
    "答聂文蔚一": 1526, "答聂文蔚二": 1527,
    "训蒙大意示教读刘伯颂等": 1518, "教约": 1518,
    "陈九川录": 1520, "黄直录": 1526, "黄修易录": 1526,
    "黄省曾录": 1524, "黄以方录": 1527,
}
for e in entry_scores:
    e["mid_year"] = CHAPTER_MID_YEAR[e["chapter"]]

dim_series = {}
for dim in DIMENSIONS:
    by_y = {}
    for e in entry_scores:
        by_y.setdefault(e["mid_year"], []).append(e["scores"][dim]["net"])
    series_y = sorted(by_y.keys())
    series_v = [float(np.mean(by_y[y])) for y in series_y]
    dim_series[dim] = (series_y, series_v)


# ============================================================================
# 两种检测方法
# ============================================================================
def detect_pelt(series, multiplier=1.0):
    """PELT + BIC, multiplier 控制罚项严厉度. multiplier=1 是标准 BIC."""
    series = np.asarray(series, dtype=float).reshape(-1, 1)
    n = len(series)
    sigma_sq = max(float(np.var(series)), 1e-6)
    pen = multiplier * np.log(n) * sigma_sq
    algo = rpt.Pelt(model="l2", min_size=2, jump=1).fit(series)
    breaks = algo.predict(pen=pen)
    return [b for b in breaks if b < n]


def detect_binseg_1break(series):
    """Binary Segmentation 强制找 1 个断点的位置 (即使弱也报告). 返回 index."""
    series = np.asarray(series, dtype=float).reshape(-1, 1)
    n = len(series)
    if n < 4:
        return None
    algo = rpt.Binseg(model="l2", min_size=2, jump=1).fit(series)
    try:
        breaks = algo.predict(n_bkps=1)
        for b in breaks:
            if b < n:
                return b
    except Exception:
        return None
    return None


def reduction_in_variance(series, break_idx):
    """衡量这个断点的解释力: 1 - (within_seg_var / total_var)
    数值越接近 1, 断点越显著."""
    s = np.asarray(series, dtype=float)
    if break_idx is None or break_idx <= 0 or break_idx >= len(s):
        return 0.0
    total_var = float(np.var(s))
    if total_var < 1e-9:
        return 0.0
    n1, n2 = break_idx, len(s) - break_idx
    v1 = float(np.var(s[:break_idx])) if n1 > 1 else 0.0
    v2 = float(np.var(s[break_idx:])) if n2 > 1 else 0.0
    within_var = (n1 * v1 + n2 * v2) / len(s)
    return 1 - within_var / total_var


# ============================================================================
# 跑所有序列
# ============================================================================
KEY_CONCEPTS = [
    "致良知", "良知", "心即理", "知行合一",
    "格物", "天理", "人欲",
    "朱子", "立志", "事上", "工夫", "用功",
]

results = {}

print("=" * 90)
print("方法 1: PELT (BIC 标准罚项)  |  方法 2: BinSeg 强制找 1 个断点 (+ 方差减少量 R²)")
print("=" * 90)
print(f"{'序列':<10} {'PELT 断点(年)':<20} {'BinSeg 断点(年)':<15} {'R²':<6} {'前段':<8} {'后段':<8}")
print("-" * 90)

# 概念
for concept in KEY_CONCEPTS:
    s = freq_by_concept[concept]
    # PELT
    pelt_idx = detect_pelt(s, multiplier=1.0)
    pelt_years = [int(years_arr[i]) for i in pelt_idx]
    # Binseg 强制 1 个断点
    bin_idx = detect_binseg_1break(s)
    bin_year = int(years_arr[bin_idx]) if bin_idx is not None else None
    r2 = reduction_in_variance(s, bin_idx)
    # 前后段均值
    if bin_idx is not None:
        pre_mean = float(np.mean(s[:bin_idx]))
        post_mean = float(np.mean(s[bin_idx:]))
    else:
        pre_mean = post_mean = float(np.mean(s))

    results[concept] = {
        "type": "concept",
        "series": s, "years": list(years_arr),
        "pelt_break_years": pelt_years,
        "binseg_break_year": bin_year,
        "binseg_r2": r2,
        "pre_mean": pre_mean, "post_mean": post_mean,
    }
    pelt_str = ", ".join(str(y) for y in pelt_years) if pelt_years else "(无)"
    bin_str  = str(bin_year) if bin_year else "(无)"
    print(f"{concept:<10} {pelt_str:<20} {bin_str:<15} {r2:.2f}   "
          f"{pre_mean:>6.2f}   {post_mean:>6.2f}")

print()
# 人格维度
for dim in DIMENSIONS:
    yrs, s = dim_series[dim]
    pelt_idx = detect_pelt(s, multiplier=1.0)
    pelt_years = [yrs[i] for i in pelt_idx]
    bin_idx = detect_binseg_1break(s)
    bin_year = yrs[bin_idx] if bin_idx is not None else None
    r2 = reduction_in_variance(s, bin_idx)
    if bin_idx is not None:
        pre_mean = float(np.mean(s[:bin_idx]))
        post_mean = float(np.mean(s[bin_idx:]))
    else:
        pre_mean = post_mean = float(np.mean(s))

    results[f"DIM_{dim}"] = {
        "type": "personality",
        "series": s, "years": yrs,
        "pelt_break_years": pelt_years,
        "binseg_break_year": bin_year,
        "binseg_r2": r2,
        "pre_mean": pre_mean, "post_mean": post_mean,
    }
    pelt_str = ", ".join(str(y) for y in pelt_years) if pelt_years else "(无)"
    bin_str  = str(bin_year) if bin_year else "(无)"
    print(f"{dim:<10} {pelt_str:<20} {bin_str:<15} {r2:.2f}   "
          f"{pre_mean:>6.2f}   {post_mean:>6.2f}")

# ============================================================================
# 断点聚合: 看哪个年份被多个序列同时识别为最优单断点
# ============================================================================
binseg_years = [r["binseg_break_year"] for r in results.values() if r["binseg_break_year"]]
counter = Counter(binseg_years)

print()
print("=" * 90)
print("BinSeg 单断点聚合: 哪个年份被最多序列认作最优断点")
print("=" * 90)
print(f"  (共 {len(binseg_years)} 个序列检出断点, 总共 {len(results)} 个序列)\n")
for yr, n in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
    bar = "█" * n
    print(f"  {yr}: {n:>2} 个序列  {bar}")

# ============================================================================
# 高解释力序列 (R² > 0.3) 的断点位置
# ============================================================================
strong_breaks = [(k, r["binseg_break_year"], r["binseg_r2"])
                 for k, r in results.items()
                 if r["binseg_break_year"] and r["binseg_r2"] > 0.3]

print(f"\n=== 强信号断点 (R² > 0.3): 共 {len(strong_breaks)} 个 ===")
for k, y, r in sorted(strong_breaks, key=lambda x: -x[2]):
    print(f"  {k:<20}  断点 = {y}  R² = {r:.2f}")

# 保存
out = ROOT / "data" / "analysis" / "breakpoints.json"
results_clean = {}
for k, v in results.items():
    results_clean[k] = {
        "type":              v["type"],
        "series":            [float(x) for x in v["series"]],
        "years":             [int(x) for x in v["years"]],
        "pelt_break_years":  [int(x) for x in v["pelt_break_years"]],
        "binseg_break_year": int(v["binseg_break_year"]) if v["binseg_break_year"] else None,
        "binseg_r2":         v["binseg_r2"],
        "pre_mean":          v["pre_mean"],
        "post_mean":         v["post_mean"],
    }
with out.open("w", encoding="utf-8") as f:
    json.dump({
        "results":          results_clean,
        "binseg_clustering": dict(counter),
    }, f, ensure_ascii=False, indent=2)

print(f"\n输出: {out}")
