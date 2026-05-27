"""全集级 ITS: 28 个年份点的人格维度时间序列 + 事件 pre/post 因果效应

关键差异 vs 之前的 343 条版本:
  - 时间点 9 → 28 (3x)
  - pre-period 自由度 2-3 → 5-10 (t 值终于可信)
  - 6 个体裁可分别测 (解决记录者-时段共线)
  - 含奏疏 → 能测处变能力 / 决断力 / 情感深度

5 个 treatment 事件:
  1506 廷杖几死 + 贬龙场
  1508 龙场悟道
  1517 徐爱卒
  1519 平宁王之乱
  1521 致良知
  1527 天泉证道
"""
import json
from pathlib import Path
from collections import defaultdict

import numpy as np

from personality_markers_v2 import DIMENSIONS

ROOT = Path(__file__).resolve().parent.parent

# 读年份汇总
year_summary = json.loads(
    (ROOT / "data" / "analysis" / "personality_full_by_year.json").read_text(encoding="utf-8")
)

# 转 numpy: 每个维度一条时间序列
all_years = sorted(int(y) for y in year_summary.keys())
print(f"覆盖年份: {all_years}")
print(f"时间点数: {len(all_years)}")

series = {}    # dim → [(year, mean, se, n)]
for dim in DIMENSIONS:
    series[dim] = []
    for y in all_years:
        d = year_summary[str(y)].get(dim)
        if d:
            series[dim].append((y, d["mean"], d["se"], d["n"]))

# ============================================================================
# ITS 主函数
# ============================================================================
def its(series_tuples, event_year, min_pre=3, min_post=3):
    """
    在 pre-period 拟合线性趋势, 外推到 post-period, 估计偏离.

    series_tuples: list of (year, mean, se, n)
    返回 dict
    """
    if not series_tuples:
        return None
    yrs   = np.array([t[0] for t in series_tuples])
    means = np.array([t[1] for t in series_tuples])
    ns    = np.array([t[3] for t in series_tuples])

    pre_mask = yrs < event_year
    post_mask = yrs >= event_year
    if pre_mask.sum() < min_pre or post_mask.sum() < min_post:
        return None

    pre_y, pre_v = yrs[pre_mask], means[pre_mask]
    post_y, post_v = yrs[post_mask], means[post_mask]
    pre_n = ns[pre_mask]; post_n = ns[post_mask]

    # OLS on pre: v ~ alpha + beta * (year - event_year)
    A = np.column_stack([np.ones_like(pre_y, dtype=float), (pre_y - event_year).astype(float)])
    beta, _, _, _ = np.linalg.lstsq(A, pre_v, rcond=None)
    alpha, slope = float(beta[0]), float(beta[1])

    cf_post = alpha + slope * (post_y - event_year)
    effect_per_year = post_v - cf_post
    avg_effect = float(np.mean(effect_per_year))

    # 简化 SE: pre 残差方差作 noise 估计, 加权 post 自由度
    pre_resid = pre_v - (alpha + slope * (pre_y - event_year))
    if len(pre_resid) > 2:
        s2 = float(np.sum(pre_resid ** 2) / (len(pre_resid) - 2))
    else:
        s2 = 0.0
    se = (s2 * (1/len(pre_y) + 1/len(post_y))) ** 0.5 if s2 > 0 else 1e-9
    t = avg_effect / se if se > 1e-9 else 0

    return {
        "event_year":     event_year,
        "n_pre":          int(pre_mask.sum()),
        "n_post":         int(post_mask.sum()),
        "pre_alpha":      alpha,
        "pre_slope":      slope,
        "pre_residual_se": float(np.sqrt(s2)) if s2 > 0 else 0.0,
        "actual_post":    float(np.mean(post_v)),
        "cf_post":        float(np.mean(cf_post)),
        "effect":         avg_effect,
        "se":             se,
        "t":              t,
        "pre_years":      pre_y.tolist(),
        "pre_actual":     pre_v.tolist(),
        "post_years":     post_y.tolist(),
        "post_actual":    post_v.tolist(),
        "post_cf":        cf_post.tolist(),
    }


# ============================================================================
# 6 个事件 × 8 个维度
# ============================================================================
EVENTS = [
    (1506, "廷杖贬龙场"),
    (1508, "龙场悟道"),
    (1517, "徐爱卒"),
    (1519, "平宁王之乱"),
    (1521, "致良知正式提出"),
    (1527, "天泉证道"),
]

print()
print("=" * 110)
print("全集级 ITS: 6 个事件 × 8 个维度的因果效应估计")
print("=" * 110)
print(f"{'事件':<22} | " + " | ".join(f"{d:>10}" for d in DIMENSIONS))
print("-" * 110)

results = {}
for ev_year, ev_name in EVENTS:
    label = f"{ev_year} {ev_name}"
    results[label] = {}
    row = []
    for dim in DIMENSIONS:
        r = its(series[dim], ev_year)
        if r is None:
            row.append("    —    ")
            continue
        results[label][dim] = r
        eff = r["effect"]
        t = r["t"]
        sig = "★★★" if abs(t) > 2.58 else "★★" if abs(t) > 1.96 else "★" if abs(t) > 1.64 else ""
        row.append(f"{eff:+6.2f}{sig:<3}({t:>4.1f})")
    print(f"{label:<22} | " + " | ".join(row))

# 显著效应汇总
print()
print("=" * 90)
print("显著效应汇总 (|t| > 1.96)")
print("=" * 90)
strong = []
for ev_label, dims in results.items():
    for dim, r in dims.items():
        if abs(r["t"]) > 1.96:
            strong.append((ev_label, dim, r["effect"], r["t"],
                           r["actual_post"], r["cf_post"],
                           r["n_pre"], r["n_post"]))

for ev, dim, eff, t, ap, cf, np_, np2 in sorted(strong, key=lambda x: -abs(x[3])):
    direction = "上升" if eff > 0 else "下降"
    sig = "★★★" if abs(t) > 2.58 else "★★"
    print(f"  {ev:<24} {dim:<8} {direction}  "
          f"实际 {ap:>6.2f} vs 反事实 {cf:>6.2f}, 偏离 {eff:+6.2f}  "
          f"(t={t:>5.2f} {sig}, pre={np_} post={np2})")

# 保存
out = ROOT / "data" / "analysis" / "its_full_corpus.json"
out.write_text(json.dumps({
    "events":   [(y, n) for y, n in EVENTS],
    "all_years": all_years,
    "results":  results,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")
