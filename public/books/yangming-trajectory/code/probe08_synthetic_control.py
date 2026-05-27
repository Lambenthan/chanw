"""探针实验: 文本内 quasi-synthetic control

核心思路 (改编自 Abadie et al. 2010):
  - "treated" 序列: 受 1519-1521 事件链影响的概念 (致良知 / 良知 / 人欲)
  - "donor pool" (供体池): 阳明文本里相对稳定、不应受这次事件影响的概念
    候选: 性 / 仁 / 义 / 中庸 / 修身 (传统儒家术语,理论上跨事件应稳定)
  - 在 pre-period (1515-1521) 上, 寻找 donor 的权重 w_i, 使加权和最贴合 treated
  - 在 post-period (1521+), 用同样 weights 算"反事实" treated 序列
  - 比较实际 vs 反事实

权重约束 (Abadie 标准):
  - 所有 w_i >= 0
  - sum(w_i) = 1

简化版用 SLSQP 优化 (scipy)
"""
import json
import csv
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent

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


TREATMENT_YEAR = 1521  # 阳明正式提出致良知三字

# Treated 序列: 我们想构造反事实的概念
TREATED = ["致良知", "良知", "人欲", "天理"]

# Donor pool: 应该相对稳定 (不直接受致良知事件影响)
DONORS = ["性", "仁", "义", "中庸", "修身", "工夫", "用功", "格物", "诚意"]


def synthetic_control(treated_series, donor_series, years, treatment_year):
    """给定 treated 序列 + donor 序列 (各为 list of values over years),
    在 pre-period 上求 w 最小化 ||treated_pre - W @ donor_pre||,
    约束 sum(w)=1, w >= 0.
    返回: weights + 反事实序列 + 拟合误差 + 偏离
    """
    yrs = np.asarray(years)
    pre_mask = yrs < treatment_year
    post_mask = yrs >= treatment_year

    Y_pre  = np.asarray(treated_series)[pre_mask]
    Y_post = np.asarray(treated_series)[post_mask]
    D_pre  = np.asarray(donor_series)[:, pre_mask]   # (n_donors, n_pre)
    D_post = np.asarray(donor_series)[:, post_mask]

    n_d = D_pre.shape[0]

    def loss(w):
        synth = w @ D_pre
        return float(np.sum((Y_pre - synth) ** 2))

    # 优化
    w0 = np.ones(n_d) / n_d
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bnds = [(0, 1) for _ in range(n_d)]
    res = minimize(loss, w0, method="SLSQP", constraints=cons, bounds=bnds)
    w = res.x

    cf_pre  = w @ D_pre
    cf_post = w @ D_post

    return {
        "weights":      [float(x) for x in w],
        "pre_actual":   [float(x) for x in Y_pre],
        "pre_cf":       [float(x) for x in cf_pre],
        "pre_rmse":     float(np.sqrt(np.mean((Y_pre - cf_pre) ** 2))),
        "post_actual":  [float(x) for x in Y_post],
        "post_cf":      [float(x) for x in cf_post],
        "post_effect":  float(np.mean(Y_post) - np.mean(cf_post)),
        "post_effect_per_year": [(int(y), float(a-c)) for y, a, c in
                                  zip(yrs[post_mask], Y_post, cf_post)],
        "pre_years":    [int(y) for y in yrs[pre_mask]],
        "post_years":   [int(y) for y in yrs[post_mask]],
    }


# 跑 4 个 treated 概念
donor_matrix = np.array([freq[d] for d in DONORS])

print("=" * 95)
print(f"合成控制法: treatment = {TREATMENT_YEAR} 致良知")
print("=" * 95)
print(f"Donor pool: {DONORS}")
print()

results = {}
for c in TREATED:
    treated = freq[c]
    sc = synthetic_control(treated, donor_matrix, years, TREATMENT_YEAR)
    results[c] = sc

    print(f"\n[{c}]")
    print(f"  Pre 期拟合 RMSE = {sc['pre_rmse']:.3f} (越小越好)")
    print(f"  Donor 权重 (>0.01): ", end="")
    weights_str = []
    for d, w in zip(DONORS, sc["weights"]):
        if w > 0.01:
            weights_str.append(f"{d}={w:.2f}")
    print(", ".join(weights_str))

    print(f"  Post 实际均值: {np.mean(sc['post_actual']):.2f}")
    print(f"  Post 反事实均值: {np.mean(sc['post_cf']):.2f}")
    print(f"  ★ 偏离 (实际 − 反事实): {sc['post_effect']:+.2f}")

    print(f"  逐年偏离:")
    for y, eff in sc["post_effect_per_year"]:
        print(f"    {y}: {eff:+6.2f}")

# 安慰剂检验: 用 donor 池里每个概念当 placebo treated, 跑同样合成
# 如果 placebo 偏离的分布广泛覆盖了我们的真正 treated 偏离, 说明效应不显著
print()
print("=" * 95)
print("Placebo 检验: 把 donor 当 treated 跑同样合成, 看 post 偏离分布")
print("=" * 95)

placebo_effects = {}
for placebo_c in DONORS:
    other_donors = [d for d in DONORS if d != placebo_c]
    other_matrix = np.array([freq[d] for d in other_donors])
    sc = synthetic_control(freq[placebo_c], other_matrix, years, TREATMENT_YEAR)
    placebo_effects[placebo_c] = sc["post_effect"]

print(f"{'概念':<8}  {'post 偏离':>12}")
for c, e in sorted(placebo_effects.items(), key=lambda x: -abs(x[1])):
    print(f"{c:<8}  {e:+12.2f}")

# 比较 treated 偏离 vs placebo 偏离分布
treated_effects = {c: results[c]["post_effect"] for c in TREATED}
placebo_array = np.array(list(placebo_effects.values()))
print(f"\nPlacebo 偏离 95% 区间: [{np.percentile(placebo_array, 2.5):.2f}, "
      f"{np.percentile(placebo_array, 97.5):.2f}]")
print(f"Placebo 偏离最大 |.|: {np.max(np.abs(placebo_array)):.2f}")

print(f"\n=== Treated 偏离 vs Placebo 上界 ===")
for c, e in treated_effects.items():
    p_max = np.max(np.abs(placebo_array))
    signif = "★★★" if abs(e) > p_max else "★★" if abs(e) > p_max * 0.7 else ""
    print(f"  {c:<6}: {e:+7.2f}   (placebo max {p_max:.2f})   {signif}")

# 保存
out = ROOT / "data" / "analysis" / "synthetic_control.json"
out.write_text(json.dumps({
    "treatment_year":   TREATMENT_YEAR,
    "donors":           DONORS,
    "results":          results,
    "placebo_effects":  placebo_effects,
    "years":            [int(y) for y in years],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")
