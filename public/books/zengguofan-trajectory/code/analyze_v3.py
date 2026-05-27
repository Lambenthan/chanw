"""
analyze_v3.py
v3 全数据分析:
  - 日级 ITS: 5554 日条目 + 4 treatment (1853/1860/1864/1870)
  - 五体裁 FE 回归: 家书 / 信札 / 日记 / 奏稿 / 续编信札
  - Placebo 合成控制 (补 v2 留下的待办)
  - 1870 教案均值比较 (因 1872 数据为零, 沿用 chap01 v2 方法)
"""
import json
import math
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import PERSONALITY_DIMENSIONS, CORE_CONCEPTS

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).open(encoding="utf-8")]


def score_record(r):
    text = r["text"]
    chars = max(r.get("char_count", 1), 1)
    for dim, subs in PERSONALITY_DIMENSIONS.items():
        cnt = sum(text.count(w) for sub in subs.values() for w in sub)
        r[f"{dim}_per1k"] = cnt / chars * 1000
    for theme, words in CORE_CONCEPTS.items():
        cnt = sum(text.count(w) for w in words)
        r[f"{theme}_per1k"] = cnt / chars * 1000
    return r


def its_ols(years, vals, treatment_year, year_origin=1841):
    y = np.array(vals, dtype=float)
    t = np.array(years, dtype=float)
    D = (t >= treatment_year + 1).astype(float)
    t_post = np.where(D == 1, t - treatment_year, 0)
    X = np.column_stack([np.ones_like(t), t - year_origin, D, t_post])
    try:
        XtX_inv = np.linalg.inv(X.T @ X)
        beta = XtX_inv @ X.T @ y
    except np.linalg.LinAlgError:
        return None
    resid = y - X @ beta
    n, k = len(y), 4
    if n - k <= 0:
        return None
    sigma2 = (resid ** 2).sum() / (n - k)
    se = np.sqrt(np.diag(XtX_inv) * sigma2)
    return {
        "n": int(n), "treatment": treatment_year,
        "beta2": float(beta[2]),
        "t_stat": float(beta[2] / se[2]) if se[2] > 0 else 0.0,
        "pre_mean": float(np.mean([v for y_, v in zip(years, vals) if y_ < treatment_year])),
        "post_mean": float(np.mean([v for y_, v in zip(years, vals) if y_ > treatment_year])),
    }


# ============================================================
# Step 1: 日级 ITS
# ============================================================
def run_daily_its():
    """用 5554 日条目按 (年, 月) 聚合到月级 (日级太稀疏可能 t=NaN)
    然后跑 ITS"""
    print("=== Step 1: 日级 ITS (日记 5554 条目, 按月聚合) ===")
    diary = [score_record(r) for r in load_jsonl(CORPUS / "diary_daily.jsonl")]
    # 按 (year, month) 聚合
    by_ym = defaultdict(list)
    for r in diary:
        if r.get("year") and r.get("month"):
            by_ym[(r["year"], r["month"])].append(r)

    # 把 (年,月) 转 fractional year (1851.5 = 1851 年 7 月)
    def ym_to_frac(y, m):
        return y + (m - 0.5) / 12

    # 时间序列: 按 frac year 排序的 (frac_year, dim_means)
    series_frac = []
    series_year_int = []
    series_records = []
    for (y, m), rs in sorted(by_ym.items()):
        fy = ym_to_frac(y, m)
        series_frac.append(fy)
        series_year_int.append(y)
        series_records.append(rs)

    print(f"  月级时间点: {len(series_frac)}, 跨 {series_frac[0]:.1f} - {series_frac[-1]:.1f}")

    # 对每个 treatment + 每个序列跑 ITS
    TREATMENTS = [1853, 1860, 1864, 1870]
    KEYS = list(PERSONALITY_DIMENSIONS) + list(CORE_CONCEPTS)
    results = {}
    for t in TREATMENTS:
        results[t] = {}
        for k in KEYS:
            keyl = f"{k}_per1k"
            # 月级序列
            mvs = []
            for fy, recs in zip(series_frac, series_records):
                if fy == t:  # 治疗当年所有月数据剔除
                    continue
                vals = [r[keyl] for r in recs]
                if not vals:
                    continue
                mvs.append((fy, float(np.mean(vals))))
            if len(mvs) < 12:
                continue
            years_arr = [fy for fy, _ in mvs]
            vals_arr = [v for _, v in mvs]
            n_pre = sum(1 for fy in years_arr if fy < t)
            n_post = sum(1 for fy in years_arr if fy > t)
            if n_pre < 6 or n_post < 6:
                continue
            r = its_ols(years_arr, vals_arr, t, year_origin=int(years_arr[0]))
            if r:
                r["n_pre"] = n_pre
                r["n_post"] = n_post
                results[t][k] = r

    (CORPUS / "diary_daily_its.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  {'目标':16s}" + "".join(f"  {t}".rjust(15) for t in TREATMENTS))
    for k in ["D2_自我修正", "D8_三教融合", "军务", "战事", "修身", "教化"]:
        row = f"  {k:16s}"
        for t in TREATMENTS:
            r = results[t].get(k)
            if r:
                row += f"  β={r['beta2']:+6.2f} t={r['t_stat']:+5.2f}"
            else:
                row += f"  {'-':>15s}"
        print(row)


