"""
extract_and_analyze.py
一站式: 切分曾国藩家书 → 解析日期 → 跑 ITS / 散度 / 断点 / FE

家书结构特点:
  - 按主题分类编 (1 修身篇 / 2 教化篇 / ...)
  - 每封信用 "禀父母" / "致沅弟" / "致诸弟" / "致澄弟" / "致温弟" / "致季弟" / "与XX" 开头
  - 末尾用括号标日期 "（道光二十一年五月十八日）"

输出:
  data/corpus/letters.jsonl          每封信一条
  data/corpus/personality_yearly.json
  data/corpus/concept_yearly.json
  data/corpus/its_results.json
  data/corpus/divergence_results.json
  data/corpus/breakpoints.json
  data/corpus/genre_fe_results.json
"""
import json
import re
import math
from pathlib import Path
from collections import defaultdict, Counter
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import CORE_CONCEPTS, PERSONALITY_DIMENSIONS, all_concepts_flat

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LETTERS_RAW = PROJECT_ROOT / "data" / "raw_corpus" / "zeng_main" / "曾国藩家书.txt"
NIANPU_RAW = PROJECT_ROOT / "data" / "raw_corpus" / "zeng_meta" / "曾文正公年谱.txt"
LI_RAW = PROJECT_ROOT / "data" / "raw_corpus" / "li_hongzhang" / "李文忠公选集.txt"
ZUO_RAW = PROJECT_ROOT / "data" / "raw_corpus" / "zuo_zongtang" / "左文襄公奏牍.txt"

CORPUS = PROJECT_ROOT / "data" / "corpus"
CORPUS.mkdir(parents=True, exist_ok=True)

# ============================================================
# 中文数字 / 年号 → 公历年
# ============================================================
ERA_BASE = {
    "嘉庆": 1796, "道光": 1821, "咸丰": 1851, "同治": 1862, "光绪": 1875,
}
CN_NUM = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
          "廿": 20, "卅": 30, "正": 1, "腊": 12}


def cn_to_int(s):
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("廿"):
        return 20 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    if s.startswith("卅"):
        return 30 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    if s.startswith("十"):
        return 10 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    if "十" in s:
        parts = s.split("十", 1)
        tens = (CN_NUM.get(parts[0], 1) if parts[0] else 1) * 10
        ones = CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens + ones
    return None


DATE_RE = re.compile(
    r"[（(]\s*(嘉庆|道光|咸丰|同治|光绪)\s*([元一二三四五六七八九十廿卅]+)\s*年"
    r"(?:\s*(闰)?\s*([元一二三四五六七八九十廿卅正腊]+)\s*月"
    r"(?:\s*([元一二三四五六七八九十廿卅]+)\s*日)?)?\s*[）)]"
)


def parse_chinese_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    era, era_year_cn, _intercalary, month_cn, day_cn = m.groups()
    base = ERA_BASE.get(era)
    if not base:
        return None
    era_year = cn_to_int(era_year_cn)
    if era_year is None:
        return None
    year = base + era_year - 1
    month = cn_to_int(month_cn) if month_cn else None
    day = cn_to_int(day_cn) if day_cn else None
    return {
        "year": year, "month": month, "day": day,
        "era": era, "era_year": era_year,
        "raw": m.group(0),
    }


# ============================================================
# 家书切分
# ============================================================
RECIPIENT_RE = re.compile(
    r"^(禀父母|禀父亲|禀祖父母|禀叔父|"
    r"致诸弟|致温弟|致澄弟|致沅弟|致季弟|致两弟|致温沅季三弟|致沅季两弟|"
    r"致澄沅季三弟|致澄沅两弟|"
    r"致纪泽|致纪鸿|致纪泽纪鸿|"
    r"复.*|与.{1,8})"
)
SECTION_RE = re.compile(r"^\s*(一|二|三|四|五|六|七|八|九|十)\s*(修身篇|劝学篇|治家篇|"
                        r"理财篇|交友篇|为政篇|用人篇|处世篇|治学篇|养生篇|教子篇)?")


