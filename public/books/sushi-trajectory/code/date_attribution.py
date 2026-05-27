"""
date_attribution.py
给 sushi_main.jsonl 的每篇填 year / year_confidence

三方推断:
  1. 年谱提及匹配: 年谱 raw_text 用《》标出的诗文题,与 sushi_main 篇题做模糊匹配
     → year_confidence='high'
  2. 篇题干支匹配: 篇题含"辛丑/壬寅/丙午"等天干地支 → 公历年
     → year_confidence='high'
  3. 卷次众数推断: 苏轼集卷大致按时序排,每卷取已匹配篇目的众数年作为该卷剩余篇目的估计
     → year_confidence='medium'

未匹配的篇目 year=None, year_confidence=None。

输出:
  data/corpus/sushi_main_dated.jsonl
  data/corpus/date_attribution_stats.json
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IN_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_main.jsonl"
BIO_JSON = PROJECT_ROOT / "data" / "corpus" / "sushi_biography.json"
OUT_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_main_dated.jsonl"
OUT_STATS = PROJECT_ROOT / "data" / "corpus" / "date_attribution_stats.json"

# 干支 → 公历起始年 (60 年循环,苏轼活在 1037-1101 这个 65 年窗口内)
# 计算: 1037 = 丁丑, 所以 60 年循环里 1037-1101 干支序如下
GANZHI = ["甲子","乙丑","丙寅","丁卯","戊辰","己巳","庚午","辛未","壬申","癸酉",
          "甲戌","乙亥","丙子","丁丑","戊寅","己卯","庚辰","辛巳","壬午","癸未",
          "甲申","乙酉","丙戌","丁亥","戊子","己丑","庚寅","辛卯","壬辰","癸巳",
          "甲午","乙未","丙申","丁酉","戊戌","己亥","庚子","辛丑","壬寅","癸卯",
          "甲辰","乙巳","丙午","丁未","戊申","己酉","庚戌","辛亥","壬子","癸丑",
          "甲寅","乙卯","丙辰","丁巳","戊午","己未","庚申","辛酉","壬戌","癸亥"]

# 苏轼生命窗口里所有干支 → 年份
SUSHI_WINDOW_YEARS = list(range(1037, 1102))


def ganzhi_to_years_in_sushi_window(gz):
    """干支 → 苏轼生命窗口内的所有可能公历年"""
    # 1037=丁丑 → index in GANZHI
    base_year = 1037
    base_idx = GANZHI.index("丁丑")  # = 13
    candidates = []
    for y in SUSHI_WINDOW_YEARS:
        idx = (base_idx + y - base_year) % 60
        if GANZHI[idx] == gz:
            candidates.append(y)
    return candidates


# 加载年谱
bio = json.load(BIO_JSON.open(encoding="utf-8"))
bio_by_year = {r["year"]: r for r in bio if r.get("year")}


def normalize_title(t):
    """归一化篇题: 去标点 / 空白 / 全角"""
    if not t:
        return ""
    t = re.sub(r"[，。！？；：、,.!?;:\s　\(\)（）【】「」\"\'·]", "", t)
    t = re.sub(r"[一二三四五六七八九十百千万首]+$", "", t)  # 去末尾的"五首/七首"等
    return t


def extract_mentioned_titles_from_bio():
    """
    从年谱 raw_text 用《》抽取所有提及篇目, 返回 {year: [title1, title2, ...]}
    """
    mentions = defaultdict(list)
    for year, rec in bio_by_year.items():
        text = rec.get("raw_text", "")
        for m in re.finditer(r"《([^《》]{2,60})》", text):
            title = m.group(1).strip()
            mentions[year].append(title)
    return mentions


def title_match(sushi_title_norm, bio_title_norm):
    """简单包含式匹配: 一方含另一方的前 6 字以上视为匹配"""
    if not sushi_title_norm or not bio_title_norm:
        return False
    short, long = (sushi_title_norm, bio_title_norm) if len(sushi_title_norm) < len(bio_title_norm) else (bio_title_norm, sushi_title_norm)
    if len(short) < 4:
        return short == long  # 太短的需完全相等
    # 短的核心 (前 4-6 字) 在长的里出现
    core_len = min(6, len(short))
    return short[:core_len] in long


def main():
    # ---------- 加载 sushi_main ----------
    records = []
    with IN_JSONL.open(encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    print(f"加载 {len(records)} 篇")

    # ---------- 第一遍: 干支匹配 ----------
    GANZHI_PATTERN = re.compile("(" + "|".join(GANZHI) + ")")
    dated_by_ganzhi = 0
    for r in records:
        title = r.get("title", "")
        m = GANZHI_PATTERN.search(title)
        if m:
            gz = m.group(1)
            candidates = ganzhi_to_years_in_sushi_window(gz)
            if len(candidates) == 1:
                r["year"] = candidates[0]
                r["year_confidence"] = "high"
                r["year_source"] = "ganzhi"
                dated_by_ganzhi += 1
            elif len(candidates) > 1:
                # 多候选: 留待第二轮 (用年谱或卷次缩小)
                r["_ganzhi_candidates"] = candidates

    print(f"  干支匹配填上: {dated_by_ganzhi} 篇")

    # ---------- 第二遍: 年谱《》提及匹配 ----------
    mentions_by_year = extract_mentioned_titles_from_bio()
    print(f"  年谱提及篇目 (按年统计):")
    total_mentions = sum(len(v) for v in mentions_by_year.values())
    print(f"    总计 {total_mentions} 处提及, 跨 {len(mentions_by_year)} 年")

    # 预归一
    norm_records = [(r, normalize_title(r.get("title", ""))) for r in records]
    dated_by_bio = 0
    for year, titles in mentions_by_year.items():
        for bio_t in titles:
            bio_t_norm = normalize_title(bio_t)
            if len(bio_t_norm) < 4:
                continue
            for r, sushi_norm in norm_records:
                if r.get("year"):
                    continue
                if title_match(sushi_norm, bio_t_norm):
                    # 干支候选若与年谱年冲突,以年谱为准
                    if "_ganzhi_candidates" in r and year not in r["_ganzhi_candidates"]:
                        continue
                    r["year"] = year
                    r["year_confidence"] = "high"
                    r["year_source"] = "biography_mention"
                    r["_matched_bio_title"] = bio_t
                    dated_by_bio += 1
                    break
    print(f"  年谱《》匹配填上: {dated_by_bio} 篇")

    # ---------- 第三遍: 干支多候选 + 卷次惯例 → 卷众数 ----------
    # 收集每卷已 high-confidence 年的分布
    vol_year_dist = defaultdict(Counter)
    for r in records:
        v = r.get("volume")
        if v and r.get("year") and r.get("year_confidence") == "high":
            vol_year_dist[v][r["year"]] += 1

    # 干支多候选: 选与卷众数最近的
    resolved_ganzhi = 0
    for r in records:
        if r.get("year"):
            continue
        if "_ganzhi_candidates" in r:
            v = r.get("volume")
            if v and vol_year_dist.get(v):
                mode_year = vol_year_dist[v].most_common(1)[0][0]
                best = min(r["_ganzhi_candidates"], key=lambda y: abs(y - mode_year))
                r["year"] = best
                r["year_confidence"] = "medium"
                r["year_source"] = "ganzhi_resolved_by_volume"
                resolved_ganzhi += 1
            else:
                # 没卷众数 → 取候选中最居中的
                cands = r["_ganzhi_candidates"]
                r["year"] = cands[len(cands)//2]
                r["year_confidence"] = "low"
                r["year_source"] = "ganzhi_ambiguous"
                resolved_ganzhi += 1
    print(f"  干支多候选解决: {resolved_ganzhi} 篇")

    # ---------- 第四遍: 卷次众数 → 整卷未编年篇目 ----------
    # 重新算 vol_year_dist (含 medium)
    vol_year_dist_all = defaultdict(Counter)
    for r in records:
        v = r.get("volume")
        if v and r.get("year"):
            vol_year_dist_all[v][r["year"]] += 1

    # 卷次众数推断只对"时序体裁"(诗/词)用; 尺牍/奏议/题跋是按类编不按年编
    TIME_ORDERED_GENRES = {"诗", "词", "赋"}
    by_volume = 0
    for r in records:
        if r.get("year"):
            continue
        if r.get("genre_raw") not in TIME_ORDERED_GENRES:
            continue
        v = r.get("volume")
        if v and vol_year_dist_all.get(v):
            # 仅当本卷已有 2+ anchors 支持同一年,才外推
            top = vol_year_dist_all[v].most_common(3)
            if top[0][1] >= 3:
                r["year"] = top[0][0]
                r["year_confidence"] = "medium"
                r["year_source"] = "volume_mode"
                by_volume += 1
            elif top[0][1] == 2:
                r["year"] = top[0][0]
                r["year_confidence"] = "low"
                r["year_source"] = "volume_weak_mode"
                by_volume += 1
    print(f"  卷次众数推断 (仅诗/词/赋): {by_volume} 篇")

    # ---------- 清理临时字段 + 写出 ----------
    for r in records:
        r.pop("_ganzhi_candidates", None)

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------- 统计 ----------
    conf_dist = Counter(r.get("year_confidence") or "null" for r in records)
    src_dist = Counter(r.get("year_source") or "none" for r in records)
    year_dist = Counter(r["year"] for r in records if r.get("year"))
    stats = {
        "total": len(records),
        "dated": sum(1 for r in records if r.get("year")),
        "by_confidence": dict(conf_dist),
        "by_source": dict(src_dist),
        "year_min_max": [min(year_dist), max(year_dist)] if year_dist else None,
        "year_distribution_summary": {
            y: year_dist[y] for y in sorted(year_dist.keys())
        }
    }
    OUT_STATS.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    dated = stats["dated"]
    total = stats["total"]
    print()
    print(f"=== 编年回填汇总 ===")
    print(f"  总篇目: {total}")
    print(f"  已编年: {dated} ({dated/total*100:.1f}%)")
    print(f"  confidence 分布: {dict(conf_dist)}")
    print(f"  source 分布: {dict(src_dist)}")
    print(f"  年份范围: {stats['year_min_max']}")
    print()
    print(f"=== 按年篇目数 (前 10 个最多年) ===")
    for y, n in year_dist.most_common(10):
        print(f"  {y}  {n:4d} 篇")
    print()
    print(f"输出: {OUT_JSONL}")
    print(f"     {OUT_STATS}")


if __name__ == "__main__":
    main()
