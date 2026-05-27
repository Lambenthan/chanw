"""探针实验 Step 4: T3→T4 关键过渡的细节展开

T3→T4 是 5 个过渡里 L1 最大、新/退概念最多的一次.
本步具体看:
  - 致良知首次出现的具体条目, 上下文是什么
  - 人欲退场的具体表现 (T3 还在哪些条目里高频出现, T4 几乎不见)
  - 朱子从 T2-T3 沉默到 T4 重新被点名, 具体语境
  - 训蒙大意 + 教约 (1518) 这两篇早期写作要不要从 T4 里剥离出来重看
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
records = [json.loads(line) for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8")]

TARGET_CONCEPTS = ["致良知", "良知", "人欲", "天理", "朱子", "克己", "先儒", "格物"]

def find_entries_with(concept, period_filter=None):
    hits = []
    for r in records:
        if period_filter and r["time_period"] not in period_filter:
            continue
        if concept in r["text"]:
            hits.append(r)
    return hits

# ============================================================================
# (1) 致良知首次出现的条目 —— 全语料扫描
# ============================================================================
print("=" * 70)
print("发现 1: '致良知'三字组合的全语料首次出现条目")
print("=" * 70)
hits = find_entries_with("致良知")
for r in hits[:3]:
    print(f"\n[第 {r['item_no']} 条]  {r['time_period']} {r['chapter']} ({r['recorder_or_addressee']}, {r['year_range']})")
    pos = r["text"].find("致良知")
    ctx = r["text"][max(0, pos-30):pos+60]
    print(f"  ...{ctx}...")

print(f"\n  总共出现条目数: {len(hits)}")
by_period = {}
for r in hits:
    by_period.setdefault(r["time_period"], []).append(r["item_no"])
for p, items in sorted(by_period.items()):
    print(f"  {p}: {len(items)} 条 (#{min(items)}–#{max(items)})")

# ============================================================================
# (2) T3 与 T4 各自的"人欲"出现 — 看消失的发生
# ============================================================================
print("\n" + "=" * 70)
print("发现 2: '人欲'在 T3 和 T4 的对比")
print("=" * 70)
for period in ["T3", "T4"]:
    hits = find_entries_with("人欲", [period])
    n_total = sum(1 for r in records if r["time_period"] == period)
    total_count = sum(r["text"].count("人欲") for r in hits)
    print(f"\n{period}: {len(hits)} / {n_total} 条提到 '人欲', 共 {total_count} 次")
    for r in hits[:2]:
        pos = r["text"].find("人欲")
        ctx = r["text"][max(0, pos-25):pos+45]
        print(f"  [#{r['item_no']}] ...{ctx}...")

# ============================================================================
# (3) '朱子'在三个时段被点名的语境差异
# ============================================================================
print("\n" + "=" * 70)
print("发现 3: '朱子'被点名的时段与语境")
print("=" * 70)
for period in ["T1", "T2", "T3", "T4"]:
    hits = find_entries_with("朱子", [period])
    total = sum(r["text"].count("朱子") for r in hits)
    n_total = sum(1 for r in records if r["time_period"] == period)
    print(f"\n{period}: {len(hits)} / {n_total} 条提到 '朱子', 共 {total} 次")
    for r in hits[:2]:
        pos = r["text"].find("朱子")
        ctx = r["text"][max(0, pos-25):pos+50]
        print(f"  [#{r['item_no']}] ...{ctx}...")

# ============================================================================
# (4) T4 内部细分: 训蒙大意 + 教约 (1518) vs 答顾东桥等书信 (1521+)
# ============================================================================
print("\n" + "=" * 70)
print("发现 4: T4 内部细分 (1518 早期 vs 1521+ 致良知后)")
print("=" * 70)

EARLY_CHAPTERS = ["训蒙大意示教读刘伯颂等", "教约"]
LATE_CHAPTERS = ["答顾东桥书", "答周道通书", "答陆原静书", "又(答陆原静)",
                 "答欧阳崇一", "答罗整庵少宰书", "答聂文蔚一", "答聂文蔚二"]

def stats_for(period, chapters, concepts):
    recs = [r for r in records if r["time_period"] == period and r["chapter"] in chapters]
    chars = sum(r["char_count"] for r in recs)
    print(f"\n{period} 子集 ({', '.join(chapters[:2])}...): {len(recs)} 条, {chars:,} 字")
    if chars == 0:
        return
    for c in concepts:
        cnt = sum(r["text"].count(c) for r in recs)
        per_kc = cnt / chars * 1000
        print(f"  {c:<6}: {cnt:>3} 次  ({per_kc:.2f} /千字)")

stats_for("T4", EARLY_CHAPTERS, TARGET_CONCEPTS)
stats_for("T4", LATE_CHAPTERS, TARGET_CONCEPTS)
