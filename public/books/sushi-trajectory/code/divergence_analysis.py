"""
divergence_analysis.py
苏轼 6 时段内部散度 + 苏轼 vs 王安石/黄庭坚 二维参照空间

输入:
  data/corpus/sushi_main_dated.jsonl  (含 year + concept 词)
  data/raw_corpus/wang_anshi/临川文集.txt
  data/raw_corpus/huang_tingjian/山谷全集.txt
  data/raw_corpus/huang_tingjian/山谷诗注.txt

策略:
  1. 苏轼 6 时段 P1-P6 内部散度 (5 个过渡)
  2. 苏轼每时段 vs 王安石全集的 JS 散度 (二维 X 轴)
  3. 苏轼每时段 vs 黄庭坚全集的 JS 散度 (二维 Y 轴)
  4. 概念基底: concept_vocabulary.py 中的 56 个核心概念
  5. 全部用每千字频率作为分布
"""
import json
import math
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import CORE_CONCEPTS, all_concepts_flat

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATED_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_main_dated.jsonl"
WANG = PROJECT_ROOT / "data" / "raw_corpus" / "wang_anshi" / "临川文集.txt"
HUANG_QUANJI = PROJECT_ROOT / "data" / "raw_corpus" / "huang_tingjian" / "山谷全集.txt"
HUANG_SHIZHU = PROJECT_ROOT / "data" / "raw_corpus" / "huang_tingjian" / "山谷诗注.txt"

OUT = PROJECT_ROOT / "data" / "corpus" / "divergence_results.json"

# 6 时段切分
PERIODS = {
    "P1_早年": (1057, 1070),
    "P2_反新法": (1071, 1078),
    "P3_乌台后黄州": (1080, 1084),
    "P4_元祐起复": (1086, 1093),
    "P5_惠州": (1094, 1096),
    "P6_儋州与北归": (1097, 1101),
}

CONCEPTS = all_concepts_flat()


def text_to_concept_dist(text, concepts):
    """文本 → 概念频率分布 (按总词频归一化)"""
    counts = {c: text.count(c) for c in concepts}
    total = sum(counts.values())
    if total == 0:
        return {c: 0.0 for c in concepts}
    return {c: counts[c] / total for c in counts}


def js_divergence(p, q):
    """Jensen-Shannon 散度, base 2, 范围 [0, 1]"""
    m = {c: (p[c] + q[c]) / 2 for c in p}
    def kl(a, b):
        s = 0.0
        for c in a:
            if a[c] > 0 and b[c] > 0:
                s += a[c] * math.log2(a[c] / b[c])
        return s
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def l1_divergence(p, q):
    """L1 距离, 范围 [0, 2]"""
    return sum(abs(p[c] - q[c]) for c in p)


def main():
    # ---------- 加载苏轼 corpus 按时段聚合 ----------
    period_texts = defaultdict(str)
    n_pieces = defaultdict(int)
    with DATED_JSONL.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            y = r.get("year")
            conf = r.get("year_confidence")
            if not y or conf not in ("high", "medium", "low"):
                continue
            for name, (lo, hi) in PERIODS.items():
                if lo <= y <= hi:
                    period_texts[name] += r.get("text", "")
                    n_pieces[name] += 1
                    break

    # ---------- 计算各时段概念分布 ----------
    period_dist = {name: text_to_concept_dist(period_texts[name], CONCEPTS)
                   for name in PERIODS}

    for name in PERIODS:
        n = n_pieces[name]
        char_total = len(period_texts[name])
        print(f"  {name:18s}  n_pieces={n:4d}  字数={char_total:>8d}")

    # ---------- 外部对照 ----------
    wang_text = WANG.read_text(encoding="utf-8", errors="replace")
    huang_text = HUANG_QUANJI.read_text(encoding="utf-8", errors="replace") \
                 + HUANG_SHIZHU.read_text(encoding="utf-8", errors="replace")
    wang_dist = text_to_concept_dist(wang_text, CONCEPTS)
    huang_dist = text_to_concept_dist(huang_text, CONCEPTS)
    print(f"  王安石(临川文集) 字数: {len(wang_text):,}")
    print(f"  黄庭坚(山谷全集+诗注) 字数: {len(huang_text):,}")

    # ---------- 内部 5 个过渡 (P1→P2, P2→P3, ..., P5→P6) ----------
    period_names = list(PERIODS.keys())
    print()
    print(f"=== 苏轼内部 5 个过渡的 JS / L1 散度 ===")
    transitions = []
    for i in range(len(period_names) - 1):
        a, b = period_names[i], period_names[i+1]
        js = js_divergence(period_dist[a], period_dist[b])
        l1 = l1_divergence(period_dist[a], period_dist[b])
        transitions.append({"from": a, "to": b, "JS": js, "L1": l1})
        print(f"  {a} → {b}")
        print(f"    JS={js:.4f}, L1={l1:.4f}")

    # ---------- 二维参照空间: 每时段 (距王, 距黄) ----------
    print()
    print(f"=== 二维参照空间: 苏轼每时段 vs (王安石, 黄庭坚) ===")
    print(f"  {'时段':18s}  {'JS(vs王)':>10s}  {'JS(vs黄)':>10s}  {'差':>8s}")
    coords = {}
    for name in period_names:
        js_w = js_divergence(period_dist[name], wang_dist)
        js_h = js_divergence(period_dist[name], huang_dist)
        coords[name] = {"x_vs_wang": js_w, "y_vs_huang": js_h, "diff": js_w - js_h}
        print(f"  {name:18s}  {js_w:10.4f}  {js_h:10.4f}  {js_w - js_h:+8.4f}")

    # ---------- 王安石 vs 黄庭坚 (parity check) ----------
    js_wh = js_divergence(wang_dist, huang_dist)
    print()
    print(f"=== Parity check: 王安石 vs 黄庭坚 JS={js_wh:.4f}")

    # ---------- 输出 ----------
    out_data = {
        "periods": {name: {
            "n_pieces": n_pieces[name],
            "char_total": len(period_texts[name]),
            "concept_dist": period_dist[name],
        } for name in period_names},
        "transitions": transitions,
        "coords_vs_wh": coords,
        "wang_vs_huang": js_wh,
        "wang_dist": wang_dist,
        "huang_dist": huang_dist,
    }
    OUT.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 关键概念演化追踪 ----------
    print()
    print(f"=== 关键概念在 6 时段的演化 (千字频率) ===")
    KEY_CONCEPTS = ["新法", "归", "闲", "老", "病", "禅", "佛", "道", "玄",
                    "黄州", "东坡", "海南", "归田"]
    print(f"  概念  " + "  ".join(f"{n[:6]:>6s}" for n in period_names))
    for c in KEY_CONCEPTS:
        if c not in CONCEPTS:
            continue
        per1k_row = []
        for name in period_names:
            count = period_texts[name].count(c)
            chars = max(len(period_texts[name]), 1)
            per1k_row.append(count / chars * 1000)
        row_str = "  ".join(f"{v:>6.2f}" for v in per1k_row)
        print(f"  {c:5s}  {row_str}")

    print()
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
