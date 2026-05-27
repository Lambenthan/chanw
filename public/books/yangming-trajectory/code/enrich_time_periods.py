"""
给 chuanxilu.jsonl 每条增加 time_period (T1-T6) 和 year_range 字段.

时段划分依据:
  - 学界公认的传习录三卷成书时间
  - 各记录者 / 收信人在阳明门下的活动时间
  - 钱德洪《阳明先生年谱》交叉校对

注意: 时段之间存在年份重叠 (例如 T2 陆澄期 1515-1521 与 T3 薛侃期 1519-1522),
这是传习录编纂方式决定的, 不同学生在同一年份都在记录, 无法消除.
"""

import json
from pathlib import Path

# 章节 → (时段编号, 阳明年龄区间, 年份范围, 简要说明)
CHAPTER_TO_PERIOD = {
    "徐爱录":        ("T1", "41-46", "1512-1517", "龙场归来初期讲学, 徐爱 1517 早逝"),
    "陆澄录":        ("T2", "44-50", "1515-1521", "滁州/南京讲学, 思想成型"),
    "薛侃录":        ("T3", "48-51", "1519-1522", "江西讲学 + 平宁王之乱(1519)"),
    "答顾东桥书":     ("T4", "53-54", "1525",      "嘉靖四年答顾璘信"),
    "答周道通书":     ("T4", "53-55", "1525-1526", ""),
    "答陆原静书":     ("T4", "50-51", "1521-1522", ""),
    "又(答陆原静)":   ("T4", "50-52", "1521-1523", ""),
    "答欧阳崇一":     ("T4", "52-53", "1524",      ""),
    "答罗整庵少宰书": ("T4", "53-54", "1525",      ""),
    "答聂文蔚一":     ("T4", "54-55", "1526",      ""),
    "答聂文蔚二":     ("T4", "55-56", "1527",      ""),
    "训蒙大意示教读刘伯颂等": ("T4", "47", "1518", "赣州时期儿童教育"),
    "教约":          ("T4", "47",    "1518",      "赣州时期"),
    "陈九川录":       ("T5", "44-54", "1515-1525", "正德乙亥(1515)初见至嘉靖间"),
    "黄直录":         ("T5", "53-57", "1524-1528", "黄直 1524 进士入门"),
    "黄修易录":       ("T5", "53-57", "1524-1528", ""),
    "黄省曾录":       ("T6", "50-57", "1521-1528", "含 1527 天泉证道四句教"),
    "黄以方录":       ("T6", "55-57", "1526-1528", "晚年记录"),
}

# 时段元数据 (展示用)
PERIOD_META = {
    "T1": {"name": "徐爱期",       "year_min": 1512, "year_max": 1517, "age_min": 41, "age_max": 46},
    "T2": {"name": "陆澄期",       "year_min": 1515, "year_max": 1521, "age_min": 44, "age_max": 50},
    "T3": {"name": "薛侃期",       "year_min": 1519, "year_max": 1522, "age_min": 48, "age_max": 51},
    "T4": {"name": "卷中书信期",   "year_min": 1518, "year_max": 1527, "age_min": 47, "age_max": 56},
    "T5": {"name": "中后期门人录", "year_min": 1515, "year_max": 1528, "age_min": 44, "age_max": 57},
    "T6": {"name": "晚年定型期",   "year_min": 1521, "year_max": 1528, "age_min": 50, "age_max": 57},
}


def main():
    ROOT = Path(__file__).resolve().parent.parent
    src = ROOT / "data" / "corpus" / "chuanxilu_343_raw.jsonl"
    dst = ROOT / "data" / "corpus" / "chuanxilu_343.jsonl"

    records = [json.loads(line) for line in src.open(encoding="utf-8")]
    for r in records:
        ch = r["chapter"]
        if ch not in CHAPTER_TO_PERIOD:
            raise ValueError(f"未映射章节: {ch}")
        period, ages, yr_range, note = CHAPTER_TO_PERIOD[ch]
        r["time_period"]      = period
        r["age_range"]        = ages
        r["year_range"]       = yr_range
        r["period_note"]      = note

    with dst.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 同时存 period meta
    meta_path = ROOT / "data" / "analysis" / "period_meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(PERIOD_META, f, ensure_ascii=False, indent=2)

    # 打印分布
    from collections import Counter
    cnt = Counter(r["time_period"] for r in records)
    print("时段分布:")
    for p in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        meta = PERIOD_META[p]
        chars = sum(r["char_count"] for r in records if r["time_period"] == p)
        print(f"  {p} {meta['name']:6s} ({meta['year_min']}-{meta['year_max']}, {meta['age_min']}-{meta['age_max']}岁): "
              f"{cnt[p]:3d} 条, {chars:>6,} 字")

    print(f"\n输出: {dst}")
    print(f"      {meta_path}")


if __name__ == "__main__":
    main()