def extract_letters():
    """家书无显式标题, 按括号日期切分: 每封信以日期结尾。
    收信人从信首格式推断 (父母大人 / 诸位贤弟 / 沅弟左右等)。"""
    text = LETTERS_RAW.read_text(encoding="utf-8", errors="replace")
    # 找所有日期匹配的 (start, end, date_dict)
    date_positions = []
    for m in DATE_RE.finditer(text):
        date_positions.append({
            "start": m.start(),
            "end": m.end(),
            "raw": m.group(0),
        })
    letters = []
    prev_end = 0
    for i, dp in enumerate(date_positions):
        body = text[prev_end:dp["end"]].strip()
        prev_end = dp["end"]
        # 跳过太短的段
        body_clean = body.replace("\n", "").replace("　", "").replace(" ", "")
        if len(body_clean) < 50:
            continue
        date = parse_chinese_date(dp["raw"])
        # 推断收信人 (从信首 100 字)
        head = body[:120].replace("\n", " ")
        recipient_class = "unknown"
        recipient_raw = None
        for pat, cls in [
            (r"父亲大人|母亲大人|父母大人|祖父母大人", "父母长辈"),
            (r"叔父大人", "父母长辈"),
            (r"诸位贤弟|诸弟|温甫|澄侯|沅甫|季洪|沅弟|澄弟|温弟|季弟", "兄弟"),
            (r"纪泽|纪鸿|字谕纪泽|字谕纪鸿", "儿子"),
        ]:
            mm = re.search(pat, head)
            if mm:
                recipient_class = cls
                recipient_raw = mm.group(0)
                break
        letters.append({
            "id": f"zgf_l{len(letters)+1:04d}",
            "recipient_raw": recipient_raw,
            "recipient_class": recipient_class,
            "year": date["year"] if date else None,
            "month": date["month"] if date else None,
            "day": date["day"] if date else None,
            "date_raw": date["raw"] if date else None,
            "char_count": len(body_clean),
            "text": body,
        })
    return letters


def classify_recipient(r):
    """家书收信人分类: 父母 / 兄弟 / 儿子 / 朋友"""
    if not r:
        return "unknown"
    if "父" in r or "母" in r or "祖" in r or "叔" in r:
        return "父母长辈"
    if "诸弟" in r or "沅" in r or "澄" in r or "温" in r or "季" in r or "两弟" in r:
        return "兄弟"
    if "纪泽" in r or "纪鸿" in r:
        return "儿子"
    return "朋友其他"


# ============================================================
# 评分
# ============================================================
def score_dim(text, dim_dict):
    """对一段 text 计 dim_dict 内所有子维度的词频累加"""
    return sum(text.count(w) for sub in dim_dict.values() for w in sub)


def score_concept(text, words):
    return sum(text.count(w) for w in words)


def annotate_scores(letters):
    """给每封信加 8 维评分 + 9 主题评分 (per1k)"""
    for r in letters:
        text = r["text"]
        chars = max(r["char_count"], 1)
        for dim, subs in PERSONALITY_DIMENSIONS.items():
            r[f"{dim}_per1k"] = score_dim(text, subs) / chars * 1000
        for theme, words in CORE_CONCEPTS.items():
            r[f"{theme}_per1k"] = score_concept(text, words) / chars * 1000
    return letters


# ============================================================
# 按年聚合
# ============================================================
def aggregate_yearly(letters, key_field):
    by_year = defaultdict(list)
    for r in letters:
        if r["year"] is None:
            continue
        by_year[r["year"]].append(r[key_field])
    return {y: float(np.mean(v)) for y, v in by_year.items() if v}


# ============================================================
# ITS 模型: 1860 安庆围攻为核心 treatment (沿用阳明 1506 / 苏轼 1079 的"中段外生冲击"逻辑)
# 但曾国藩还有 1853 创湘军, 我们对 1853 单独做 ITS, 看 1853 vs 1860 vs 1864 vs 1870 哪个最强
# ============================================================
TREATMENT_CANDIDATES = [1853, 1860, 1864, 1870]


def its_ols(years, values, treatment_year):
    y = np.array(values, dtype=float)
    t = np.array(years, dtype=float)
    D = (t >= treatment_year + 1).astype(float)
    t_post = np.where(D == 1, t - treatment_year, 0)
    X = np.column_stack([np.ones_like(t), t, D, t_post])
    try:
        XtX = X.T @ X
        XtX_inv = np.linalg.inv(XtX)
        beta = XtX_inv @ X.T @ y
    except np.linalg.LinAlgError:
        return None
    yhat = X @ beta
    resid = y - yhat
    n, k = len(y), 4
    if n - k <= 0:
        return None
    sigma2 = (resid ** 2).sum() / (n - k)
    se = np.sqrt(np.diag(XtX_inv) * sigma2)
    return {
        "n": int(n),
        "treatment_year": treatment_year,
        "beta2_level_shift": float(beta[2]),
        "se_level_shift": float(se[2]),
        "t_level_shift": float(beta[2] / se[2]) if se[2] > 0 else 0.0,
        "pre_mean": float(np.mean([v for y_, v in zip(years, values) if y_ < treatment_year])),
        "post_mean": float(np.mean([v for y_, v in zip(years, values) if y_ > treatment_year])),
    }


def run_its_all(letters, treatment_year):
    """对 17 序列跑 ITS"""
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


# ============================================================
# 散度分析
# ============================================================
def text_to_concept_dist(text, concepts):
    counts = {c: text.count(c) for c in concepts}
    total = sum(counts.values())
    if total == 0:
        return {c: 0.0 for c in concepts}
    return {c: counts[c] / total for c in counts}


