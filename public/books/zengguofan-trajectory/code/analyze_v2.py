"""
analyze_v2.py
基于 EPUB 抽出的 letters_v2.jsonl (1482 封) + diary.jsonl (75 part)
重跑全部分析: 评分 / ITS / 散度 / 断点 / FE

新增 1870 天津教案 treatment 候选 (现有 36 封 1870 + 26 封 1871 家书支撑).
"""
import json
import math
from pathlib import Path
from collections import defaultdict, Counter
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import CORE_CONCEPTS, PERSONALITY_DIMENSIONS, all_concepts_flat

ROOT = Path(__file__).resolve().parent.parent
LETTERS = ROOT / "data" / "corpus" / "letters_v2.jsonl"
DIARY = ROOT / "data" / "corpus" / "diary.jsonl"
SHUZHA = ROOT / "data" / "corpus" / "shuzha.jsonl"
OUT = ROOT / "data" / "corpus"

TREATMENT_CANDIDATES = [1853, 1860, 1864, 1870]


def load_jsonl(p):
    return [json.loads(l) for l in p.open(encoding="utf-8")]


def annotate_scores(records):
    for r in records:
        text = r["text"]
        chars = max(r["char_count"], 1)
        for dim, subs in PERSONALITY_DIMENSIONS.items():
            cnt = sum(text.count(w) for sub in subs.values() for w in sub)
            r[f"{dim}_per1k"] = cnt / chars * 1000
        for theme, words in CORE_CONCEPTS.items():
            cnt = sum(text.count(w) for w in words)
            r[f"{theme}_per1k"] = cnt / chars * 1000
    return records


def aggregate_yearly(records, key):
    by_y = defaultdict(list)
    for r in records:
        if r.get("year") is not None:
            by_y[r["year"]].append(r[key])
    return {y: float(np.mean(v)) for y, v in by_y.items() if v}


def its_ols(years, values, treatment_year):
    y = np.array(values, dtype=float)
    t = np.array(years, dtype=float)
    D = (t >= treatment_year + 1).astype(float)
    t_post = np.where(D == 1, t - treatment_year, 0)
    X = np.column_stack([np.ones_like(t), t, D, t_post])
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
        "n": int(n), "treatment_year": treatment_year,
        "beta2": float(beta[2]),
        "t_stat": float(beta[2] / se[2]) if se[2] > 0 else 0.0,
        "pre_mean": float(np.mean([v for y_, v in zip(years, values) if y_ < treatment_year])),
        "post_mean": float(np.mean([v for y_, v in zip(years, values) if y_ > treatment_year])),
    }


def run_its(letters, treatment_year):
    out = {}
    for dim in PERSONALITY_DIMENSIONS:
        yearly = aggregate_yearly(letters, f"{dim}_per1k")
        years = sorted(yearly.keys())
        if len(years) < 8:
            continue
        years = [y for y in years if y != treatment_year]
        vals = [yearly[y] for y in years]
        r = its_ols(years, vals, treatment_year)
        if r:
            out[dim] = r
    for theme in CORE_CONCEPTS:
        yearly = aggregate_yearly(letters, f"{theme}_per1k")
        years = sorted(yearly.keys())
        if len(years) < 8:
            continue
        years = [y for y in years if y != treatment_year]
        vals = [yearly[y] for y in years]
        r = its_ols(years, vals, treatment_year)
        if r:
            out[theme] = r
    return out


# 散度
def text_to_dist(text, concepts):
    c = {w: text.count(w) for w in concepts}
    tot = sum(c.values())
    if tot == 0:
        return {w: 0.0 for w in concepts}
    return {w: c[w] / tot for w in c}


