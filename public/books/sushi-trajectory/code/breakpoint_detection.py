"""
breakpoint_detection.py
对 17 条时间序列做断点检测 (8 维人格 + 9 主题概念)

不依赖 ruptures 库, 手撸 Binary Segmentation + BIC 选 K
"""
import json
import math
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSON_YEARLY = PROJECT_ROOT / "data" / "corpus" / "personality_yearly.json"
CONCEPT_YEARLY = PROJECT_ROOT / "data" / "corpus" / "concept_yearly.json"
OUT = PROJECT_ROOT / "data" / "corpus" / "breakpoints.json"


def segment_ss(y, start, end):
    """段 [start, end] 内的均值与残差平方和"""
    seg = y[start:end]
    if len(seg) == 0:
        return 0.0, 0.0
    mean = seg.mean()
    ss = ((seg - mean) ** 2).sum()
    return mean, ss


def binseg(y, min_seg=2, max_breaks=3):
    """
    Binary segmentation: 贪心找 1, 2, ..., max_breaks 个断点
    返回 [(positions, total_ss), ...]
    """
    n = len(y)
    results = []
    breaks = []

    for K in range(1, max_breaks + 1):
        # 在现有 segments 里找下一个最佳新断点
        all_starts_ends = []
        sorted_breaks = sorted(breaks)
        boundaries = [0] + sorted_breaks + [n]
        segments = list(zip(boundaries[:-1], boundaries[1:]))

        best_pos = None
        best_score = float("inf")
        for (s, e) in segments:
            if e - s < 2 * min_seg:
                continue
            base_mean, base_ss = segment_ss(y, s, e)
            for split in range(s + min_seg, e - min_seg + 1):
                _, ss_left = segment_ss(y, s, split)
                _, ss_right = segment_ss(y, split, e)
                score = ss_left + ss_right
                if score < best_score:
                    best_score = score
                    best_pos = split
        if best_pos is None:
            break
        breaks.append(best_pos)
        # 算总 SS
        sorted_breaks_now = sorted(breaks)
        boundaries_now = [0] + sorted_breaks_now + [n]
        total_ss = sum(segment_ss(y, s, e)[1]
                       for s, e in zip(boundaries_now[:-1], boundaries_now[1:]))
        results.append((sorted(breaks), total_ss))
    return results


def bic_select(y, candidates):
    """BIC 选择最佳 K"""
    n = len(y)
    best = (0, [], None)  # K=0
    _, ss0 = segment_ss(y, 0, n)
    if ss0 > 0:
        bic_0 = n * math.log(ss0 / n)
        best = (0, [], bic_0)
    else:
        best = (0, [], 0.0)

    for K, (breaks, ss) in enumerate(candidates, start=1):
        if ss <= 0:
            continue
        # BIC: K+1 段均值 + K 断点位置 = 2K+1 个参数
        bic = n * math.log(ss / n) + (2 * K + 1) * math.log(n)
        if best[2] is None or bic < best[2]:
            best = (K, breaks, bic)
    return best


def main():
    person_yearly = json.load(PERSON_YEARLY.open(encoding="utf-8"))
    concept_yearly = json.load(CONCEPT_YEARLY.open(encoding="utf-8"))

    person_yearly = {int(k): v for k, v in person_yearly.items()}
    concept_yearly = {int(k): v for k, v in concept_yearly.items()}

    # 维度与主题
    sample = next(iter(person_yearly.values()))
    DIMS = [k for k in sample if k.startswith("D") and "__" not in k]
    sample2 = next(iter(concept_yearly.values()))
    THEMES = [k for k in sample2 if k not in ("n_pieces", "total_chars")]

    # 共同年份
    years = sorted(person_yearly.keys())

    results = {}

    def run_series(name, source, yearly_dict):
        ys = []
        vals = []
        for y in years:
            if name in yearly_dict.get(y, {}):
                ys.append(y)
                vals.append(yearly_dict[y][name])
        if len(vals) < 8:
            return None
        y_arr = np.array(vals, dtype=float)
        candidates = binseg(y_arr, min_seg=2, max_breaks=3)
        K, breaks, bic = bic_select(y_arr, candidates)
        # 把 indices 转回年份
        bp_years = [ys[b] for b in breaks if b < len(ys)]
        # 各段均值
        boundaries = [0] + breaks + [len(ys)]
        seg_means = []
        for s, e in zip(boundaries[:-1], boundaries[1:]):
            if e > s:
                seg_means.append({
                    "year_from": ys[s] if s < len(ys) else None,
                    "year_to": ys[e-1] if e-1 < len(ys) else None,
                    "mean": float(np.mean(vals[s:e])),
                    "n_years": e - s,
                })
        return {
            "name": name, "source": source, "K": K,
            "breakpoints_idx": breaks,
            "breakpoints_year": bp_years,
            "BIC": bic,
            "seg_means": seg_means,
            "years_used": ys,
        }

    print(f"=== 17 序列断点检测 ===")
    print(f"  {'序列名':22s}  {'K':>2s}  {'断点年份':16s}  {'段均值演化'}")
    for dim in DIMS:
        r = run_series(dim, "personality", person_yearly)
        if r:
            results[dim] = r
            bp_str = ",".join(str(b) for b in r["breakpoints_year"]) if r["breakpoints_year"] else "-"
            mean_str = " → ".join(f"{s['mean']:.2f}" for s in r["seg_means"])
            print(f"  {dim:22s}  {r['K']:>2d}  {bp_str:16s}  {mean_str}")
    for theme in THEMES:
        r = run_series(theme, "concept", concept_yearly)
        if r:
            results[theme] = r
            bp_str = ",".join(str(b) for b in r["breakpoints_year"]) if r["breakpoints_year"] else "-"
            mean_str = " → ".join(f"{s['mean']:.2f}" for s in r["seg_means"])
            print(f"  {theme:22s}  {r['K']:>2d}  {bp_str:16s}  {mean_str}")

    # ---------- 断点聚类: 哪些年份被多次选为断点 ----------
    from collections import Counter
    bp_counter = Counter()
    for name, r in results.items():
        for bp in r["breakpoints_year"]:
            bp_counter[bp] += 1
    print()
    print(f"=== 断点年份聚类 (出现 ≥ 2 次的年份) ===")
    for year, count in sorted(bp_counter.items()):
        if count >= 2:
            print(f"  {year}: {count} 次  (相关序列: ", end="")
            related = [n for n, r in results.items() if year in r["breakpoints_year"]]
            print(", ".join(related) + ")")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
