"""
extract_with_period.py
顾炎武诗集按卷次推断编年 (5 卷天然时序), 5 时段切分:

  P1 卷一 1644-1650  易代初期 (31-37 岁)
  P2 卷二 1651-1659  江南游历 (38-46 岁)
  P3 卷三 1660-1666  山东游历 (47-53 岁)
  P4 卷四 1667-1674  山西游历 (54-61 岁)
  P5 卷五 1675-1682  晚年至卒 (62-69 岁)

treatment 候选:
  1660 北上 (P2→P3 切换), 易代后 16 年, 延迟反思型
  1667 中年 (P3→P4)
  1675 晚年 (P4→P5)
"""
import json
import re
import math
import sys
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import PERSONALITY_DIMENSIONS, CORE_CONCEPTS, all_concepts_flat

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_corpus"
CORPUS = ROOT / "data" / "corpus"

PERIOD_INFO = {
    "P1_易代初期": {"vol": "卷之一", "year_mid": 1647, "year_range": (1644, 1650)},
    "P2_江南游历": {"vol": "卷之二", "year_mid": 1655, "year_range": (1651, 1659)},
    "P3_山东游历": {"vol": "卷之三", "year_mid": 1663, "year_range": (1660, 1666)},
    "P4_山西游历": {"vol": "卷之四", "year_mid": 1670, "year_range": (1667, 1674)},
    "P5_晚年至卒": {"vol": "卷之五", "year_mid": 1678, "year_range": (1675, 1682)},
}


def extract_poems_with_period():
    """诗集按 5 卷切分 + 每首诗打 period 标签 + year_mid"""
    text = (RAW / "gu_main" / "顾亭林诗文集.txt").read_text(encoding="utf-8")
    lines = text.split("\n")

    # 找各卷起始位置
    vol_positions = {}
    for i, line in enumerate(lines):
        for period, info in PERIOD_INFO.items():
            if f"●亭林诗集{info['vol']}" in line:
                vol_positions[period] = i

    if len(vol_positions) < 5:
        print(f"  警告: 只找到 {len(vol_positions)} 个卷")
        return []

    sorted_periods = sorted(vol_positions, key=vol_positions.get)
    records = []
    rec_idx = 1

    for i, period in enumerate(sorted_periods):
        start = vol_positions[period] + 1
        end = vol_positions[sorted_periods[i+1]] if i+1 < len(sorted_periods) else len(lines)
        info = PERIOD_INFO[period]

        # 切诗题 + 诗内容
        # 卷内格式: 一行"诗题" (短, < 35 字, 无标点) + 多行诗正文
        current_title = None
        current_body = []

        def flush():
            nonlocal current_title, current_body, rec_idx
            if current_title and current_body:
                body = "\n".join(current_body).strip()
                chars = len(re.findall(r"[一-鿿]", body))
                if chars >= 5:
                    records.append({
                        "id": f"poem_{rec_idx:04d}",
                        "source": "顾亭林诗集",
                        "period": period,
                        "year": info["year_mid"],
                        "year_range": info["year_range"],
                        "title": current_title,
                        "char_count": chars,
                        "text": body[:5000],
                    })
                    rec_idx += 1
            current_title = None
            current_body = []

        for j in range(start, end):
            s = lines[j].strip().lstrip("　").strip()
            if not s:
                continue
            # 短行无标点 = 标题
            if len(s) < 35 and not any(c in s for c in "。，？！；："):
                flush()
                current_title = s
            elif current_title:
                current_body.append(s)
        flush()

    return records


def extract_essays():
    """文集按卷切分, 不打编年标签"""
    text = (RAW / "gu_main" / "顾亭林诗文集.txt").read_text(encoding="utf-8")
    # 简化: 直接抽全文按行扫描, 找 "●亭林文集卷一" 等 5 卷
    lines = text.split("\n")
    vol_re = re.compile(r"●亭林文集卷之[一二三四五六七八九十]+")
    vol_positions = []
    for i, line in enumerate(lines):
        if vol_re.search(line):
            vol_positions.append((i, line.strip()))

    if not vol_positions:
        return []

    records = []
    rec_idx = 1
    for idx, (start, label) in enumerate(vol_positions):
        end = vol_positions[idx+1][0] if idx+1 < len(vol_positions) else len(lines)
        current_title = None
        current_body = []

        def flush():
            nonlocal current_title, current_body, rec_idx
            if current_title and current_body:
                body = "\n".join(current_body).strip()
                chars = len(re.findall(r"[一-鿿]", body))
                if chars >= 30:
                    records.append({
                        "id": f"essay_{rec_idx:04d}",
                        "source": "顾亭林文集",
                        "volume": label,
                        "title": current_title,
                        "char_count": chars,
                        "text": body[:10000],
                    })
                    rec_idx += 1
            current_title = None
            current_body = []

        for j in range(start+1, end):
            s = lines[j].strip().lstrip("　").strip()
            if not s:
                continue
            if len(s) < 40 and not any(c in s for c in "。，？！；："):
                flush()
                current_title = s
            elif current_title:
                current_body.append(s)
        flush()

    return records