def js(p, q):
    m = {w: (p[w] + q[w]) / 2 for w in p}
    def kl(a, b):
        s = 0.0
        for w in a:
            if a[w] > 0 and b[w] > 0:
                s += a[w] * math.log2(a[w] / b[w])
        return s
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def run_divergence(letters):
    """6 时段切分 + 二维参照(李 / 左)
    新增 P5 1870 教案时段
    """
    PERIODS = {
        "P1_翰林期": (1841, 1852),
        "P2_创湘军": (1854, 1859),
        "P3_安庆天京": (1861, 1864),
        "P4_办洋务": (1865, 1869),
        "P5_教案晚年": (1871, 1872),
    }
    concepts = all_concepts_flat()
    pt = defaultdict(str)
    np_ct = defaultdict(int)
    for r in letters:
        y = r.get("year")
        if y is None:
            continue
        for nm, (lo, hi) in PERIODS.items():
            if lo <= y <= hi:
                pt[nm] += r["text"]
                np_ct[nm] += 1
                break
    pd_ = {nm: text_to_dist(pt[nm], concepts) for nm in PERIODS}
    # 外部对照
    LI = ROOT / "data" / "raw_corpus" / "li_hongzhang" / "李文忠公选集.txt"
    ZUO = ROOT / "data" / "raw_corpus" / "zuo_zongtang" / "左文襄公奏牍.txt"
    li_text = LI.read_text(encoding="utf-8", errors="replace")
    zuo_text = ZUO.read_text(encoding="utf-8", errors="replace")
    li_dist = text_to_dist(li_text, concepts)
    zuo_dist = text_to_dist(zuo_text, concepts)
    pn = list(PERIODS)
    trans = []
    for i in range(len(pn) - 1):
        a, b = pn[i], pn[i+1]
        if not pt[a] or not pt[b]:
            continue
        trans.append({"from": a, "to": b, "JS": js(pd_[a], pd_[b])})
    coords = {nm: {
        "x_vs_li": js(pd_[nm], li_dist), "y_vs_zuo": js(pd_[nm], zuo_dist),
        "n_pieces": np_ct[nm], "char_total": len(pt[nm])
    } for nm in pn if pt[nm]}
    return {"transitions": trans, "coords": coords,
            "li_vs_zuo": js(li_dist, zuo_dist)}


# 断点
def seg_ss(y, s, e):
    seg = y[s:e]
    if len(seg) == 0:
        return 0.0
    return ((seg - seg.mean()) ** 2).sum()


def binseg(y, min_seg=2, max_breaks=3):
    n = len(y)
    breaks = []
    results = []
    for K in range(1, max_breaks + 1):
        sb = sorted(breaks)
        boundaries = [0] + sb + [n]
        segs = list(zip(boundaries[:-1], boundaries[1:]))
        best_pos, best = None, float("inf")
        for (s, e) in segs:
            if e - s < 2 * min_seg:
                continue
            for split in range(s + min_seg, e - min_seg + 1):
                sc = seg_ss(y, s, split) + seg_ss(y, split, e)
                if sc < best:
                    best, best_pos = sc, split
        if best_pos is None:
            break
        breaks.append(best_pos)
        sb_now = sorted(breaks)
        bd_now = [0] + sb_now + [n]
        total_ss = sum(seg_ss(y, s, e) for s, e in zip(bd_now[:-1], bd_now[1:]))
        results.append((sorted(breaks), total_ss))
    return results


def bic_select(y, cands):
    n = len(y)
    ss0 = seg_ss(y, 0, n)
    if ss0 <= 0:
        return (0, [], 0.0)
    bic_0 = n * math.log(ss0 / n)
    best = (0, [], bic_0)
    for K, (br, ss) in enumerate(cands, start=1):
        if ss <= 0:
            continue
        bic = n * math.log(ss / n) + (2*K+1) * math.log(n)
        if bic < best[2]:
            best = (K, br, bic)
    return best


def run_breakpoints(letters):
    out = {}
    for dim in list(PERSONALITY_DIMENSIONS) + list(CORE_CONCEPTS):
        key = f"{dim}_per1k"
        yearly = aggregate_yearly(letters, key)
        years = sorted(yearly.keys())
        if len(years) < 8:
            continue
        vals = np.array([yearly[y] for y in years], dtype=float)
        cands = binseg(vals, 2, 3)
        K, br, bic = bic_select(vals, cands)
        bp_years = [years[b] for b in br if b < len(years)]
        bd = [0] + br + [len(years)]
        sm = [{"year_from": years[s], "year_to": years[e-1],
               "mean": float(np.mean(vals[s:e]))}
              for s, e in zip(bd[:-1], bd[1:]) if e > s]
        out[dim] = {"K": K, "breakpoints_year": bp_years, "seg_means": sm,
                    "BIC": bic, "n_years": len(years)}
    return out


