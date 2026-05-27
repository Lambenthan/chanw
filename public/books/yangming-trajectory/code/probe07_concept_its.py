"""探针实验: ITS (中断时间序列) on 12 个核心概念

对每个 (事件, 概念) 组合, 做简化 ITS:
  outcome = concept 每千字频率
  pre-period: 事件年份之前的所有 chapter-mid-year 数据
  post-period: 事件年份之后
  在 pre-period 上拟合线性趋势 (intercept + slope), 外推到 post-period
  比较实际 vs 反事实

简化版没做 Newey-West HAC SE (因为只 9 个点), 用 Welch t-test 当 sanity check.
"""
import json
import csv
from pathlib import Path
from collections import defaultdict

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

# 读 chapter timeline
years, chars = [], []
freq = {}
with (ROOT / "data" / "analysis" / "chapter_timeline.csv").open(encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        years.append(int(row["year"]))
        chars.append(int(row["chars"]))
        for c, v in row.items():
            if c in ("year", "chars", "n_entries"):
                continue
            freq.setdefault(c, []).append(float(v))
years = np.array(years)

EVENTS = [(1517, "徐爱卒"), (1519, "宁王之乱"), (1521, "致良知"), (1522, "父王华卒")]
KEY_CONCEPTS = [
    "致良知", "良知", "心即理", "知行合一",
    "格物", "天理", "人欲",
    "朱子", "立志", "事上", "工夫", "用功",
]


def its_simple(yrs, vals, event_year, min_pre=2, min_post=2):
    """简易 ITS:
      1. 在 yrs < event_year 上拟合 OLS (alpha + beta*year)
      2. 外推到 yrs >= event_year 得到反事实
      3. effect = mean(actual_post) - mean(predicted_post)
      4. Welch t 检验 实际 post 与反事实 post 的均值差
    """
    yrs = np.asarray(yrs); vals = np.asarray(vals)
    pre_mask = yrs < event_year
    post_mask = yrs >= event_year
    pre_y, pre_v = yrs[pre_mask], vals[pre_mask]
    post_y, post_v = yrs[post_mask], vals[post_mask]
    if len(pre_y) < min_pre or len(post_y) < min_post:
        return None

    # OLS on pre
    A = np.column_stack([np.ones_like(pre_y), pre_y - event_year])
    try:
        beta = np.linalg.lstsq(A, pre_v, rcond=None)[0]
    except Exception:
        return None
    alpha, slope = float(beta[0]), float(beta[1])

    # Counterfactual on post
    cf_post = alpha + slope * (post_y - event_year)
    actual_post_mean = float(np.mean(post_v))
    cf_post_mean = float(np.mean(cf_post))
    effect = actual_post_mean - cf_post_mean

    # 简易 SE: 用 pre 残差方差 + post 实际方差合并估计
    pre_resid = pre_v - (alpha + slope * (pre_y - event_year))
    pre_var = float(np.var(pre_resid, ddof=1)) if len(pre_resid) > 1 else 0
    post_var = float(np.var(post_v, ddof=1)) if len(post_v) > 1 else 0
    n1, n2 = len(pre_y), len(post_y)
    se = (pre_var/n1 + post_var/n2) ** 0.5 if (pre_var + post_var) > 0 else 1e-9
    t = effect / se if se > 1e-9 else 0
    return {
        "event_year":      event_year,
        "n_pre":           n1,
        "n_post":          n2,
        "pre_alpha":       alpha,
        "pre_slope":       slope,
        "actual_post":     actual_post_mean,
        "cf_post":         cf_post_mean,
        "effect":          effect,
        "se":              se,
        "t":               t,
        "actual_post_vals": [float(v) for v in post_v],
        "cf_post_vals":     [float(v) for v in cf_post],
        "post_years":       [int(y) for y in post_y],
    }


# 跑全部 (concept, event) 组合
results = {}
print("=" * 95)
print("ITS 概念频率: 每个 (概念, 事件) 组合的反事实偏离估计")
print("=" * 95)
print(f"{'概念':<7} | " + " | ".join(f"{ev[1]+'('+str(ev[0])+')':<14}" for ev in EVENTS))
print("-" * 95)

for c in KEY_CONCEPTS:
    vals = freq[c]
    row = []
    results[c] = {}
    for ev_year, ev_name in EVENTS:
        r = its_simple(years, vals, ev_year)
        if r is None:
            row.append(f"{'—':<14}")
            continue
        results[c][ev_name] = r
        eff = r["effect"]
        t = r["t"]
        sig = "★★★" if abs(t) > 2.58 else "★★" if abs(t) > 1.96 else "★" if abs(t) > 1.64 else ""
        row.append(f"{eff:+6.2f}{sig:<3}({t:>4.1f}t)")
    print(f"{c:<7} | " + " | ".join(row))

print("\n说明: 数字 = post 实际值 − pre 趋势外推值 (每千字单位)")
print("      ★ |t|>1.64, ★★ |t|>1.96, ★★★ |t|>2.58")

# ============================================================================
# 哪些 (概念, 事件) 组合显著
# ============================================================================
print("\n=== 显著效应汇总 (|t| > 1.96, p < .05) ===")
strong = []
for c in KEY_CONCEPTS:
    for ev_name in [e[1] for e in EVENTS]:
        r = results[c].get(ev_name)
        if r and abs(r["t"]) > 1.96:
            strong.append((c, ev_name, r["effect"], r["t"], r["actual_post"], r["cf_post"]))

for c, ev, eff, t, ap, cf in sorted(strong, key=lambda x: -abs(x[3])):
    direction = "上升" if eff > 0 else "下降"
    print(f"  {c:<6}  {ev:<8}: 实际 {ap:.2f} vs 反事实 {cf:.2f}, 偏离 {eff:+.2f} (t={t:.2f}) — {direction}")

# 保存
out = ROOT / "data" / "analysis" / "probe_concept_its.json"
out.write_text(json.dumps({"results": results,
                            "events": [(int(y), n) for y, n in EVENTS]},
                          ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")