def js_divergence(p, q):
    m = {c: (p[c] + q[c]) / 2 for c in p}
    def kl(a, b):
        s = 0.0
        for c in a:
            if a[c] > 0 and b[c] > 0:
                s += a[c] * math.log2(a[c] / b[c])
        return s
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def l1_divergence(p, q):
    return sum(abs(p[c] - q[c]) for c in p)


def run_divergence(letters):
    """6 时段切分 (依 4 treatment 年)
    P1 入翰林期 (1840-1852, 反新法前)
    P2 创湘军 (1854-1859)
    P3 安庆-天京 (1861-1864)
    P4 江南办洋务 (1865-1869)
    P5 天津教案前后 (1871-1872)
    """
    PERIODS = {
        "P1_翰林期": (1840, 1852),
        "P2_创湘军": (1854, 1859),
        "P3_安庆天京": (1861, 1864),
        "P4_办洋务": (1865, 1869),
        "P5_教案晚年": (1871, 1872),
    }
    concepts = all_concepts_flat()
    period_texts = defaultdict(str)
    n_pieces = defaultdict(int)
    for r in letters:
        y = r["year"]
        if y is None:
            continue
        for name, (lo, hi) in PERIODS.items():
            if lo <= y <= hi:
                period_texts[name] += r["text"]
                n_pieces[name] += 1
                break
    period_dist = {name: text_to_concept_dist(period_texts[name], concepts)
                   for name in PERIODS}
    li_text = LI_RAW.read_text(encoding="utf-8", errors="replace")
    zuo_text = ZUO_RAW.read_text(encoding="utf-8", errors="replace")
    li_dist = text_to_concept_dist(li_text, concepts)
    zuo_dist = text_to_concept_dist(zuo_text, concepts)

    period_names = list(PERIODS.keys())
    transitions = []
    for i in range(len(period_names) - 1):
        a, b = period_names[i], period_names[i+1]
        if not period_texts[a] or not period_texts[b]:
            continue
        transitions.append({
            "from": a, "to": b,
            "JS": js_divergence(period_dist[a], period_dist[b]),
            "L1": l1_divergence(period_dist[a], period_dist[b]),
        })
    coords = {}
    for name in period_names:
        if not period_texts[name]:
            continue
        coords[name] = {
            "x_vs_li": js_divergence(period_dist[name], li_dist),
            "y_vs_zuo": js_divergence(period_dist[name], zuo_dist),
            "n_pieces": n_pieces[name],
            "char_total": len(period_texts[name]),
        }
    return {
        "periods": {name: {
            "n_pieces": n_pieces[name],
            "char_total": len(period_texts[name]),
        } for name in period_names},
        "transitions": transitions,
        "coords": coords,
        "li_vs_zuo_parity": js_divergence(li_dist, zuo_dist),
    }


# ============================================================
# 断点检测
# ============================================================
def segment_ss(y, s, e):
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
        segments = list(zip(boundaries[:-1], boundaries[1:]))
        best_pos, best = None, float("inf")
        for (s, e) in segments:
            if e - s < 2 * min_seg:
                continue
            for split in range(s + min_seg, e - min_seg + 1):
                score = segment_ss(y, s, split) + segment_ss(y, split, e)
                if score < best:
                    best = score
                    best_pos = split
        if best_pos is None:
            break
        breaks.append(best_pos)
        sb_now = sorted(breaks)
        boundaries_now = [0] + sb_now + [n]
        total_ss = sum(segment_ss(y, s, e) for s, e in
                       zip(boundaries_now[:-1], boundaries_now[1:]))
        results.append((sorted(breaks), total_ss))
    return results


def bic_select(y, candidates):
    n = len(y)
    _, ss0 = 0, segment_ss(y, 0, n)
    if ss0 <= 0:
        return (0, [], 0.0)
    bic_0 = n * math.log(ss0 / n)
    best = (0, [], bic_0)
    for K, (breaks, ss) in enumerate(candidates, start=1):
        if ss <= 0:
            continue
        bic = n * math.log(ss / n) + (2 * K + 1) * math.log(n)
        if bic < best[2]:
            best = (K, breaks, bic)
    return best


def run_breakpoints(letters):
    out = {}
    for dim in list(PERSONALITY_DIMENSIONS.keys()) + list(CORE_CONCEPTS.keys()):
        key = f"{dim}_per1k"
        yearly = aggregate_yearly(letters, key)
        years = sorted(yearly.keys())
        if len(years) < 8:
            continue
        vals = np.array([yearly[y] for y in years], dtype=float)
        cands = binseg(vals, 2, 3)
        K, breaks, bic = bic_select(vals, cands)
        bp_years = [years[b] for b in breaks if b < len(years)]
        boundaries = [0] + breaks + [len(years)]
        seg_means = []
        for s, e in zip(boundaries[:-1], boundaries[1:]):
            if e > s:
                seg_means.append({
                    "year_from": years[s],
                    "year_to": years[e-1],
                    "mean": float(np.mean(vals[s:e])),
                })
        out[dim] = {
            "K": K, "breakpoints_year": bp_years,
            "seg_means": seg_means, "BIC": bic, "n_years": len(years)
        }
    return out