def annotate(records):
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


def its_ols(years, vals, treatment_year):
    y = np.array(vals, dtype=float)
    t = np.array(years, dtype=float)
    D = (t >= treatment_year + 1).astype(float)
    t_post = np.where(D == 1, t - treatment_year, 0)
    X = np.column_stack([np.ones_like(t), t - 1644, D, t_post])
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
    }


def run_its_poems(poems, treatment_year):
    """诗集按 period 中年聚合, 跑 ITS"""
    by_period = defaultdict(list)
    for r in poems:
        by_period[r["period"]].append(r)
    keys = list(PERSONALITY_DIMENSIONS) + list(CORE_CONCEPTS)
    out = {}
    for k in keys:
        keyl = f"{k}_per1k"
        # 每 period 取均值, x = year_mid
        pts = []
        for period in sorted(PERIOD_INFO):
            sub = by_period.get(period, [])
            if not sub:
                continue
            vals = [r[keyl] for r in sub if keyl in r]
            if not vals:
                continue
            pts.append((PERIOD_INFO[period]["year_mid"], float(np.mean(vals))))
        if len(pts) < 4:
            continue
        years = [p[0] for p in pts]
        vals = [p[1] for p in pts]
        r = its_ols(years, vals, treatment_year)
        if r:
            out[k] = r
    return out


def main():
    print("=== Step 1: 诗集按 5 卷切分 + 5 时段编年 ===")
    poems = extract_poems_with_period()
    print(f"  得 {len(poems)} 首诗")
    pd_dist = Counter(r["period"] for r in poems)
    for p in sorted(PERIOD_INFO):
        n = pd_dist.get(p, 0)
        info = PERIOD_INFO[p]
        print(f"  {p:18s} ({info['year_range'][0]}-{info['year_range'][1]}): {n:3d} 首")
    poems = annotate(poems)
    with (CORPUS / "gu_poems_period.jsonl").open("w", encoding="utf-8") as f:
        for r in poems:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== Step 2: 文集切分 (不编年) ===")
    essays = extract_essays()
    print(f"  得 {len(essays)} 篇")
    essays = annotate(essays)
    with (CORPUS / "gu_essays.jsonl").open("w", encoding="utf-8") as f:
        for r in essays:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== Step 3: ITS 三个 treatment 候选 (诗集 5 时段) ===")
    print(f"  {'目标':16s}  {'1660 北上':>16s}  {'1667 中年':>16s}  {'1675 晚年':>16s}")
    all_its = {}
    for t in [1660, 1667, 1675]:
        all_its[t] = run_its_poems(poems, t)
    for k in ["D2_自我修正", "D6_情感深度", "D7_隐逸倾向", "D8_三教融合",
              "易代", "故国", "兵事", "隐遁"]:
        row = f"  {k:16s}"
        for t in [1660, 1667, 1675]:
            r = all_its[t].get(k)
            if r:
                row += f"   β={r['beta2']:+6.2f} t={r['t_stat']:+5.2f}"
            else:
                row += f"   {'-':>16s}"
        print(row)
    (CORPUS / "its_poems.json").write_text(
        json.dumps(all_its, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=== Step 4: 5 时段散度 (4 过渡) ===")
    by_period_text = defaultdict(str)
    for r in poems:
        by_period_text[r["period"]] += r["text"]
    concepts = all_concepts_flat()

    def text_dist(t):
        c = {w: t.count(w) for w in concepts}
        tot = sum(c.values())
        return {w: c[w]/tot if tot else 0 for w in c}

    def js(p, q):
        m = {w: (p[w]+q[w])/2 for w in p}
        def kl(a, b):
            return sum(a[w]*math.log2(a[w]/b[w]) for w in a if a[w]>0 and b[w]>0)
        return 0.5*kl(p, m) + 0.5*kl(q, m)

    pd_ = {p: text_dist(by_period_text[p]) for p in PERIOD_INFO if by_period_text.get(p)}
    period_names = sorted(PERIOD_INFO)
    print(f"  {'过渡':30s} {'JS':>8s}")
    transitions = []
    for i in range(len(period_names)-1):
        a, b = period_names[i], period_names[i+1]
        if a in pd_ and b in pd_:
            js_val = js(pd_[a], pd_[b])
            transitions.append({"from": a, "to": b, "JS": js_val})
            print(f"  {a} → {b}: {js_val:.4f}")
    (CORPUS / "divergence_poems.json").write_text(
        json.dumps(transitions, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