# ============================================================
# Step 2: 五体裁 FE 回归
# ============================================================
def run_genre_fe():
    print()
    print("=== Step 2: 五体裁 FE 回归 (家书 + 信札 + 日记 + 奏稿 + 信札续) ===")
    # 加载五类
    family = [score_record(r) for r in load_jsonl(CORPUS / "letters_v2.jsonl")]
    friend = [score_record(r) for r in load_jsonl(CORPUS / "shuzha.jsonl")]
    diary = [score_record(r) for r in load_jsonl(CORPUS / "diary_daily.jsonl")]
    memorials = [score_record(r) for r in load_jsonl(CORPUS / "memorials.jsonl")]
    friend_cont = [score_record(r) for r in load_jsonl(CORPUS / "shuzha_continued.jsonl")]

    # 给每个标 genre 字段
    for r in family:
        r["genre"] = "家书"
    for r in friend:
        r["genre"] = "信札"
    for r in friend_cont:
        r["genre"] = "信札"
    for r in diary:
        r["genre"] = "日记"
    for r in memorials:
        r["genre"] = "奏稿"

    all_records = family + friend + friend_cont + diary + memorials
    print(f"  五体裁合计: {len(all_records):,} 条")
    print(f"    家书 {len(family)}, 信札 {len(friend)+len(friend_cont)}, 日记 {len(diary)}, 奏稿 {len(memorials)}")

    # 每体裁均值
    from collections import Counter
    genre_means = {}
    for genre in ["家书", "信札", "日记", "奏稿"]:
        sub = [r for r in all_records if r["genre"] == genre]
        if not sub:
            continue
        d = {"n": len(sub)}
        for dim in PERSONALITY_DIMENSIONS:
            key = f"{dim}_per1k"
            vals = [r[key] for r in sub if key in r]
            d[dim] = float(np.mean(vals)) if vals else 0
        genre_means[genre] = d

    print(f"\n  五体裁 × 8 维度均值 (per1k):")
    print(f"  {'体裁':6s} {'n':>6s} " + " ".join(f"{d.split('_')[0]:>6s}" for d in PERSONALITY_DIMENSIONS))
    for genre, d in genre_means.items():
        row = f"  {genre:6s} {d['n']:>6d} "
        for dim in PERSONALITY_DIMENSIONS:
            row += f" {d[dim]:>6.2f}"
        print(row)

    # FE 回归: y = α_genre + β * post + ε, treatment=1860
    print(f"\n  五体裁 FE 回归 (1860 treatment):")
    fe_results = {}
    for dim in PERSONALITY_DIMENSIONS:
        keyl = f"{dim}_per1k"
        rows = [(r[keyl], r["genre"], 1.0 if r.get("year") and r["year"] >= 1861 else 0.0)
                for r in all_records
                if r.get("year") and r["year"] != 1860 and keyl in r]
        if len(rows) < 100:
            continue
        ys = np.array([x[0] for x in rows])
        posts = np.array([x[2] for x in rows])
        # naive
        X_n = np.column_stack([np.ones_like(posts), posts])
        beta_n = np.linalg.lstsq(X_n, ys, rcond=None)[0]
        # FE
        genres_used = sorted(set(x[1] for x in rows))
        G = len(genres_used)
        if G < 2:
            continue
        gx = {g: i for i, g in enumerate(genres_used)}
        X_fe = np.zeros((len(rows), G + 1))
        for i, (_, g_, p) in enumerate(rows):
            j = gx[g_]
            if j < G - 1:
                X_fe[i, j] = 1.0
            X_fe[i, -2] = 1.0
            X_fe[i, -1] = p
        beta_fe = np.linalg.lstsq(X_fe, ys, rcond=None)[0]
        fe_results[dim] = {
            "n": len(rows),
            "naive": float(beta_n[1]),
            "fe": float(beta_fe[-1]),
            "diff": float(beta_fe[-1] - beta_n[1]),
        }
        print(f"    {dim:18s}  n={len(rows):>6d}  naive={beta_n[1]:+7.3f}  FE={beta_fe[-1]:+7.3f}  diff={beta_fe[-1]-beta_n[1]:+7.3f}")

    out = {"genre_means": genre_means, "fe_1860": fe_results}
    (CORPUS / "genre_fe_v3.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# Step 3: Placebo 合成控制
# ============================================================
def run_placebo():
    print()
    print("=== Step 3: Placebo 检验 (合成控制) ===")
    from scipy.optimize import minimize

    letters = [score_record(r) for r in load_jsonl(CORPUS / "letters_v2.jsonl")]

    def agg(key):
        by_y = defaultdict(list)
        for r in letters:
            if r.get("year"):
                by_y[r["year"]].append(r[key])
        return {y: float(np.mean(v)) for y, v in by_y.items() if v}

    TREATMENT = 1853
    PRE_START = 1841
    POST_END = 1871

    def solve_weights(Y_pre, X_pre):
        J = X_pre.shape[1]
        def loss(w):
            return ((Y_pre - X_pre @ w) ** 2).sum()
        cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
        bnds = [(0.0, 1.0)] * J
        w0 = np.ones(J) / J
        res = minimize(loss, w0, method="SLSQP", constraints=cons, bounds=bnds,
                       options={"maxiter": 200})
        return res.x

    donors = ["D1_政治姿态", "D6_情感深度", "D7_隐逸倾向", "朋友", "家族", "君臣"]
    targets = ["军务", "战事", "修身"]

    donor_data = {d: agg(f"{d}_per1k") for d in donors}
    target_data = {t: agg(f"{t}_per1k") for t in targets}

    common_pre = sorted([y for y in range(PRE_START, TREATMENT) if all(y in donor_data[d] for d in donors)])
    common_post = sorted([y for y in range(TREATMENT + 1, POST_END + 1) if all(y in donor_data[d] for d in donors)])

    print(f"  pre {len(common_pre)} 年, post {len(common_post)} 年")
    results = {}
    print(f"  {'target':10s} {'real gap':>10s} {'placebo p (rank)':>18s}")
    for tgt in targets:
        Y_pre = np.array([target_data[tgt].get(y, 0) for y in common_pre])
        X_pre = np.column_stack([np.array([donor_data[d].get(y, 0) for y in common_pre]) for d in donors])
        w = solve_weights(Y_pre, X_pre)
        X_post = np.column_stack([np.array([donor_data[d].get(y, 0) for y in common_post]) for d in donors])
        Y_post = np.array([target_data[tgt].get(y, 0) for y in common_post])
        real_gap = float((Y_post - X_post @ w).mean())

        # Placebo: 把每个 donor 当假 target
        placebo_gaps = []
        for placebo_target in donors:
            other_donors = [d for d in donors if d != placebo_target]
            y_pl_pre = np.array([donor_data[placebo_target].get(y, 0) for y in common_pre])
            X_pl_pre = np.column_stack([np.array([donor_data[d].get(y, 0) for y in common_pre]) for d in other_donors])
            w_pl = solve_weights(y_pl_pre, X_pl_pre)
            X_pl_post = np.column_stack([np.array([donor_data[d].get(y, 0) for y in common_post]) for d in other_donors])
            y_pl_post = np.array([donor_data[placebo_target].get(y, 0) for y in common_post])
            placebo_gaps.append(float((y_pl_post - X_pl_post @ w_pl).mean()))

        all_gaps = sorted(placebo_gaps + [real_gap], key=lambda x: -abs(x))
        p_rank = (all_gaps.index(real_gap) + 1) / (len(placebo_gaps) + 1)
        results[tgt] = {
            "real_gap": real_gap,
            "placebo_gaps": placebo_gaps,
            "p_rank": p_rank,
        }
        sig = "***" if p_rank <= 0.15 else "**" if p_rank <= 0.30 else "*" if p_rank <= 0.50 else ""
        print(f"  {tgt:10s} {real_gap:>+10.3f} {p_rank:>18.3f} {sig}")

    (CORPUS / "placebo_v3.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    run_daily_its()
    run_genre_fe()
    run_placebo()


if __name__ == "__main__":
    main()