# 收信人 FE
def run_fe(letters, treatment_year=1860):
    fe_results = {}
    for dim in PERSONALITY_DIMENSIONS:
        rows = [(r[f"{dim}_per1k"], r["recipient_class"],
                 1.0 if r["year"] is not None and r["year"] >= treatment_year+1 else 0.0)
                for r in letters if r["year"] is not None
                and r["year"] != treatment_year
                and r.get("recipient_class")]
        if len(rows) < 50:
            continue
        ys = np.array([x[0] for x in rows])
        posts = np.array([x[2] for x in rows])
        X_naive = np.column_stack([np.ones_like(posts), posts])
        beta_naive = np.linalg.lstsq(X_naive, ys, rcond=None)[0]
        rec_levels = sorted(set(x[1] for x in rows))
        G = len(rec_levels)
        if G < 2:
            continue
        gx = {r: i for i, r in enumerate(rec_levels)}
        X_fe = np.zeros((len(rows), G + 1))
        for i, (_, r_, p) in enumerate(rows):
            j = gx[r_]
            if j < G - 1:
                X_fe[i, j] = 1.0
            X_fe[i, -2] = 1.0
            X_fe[i, -1] = p
        beta_fe = np.linalg.lstsq(X_fe, ys, rcond=None)[0]
        fe_results[dim] = {
            "n": len(rows),
            "beta_post_naive": float(beta_naive[1]),
            "beta_post_fe": float(beta_fe[-1]),
            "diff": float(beta_fe[-1] - beta_naive[1]),
        }
    return fe_results


def main():
    print("=== Step 1: 加载 1482 封家书 ===")
    letters = load_jsonl(LETTERS)
    print(f"  载入 {len(letters)} 封")
    letters = annotate_scores(letters)

    print()
    print("=== Step 2: 4 个 treatment ITS 扫描 (含 1870 新增) ===")
    all_its = {}
    for t in TREATMENT_CANDIDATES:
        all_its[t] = run_its(letters, t)
    (OUT / "its_results_v2.json").write_text(
        json.dumps(all_its, ensure_ascii=False, indent=2), encoding="utf-8")
    KEY = ["D2_自我修正", "D8_三教融合", "军务", "战事", "修身", "湘军", "教化"]
    print(f"  {'目标':16s}" + "".join(f"  {t}".rjust(15) for t in TREATMENT_CANDIDATES))
    for k in KEY:
        row = f"  {k:16s}"
        for t in TREATMENT_CANDIDATES:
            r = all_its[t].get(k)
            if r:
                row += f"  β={r['beta2']:+6.2f} t={r['t_stat']:+5.2f}"
            else:
                row += f"  {'-':>15s}"
        print(row)

    print()
    print("=== Step 3: 散度 (5 时段 + 二维参照) ===")
    div = run_divergence(letters)
    (OUT / "divergence_results_v2.json").write_text(
        json.dumps(div, ensure_ascii=False, indent=2), encoding="utf-8")
    for tr in div["transitions"]:
        print(f"  {tr['from']} → {tr['to']}: JS={tr['JS']:.4f}")
    print()
    print("  二维参照 (JS vs 李 / vs 左):")
    for nm, c in div["coords"].items():
        print(f"    {nm}: JS(李)={c['x_vs_li']:.4f}, JS(左)={c['y_vs_zuo']:.4f}, n={c['n_pieces']}")
    print(f"  Parity: JS(李, 左) = {div['li_vs_zuo']:.4f}")

    print()
    print("=== Step 4: 断点检测 17 序列 ===")
    bp = run_breakpoints(letters)
    (OUT / "breakpoints_v2.json").write_text(
        json.dumps(bp, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, r in bp.items():
        if r["K"] >= 1:
            bp_y = ",".join(str(b) for b in r["breakpoints_year"])
            means = " → ".join(f"{m['mean']:.2f}" for m in r["seg_means"])
            print(f"  {k:16s} K={r['K']}  断点={bp_y}  段均值={means}")

    print()
    print("=== Step 5: 收信人 FE 回归 ===")
    fe = run_fe(letters)
    (OUT / "genre_fe_v2.json").write_text(
        json.dumps(fe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {'维度':18s}  {'naive':>10s}  {'FE':>10s}  {'差':>10s}")
    for k, r in fe.items():
        print(f"  {k:18s}  {r['beta_post_naive']:+10.3f}  "
              f"{r['beta_post_fe']:+10.3f}  {r['diff']:+10.3f}")


if __name__ == "__main__":
    main()
