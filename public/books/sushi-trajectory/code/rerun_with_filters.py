"""
rerun_with_filters.py
基于 sushi_main_annotated.jsonl, 用归一化文本重跑评分,
然后跑 4 个版本的 ITS 对比:
  v1: 原始 (含代笔, 未归一化)         — 复刻第 1 章原结果
  v2: 排除代笔, 未归一化
  v3: 排除代笔 + 异体字归一化
  v4: 排除代笔 + 归一化 + 仅 self_expression 词

输出: data/corpus/rerun_comparison.json
"""
import json
from pathlib import Path
from collections import defaultdict
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import CORE_CONCEPTS, PERSONALITY_DIMENSIONS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IN = PROJECT_ROOT / "data" / "corpus" / "sushi_main_annotated.jsonl"
OUT = PROJECT_ROOT / "data" / "corpus" / "rerun_comparison.json"

TREATMENT_YEAR = 1079
PRE_START = 1056
POST_END = 1101


def score_text(text, word_lists):
    s = {}
    for sub, words in word_lists.items():
        s[sub] = sum(text.count(w) for w in words)
    return s


def its_ols(years, values):
    y = np.array(values, dtype=float)
    t = np.array(years, dtype=float)
    D = (t >= 1080).astype(float)
    t_post = np.where(D == 1, t - TREATMENT_YEAR, 0)
    X = np.column_stack([np.ones_like(t), t - PRE_START, D, t_post])
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
    return {
        "n": int(n),
        "beta2_level_shift": float(beta[2]),
        "se_level_shift": float(se[2]),
        "t_level_shift": float(beta[2] / se[2]),
    }


def aggregate_yearly(records, text_field, dim_or_theme, lookup):
    """对一组篇目按年聚合, 算每千字 per1k 后取年内平均"""
    by_year = defaultdict(list)
    for r in records:
        y = r.get("year")
        conf = r.get("year_confidence")
        if not y or conf not in ("high", "medium"):
            continue
        if y == TREATMENT_YEAR:
            continue
        text = r.get(text_field) or r.get("text") or ""
        chars = max(r.get("char_count", 0), 1)
        entry = lookup.get(dim_or_theme)
        if isinstance(entry, dict):
            # PERSONALITY_DIMENSIONS: subdim -> [words]
            cnt = sum(sum(text.count(w) for w in ws) for ws in entry.values())
        elif isinstance(entry, list):
            # CORE_CONCEPTS: theme -> [words]
            cnt = sum(text.count(w) for w in entry)
        else:
            continue
        per1k = cnt / chars * 1000
        by_year[y].append(per1k)
    return {y: np.mean(v) for y, v in by_year.items() if v}


def run_its_on_records(records, name, source, text_field):
    """对一个 records 子集跑 17 序列 ITS, 返回 {name: result}"""
    out = {}
    for dim in PERSONALITY_DIMENSIONS:
        yearly = aggregate_yearly(records, text_field, dim, PERSONALITY_DIMENSIONS)
        if len(yearly) < 8:
            continue
        years = sorted(yearly.keys())
        vals = [yearly[y] for y in years]
        r = its_ols(years, vals)
        if r:
            r["dim"] = dim
            r["source"] = "personality"
            r["pre_mean"] = float(np.mean([yearly[y] for y in years if y < TREATMENT_YEAR]))
            r["post_mean"] = float(np.mean([yearly[y] for y in years if y > TREATMENT_YEAR]))
            out[dim] = r
    for theme in CORE_CONCEPTS:
        yearly = aggregate_yearly(records, text_field, theme, CORE_CONCEPTS)
        if len(yearly) < 8:
            continue
        years = sorted(yearly.keys())
        vals = [yearly[y] for y in years]
        r = its_ols(years, vals)
        if r:
            r["dim"] = theme
            r["source"] = "concept"
            r["pre_mean"] = float(np.mean([yearly[y] for y in years if y < TREATMENT_YEAR]))
            r["post_mean"] = float(np.mean([yearly[y] for y in years if y > TREATMENT_YEAR]))
            out[theme] = r
    return out


def main():
    all_records = []
    with IN.open(encoding="utf-8") as f:
        for line in f:
            all_records.append(json.loads(line))
    print(f"加载 {len(all_records)} 篇")

    # 4 个版本
    versions = {
        "v1_baseline": all_records,  # 复刻原 ITS
        "v2_no_ghostwriting": [r for r in all_records if not r.get("is_ghostwriting")],
        "v3_no_gw_normalized": [r for r in all_records if not r.get("is_ghostwriting")],
        "v4_no_gw_norm_selfexpr": [r for r in all_records if not r.get("is_ghostwriting")
                                    and (r.get("genre_raw") != "词" or r.get("social_function") == "self_expression")],
    }
    text_fields = {
        "v1_baseline": "text",
        "v2_no_ghostwriting": "text",
        "v3_no_gw_normalized": "text_normalized",
        "v4_no_gw_norm_selfexpr": "text_normalized",
    }

    results = {}
    for v_name, recs in versions.items():
        n_total = len(recs)
        print(f"  {v_name}: n={n_total}")
        results[v_name] = run_its_on_records(recs, v_name, "main", text_fields[v_name])

    # ---------- 输出对比表 ----------
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 关键序列: D2 / D8 / 贬谪 / 黄州 / 佛家
    KEY = ["D2_自我修正", "D7_隐逸倾向", "D8_三教融合", "贬谪", "黄州", "佛家", "归隐"]
    print()
    print(f"=== 4 版本 ITS 关键效应对比 (β₂ level shift, t-stat) ===")
    print(f"  {'目标':16s}" + "".join(f"  {v[:18]:>20s}" for v in versions))
    for k in KEY:
        row = f"  {k:16s}"
        for v in versions:
            if k in results[v]:
                r = results[v][k]
                row += f"  {r['beta2_level_shift']:>+8.2f} (t={r['t_level_shift']:>+5.2f}) "
            else:
                row += f"  {'-':>20s}"
        print(row)

    print()
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
