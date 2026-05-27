"""
personality_scoring.py
对 sushi_main_dated.jsonl 每篇做 8 维人格评分 + 9 主题概念频次统计

输入:
  data/corpus/sushi_main_dated.jsonl  (含 year 字段)

输出:
  data/corpus/sushi_personality.jsonl   每篇逐维评分
  data/corpus/sushi_concept_per_entry.jsonl   每篇逐主题频次
  data/corpus/personality_yearly.json   按年聚合 (仅 high+medium confidence)
  data/corpus/concept_yearly.json       同上, 主题频次

评分规则:
  对每个子维度,统计该篇 text 中相关词频, 除以篇字数, 乘 1000
  → 每千字出现频率作为打分
"""
import json
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import CORE_CONCEPTS, PERSONALITY_DIMENSIONS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IN_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_main_dated.jsonl"
OUT_PERSONALITY = PROJECT_ROOT / "data" / "corpus" / "sushi_personality.jsonl"
OUT_CONCEPT = PROJECT_ROOT / "data" / "corpus" / "sushi_concept_per_entry.jsonl"
OUT_PERSON_YEARLY = PROJECT_ROOT / "data" / "corpus" / "personality_yearly.json"
OUT_CONCEPT_YEARLY = PROJECT_ROOT / "data" / "corpus" / "concept_yearly.json"


def score_text(text, word_lists):
    """对一段 text 计 word_lists 内每个子维度的词频和 (绝对计数)"""
    scores = {}
    for subdim, words in word_lists.items():
        cnt = 0
        for w in words:
            cnt += text.count(w)
        scores[subdim] = cnt
    return scores


def main():
    records = []
    with IN_JSONL.open(encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    print(f"加载 {len(records)} 篇")

    # ---------- 单篇评分 ----------
    person_records = []
    concept_records = []
    for r in records:
        text = r.get("text", "")
        chars = max(r.get("char_count", 0), 1)

        # 8 维评分
        pe = {
            "id": r["id"],
            "year": r.get("year"),
            "year_confidence": r.get("year_confidence"),
            "genre_raw": r.get("genre_raw"),
            "char_count": chars,
        }
        for dim, subdims in PERSONALITY_DIMENSIONS.items():
            sub_scores = score_text(text, subdims)
            # 每子维度: 每千字频
            for sd, cnt in sub_scores.items():
                pe[f"{dim}__{sd}__count"] = cnt
                pe[f"{dim}__{sd}__per1k"] = cnt / chars * 1000
            # 维度总分: 该维度所有子维度 per1k 之和
            pe[f"{dim}__total_per1k"] = sum(
                sub_scores[sd] / chars * 1000 for sd in sub_scores
            )
        person_records.append(pe)

        # 9 主题概念频次
        ce = {
            "id": r["id"],
            "year": r.get("year"),
            "year_confidence": r.get("year_confidence"),
            "genre_raw": r.get("genre_raw"),
            "char_count": chars,
        }
        for theme, words in CORE_CONCEPTS.items():
            cnt = sum(text.count(w) for w in words)
            ce[f"{theme}__count"] = cnt
            ce[f"{theme}__per1k"] = cnt / chars * 1000
        concept_records.append(ce)

    # 写 jsonl
    with OUT_PERSONALITY.open("w", encoding="utf-8") as f:
        for r in person_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with OUT_CONCEPT.open("w", encoding="utf-8") as f:
        for r in concept_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------- 按年聚合 (仅 high + medium) ----------
    DIMS = list(PERSONALITY_DIMENSIONS.keys())
    THEMES = list(CORE_CONCEPTS.keys())

    yearly_person = defaultdict(lambda: {"n_pieces": 0, "total_chars": 0})
    yearly_concept = defaultdict(lambda: {"n_pieces": 0, "total_chars": 0})

    for pe in person_records:
        y = pe.get("year")
        conf = pe.get("year_confidence")
        if not y or conf not in ("high", "medium"):
            continue
        bucket = yearly_person[y]
        bucket["n_pieces"] += 1
        bucket["total_chars"] += pe["char_count"]
        for dim in DIMS:
            key = f"{dim}__total_per1k"
            bucket.setdefault(dim, []).append(pe[key])

    for ce in concept_records:
        y = ce.get("year")
        conf = ce.get("year_confidence")
        if not y or conf not in ("high", "medium"):
            continue
        bucket = yearly_concept[y]
        bucket["n_pieces"] += 1
        bucket["total_chars"] += ce["char_count"]
        for theme in THEMES:
            key = f"{theme}__per1k"
            bucket.setdefault(theme, []).append(ce[key])

    # 聚合 = 字符加权平均
    def aggregate(bucket, keys):
        out = {"n_pieces": bucket["n_pieces"], "total_chars": bucket["total_chars"]}
        for k in keys:
            vals = bucket.get(k, [])
            out[k] = sum(vals) / len(vals) if vals else 0.0
        return out

    person_yearly_out = {
        y: aggregate(b, DIMS)
        for y, b in sorted(yearly_person.items())
    }
    concept_yearly_out = {
        y: aggregate(b, THEMES)
        for y, b in sorted(yearly_concept.items())
    }

    OUT_PERSON_YEARLY.write_text(
        json.dumps(person_yearly_out, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    OUT_CONCEPT_YEARLY.write_text(
        json.dumps(concept_yearly_out, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # ---------- 汇报 ----------
    print()
    print(f"=== 人格评分 ===")
    print(f"  逐篇评分: {len(person_records)} 篇")
    print(f"  按年聚合 (high+medium only): {len(person_yearly_out)} 年")
    print()
    print(f"=== 概念频次 ===")
    print(f"  逐篇: {len(concept_records)} 篇")
    print(f"  按年聚合 (high+medium only): {len(concept_yearly_out)} 年")
    print()
    print(f"=== treatment 年附近样本 (pre 1075-1078, treatment 1079, post 1080-1083) ===")
    for y in sorted([1075, 1076, 1077, 1078, 1079, 1080, 1081, 1082, 1083]):
        if y in person_yearly_out:
            row = person_yearly_out[y]
            print(f"  {y}  n={row['n_pieces']:3d}  D6 情感深度={row['D6_情感深度']:.2f}  "
                  f"D7 隐逸={row['D7_隐逸倾向']:.2f}  D8 三教={row['D8_三教融合']:.2f}")

    print()
    print(f"输出:")
    print(f"  {OUT_PERSONALITY}")
    print(f"  {OUT_CONCEPT}")
    print(f"  {OUT_PERSON_YEARLY}")
    print(f"  {OUT_CONCEPT_YEARLY}")


if __name__ == "__main__":
    main()