# ============================================================
# 收信人 FE 回归
# ============================================================
def run_recipient_fe(letters, treatment_year=1860):
    """y = α_recipient + β * post + ε
    用收信人作为固定效应吸收"教化对象"差异。
    """
    fe_results = {}
    for dim in PERSONALITY_DIMENSIONS:
        rows = [(r[f"{dim}_per1k"], r["recipient_class"],
                 1.0 if r["year"] is not None and r["year"] >= treatment_year+1 else 0.0)
                for r in letters if r["year"] is not None
                and r["year"] != treatment_year
                and r["recipient_class"] != "unknown"]
        if len(rows) < 30:
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


# ============================================================
# 主流程
# ============================================================
def main():
    print("=== Step 1: 切分家书 ===")
    letters = extract_letters()
    print(f"  切出 {len(letters)} 封")
    print(f"  日期有效: {sum(1 for r in letters if r['year']) } 封")
    print(f"  收信人分布: {dict(Counter(r['recipient_class'] for r in letters))}")
    if letters:
        years = [r['year'] for r in letters if r['year']]
        if years:
            print(f"  年份范围: {min(years)} - {max(years)}")

    print()
    print("=== Step 2: 8 维 + 9 主题评分 ===")
    letters = annotate_scores(letters)
    with (CORPUS / "letters.jsonl").open("w", encoding="utf-8") as f:
        for r in letters:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== Step 3: 4 个 treatment 候选 ITS 扫描 ===")
    all_its = {}
    for t in TREATMENT_CANDIDATES:
        all_its[t] = run_its_all(letters, t)
    (CORPUS / "its_results.json").write_text(
        json.dumps(all_its, ensure_ascii=False, indent=2), encoding="utf-8")
    # 打印每个 treatment 下 D2 / 战事 / 修身 的 t-stat 对比
    print(f"  {'指标':16s}" + "".join(f"  {t}".rjust(15) for t in TREATMENT_CANDIDATES))
    for k in ["D2_自我修正", "D8_三教融合", "军务", "修身", "战事", "湘军"]:
        row = f"  {k:16s}"
        for t in TREATMENT_CANDIDATES:
            r = all_its[t].get(k)
            if r:
                row += f"  β={r['beta2_level_shift']:+6.2f} t={r['t_level_shift']:+5.2f}"
            else:
                row += f"  {'-':>15s}"
        print(row)

    print()
    print("=== Step 4: 散度分析 ===")
    div = run_divergence(letters)
    (CORPUS / "divergence_results.json").write_text(
        json.dumps(div, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  5 时段 4 过渡 JS:")
    for tr in div["transitions"]:
        print(f"    {tr['from']} → {tr['to']}: JS={tr['JS']:.4f}, L1={tr['L1']:.4f}")
    print(f"  二维参照空间 (JS vs 李 / vs 左):")
    for name, c in div["coords"].items():
        print(f"    {name}: JS(李)={c['x_vs_li']:.4f}, JS(左)={c['y_vs_zuo']:.4f}")
    print(f"  Parity check: JS(李, 左) = {div['li_vs_zuo_parity']:.4f}")

    print()
    print("=== Step 5: 断点检测 ===")
    bp = run_breakpoints(letters)
    (CORPUS / "breakpoints.json").write_text(
        json.dumps(bp, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, r in bp.items():
        if r["K"] >= 1:
            bp_y = ",".join(str(b) for b in r["breakpoints_year"])
            means = " → ".join(f"{m['mean']:.2f}" for m in r["seg_means"])
            print(f"  {k:16s} K={r['K']}  断点={bp_y}  段均值={means}")

    print()
    print("=== Step 6: 收信人 FE 回归 ===")
    fe = run_recipient_fe(letters)
    (CORPUS / "genre_fe_results.json").write_text(
        json.dumps(fe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {'维度':18s}  {'naive':>10s}  {'FE':>10s}  {'差':>10s}")
    for k, r in fe.items():
        print(f"  {k:18s}  {r['beta_post_naive']:+10.3f}  {r['beta_post_fe']:+10.3f}  "
              f"{r['diff']:+10.3f}")

    print()
    print(f"=== 输出 ===")
    for f in sorted(CORPUS.glob("*.json*")):
        print(f"  {f}")


if __name__ == "__main__":
    main()
