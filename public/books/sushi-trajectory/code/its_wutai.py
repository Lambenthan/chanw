"""
its_wutai.py
对 1079 乌台诗案做单事件 ITS

模型: y_t = β0 + β1 * t + β2 * D_t + β3 * (t - T*) * D_t + ε
  其中 D_t = 1 if year >= 1080 else 0
       T* = 1079 (treatment year)

  β2 = 立即跳跃 (level shift)
  β3 = 斜率变化 (slope change)
  β1 = pre-period 趋势

对 8 个人格维度 + 9 个核心主题各做一次, 共 17 条序列。
仅使用 high + medium confidence 编年篇目。

输出:
  data/corpus/its_wutai_results.json
"""
import json
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSON_YEARLY = PROJECT_ROOT / "data" / "corpus" / "personality_yearly.json"
CONCEPT_YEARLY = PROJECT_ROOT / "data" / "corpus" / "concept_yearly.json"
OUT = PROJECT_ROOT / "data" / "corpus" / "its_wutai_results.json"

TREATMENT_YEAR = 1079
PRE_START = 1056
POST_END = 1101


def its_ols(years, values):
    """
    手工 OLS, 不依赖外部库 (避免 numpy 之外的依赖)
    返回 (beta0, beta_trend, beta_jump, beta_slope_change, residuals_std, n, t_jump, t_slope)
    """
    y = np.array(values, dtype=float)
    t = np.array(years, dtype=float)
    D = (t >= 1080).astype(float)
    t_post = np.where(D == 1, t - TREATMENT_YEAR, 0)
    # 设计矩阵 [1, t-PRE_START, D, t_post]
    X = np.column_stack([
        np.ones_like(t),
        t - PRE_START,
        D,
        t_post,
    ])
    # OLS
    try:
        XtX = X.T @ X
        XtX_inv = np.linalg.inv(XtX)
        beta = XtX_inv @ X.T @ y
    except np.linalg.LinAlgError:
        return None

    yhat = X @ beta
    resid = y - yhat
    n = len(y)
    k = 4
    if n - k <= 0:
        return None
    sigma2 = (resid ** 2).sum() / (n - k)
    se = np.sqrt(np.diag(XtX_inv) * sigma2)
    t_stats = beta / se
    return {
        "n": int(n),
        "beta0_intercept": float(beta[0]),
        "beta1_pre_trend": float(beta[1]),
        "beta2_level_shift": float(beta[2]),
        "beta3_slope_change": float(beta[3]),
        "se_level_shift": float(se[2]),
        "se_slope_change": float(se[3]),
        "t_level_shift": float(t_stats[2]),
        "t_slope_change": float(t_stats[3]),
        "rmse": float(np.sqrt(sigma2)),
        "r2": float(1 - resid.var() / y.var()) if y.var() > 0 else 0.0,
    }


def main():
    person_yearly = json.load(PERSON_YEARLY.open(encoding="utf-8"))
    concept_yearly = json.load(CONCEPT_YEARLY.open(encoding="utf-8"))

    person_yearly = {int(k): v for k, v in person_yearly.items()}
    concept_yearly = {int(k): v for k, v in concept_yearly.items()}

    # ---------- 维度列表 ----------
    sample = next(iter(person_yearly.values()))
    DIMS = [k for k in sample if k.startswith("D") and "__" not in k]
    sample2 = next(iter(concept_yearly.values()))
    THEMES = [k for k in sample2 if k not in ("n_pieces", "total_chars")]

    print(f"=== ITS 1079 乌台诗案分析 ===")
    print(f"  treatment: {TREATMENT_YEAR}")
    print(f"  pre/post 切分点: D=1 if year>=1080")
    print(f"  pre 年份: {[y for y in sorted(person_yearly) if y < TREATMENT_YEAR]}")
    print(f"  post 年份: {[y for y in sorted(person_yearly) if y > TREATMENT_YEAR]}")

    results = {}

    def run_one(source, name, yearly_dict):
        """对一个维度/主题做 ITS"""
        years = []
        values = []
        for y in sorted(yearly_dict):
            if PRE_START <= y <= POST_END and y != TREATMENT_YEAR:
                # 排除 treatment year 本身 (1079 为过渡年, n=6 噪声大)
                if name in yearly_dict[y]:
                    years.append(y)
                    values.append(yearly_dict[y][name])
        if len(years) < 6:
            return None
        n_pre = sum(1 for y in years if y < TREATMENT_YEAR)
        n_post = sum(1 for y in years if y > TREATMENT_YEAR)
        if n_pre < 2 or n_post < 2:
            return None
        res = its_ols(years, values)
        if res is None:
            return None
        res["dimension"] = name
        res["source"] = source
        res["n_pre_years"] = n_pre
        res["n_post_years"] = n_post
        res["pre_mean"] = float(np.mean([v for y, v in zip(years, values) if y < TREATMENT_YEAR]))
        res["post_mean"] = float(np.mean([v for y, v in zip(years, values) if y > TREATMENT_YEAR]))
        res["pre_post_diff"] = res["post_mean"] - res["pre_mean"]
        return res

    for dim in DIMS:
        r = run_one("personality", dim, person_yearly)
        if r:
            results[dim] = r

    for theme in THEMES:
        r = run_one("concept", theme, concept_yearly)
        if r:
            results[theme] = r

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 汇报 ----------
    print()
    print(f"=== 8 维人格 ITS 结果 ===")
    print(f"  {'维度':18s}  {'n':>3s}  {'pre均':>7s}  {'post均':>7s}  {'level':>8s}  {'t':>6s}  {'slope':>8s}  {'t':>6s}")
    for dim in DIMS:
        if dim not in results:
            continue
        r = results[dim]
        sig = "***" if abs(r["t_level_shift"]) > 3 else "**" if abs(r["t_level_shift"]) > 2 else "*" if abs(r["t_level_shift"]) > 1.7 else ""
        print(f"  {dim:18s}  {r['n']:3d}  {r['pre_mean']:7.2f}  {r['post_mean']:7.2f}  "
              f"{r['beta2_level_shift']:+8.2f}  {r['t_level_shift']:+6.2f}{sig}  "
              f"{r['beta3_slope_change']:+8.3f}  {r['t_slope_change']:+6.2f}")

    print()
    print(f"=== 9 主题概念 ITS 结果 ===")
    print(f"  {'主题':18s}  {'n':>3s}  {'pre均':>7s}  {'post均':>7s}  {'level':>8s}  {'t':>6s}")
    for theme in THEMES:
        if theme not in results:
            continue
        r = results[theme]
        sig = "***" if abs(r["t_level_shift"]) > 3 else "**" if abs(r["t_level_shift"]) > 2 else "*" if abs(r["t_level_shift"]) > 1.7 else ""
        print(f"  {theme:18s}  {r['n']:3d}  {r['pre_mean']:7.2f}  {r['post_mean']:7.2f}  "
              f"{r['beta2_level_shift']:+8.2f}  {r['t_level_shift']:+6.2f}{sig}")

    print()
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
