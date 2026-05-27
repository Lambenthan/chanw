"""
parse_wutai_timeline.py
将《东坡乌台诗案》(朋九万 撰, 宋本) 解析为 wutai_timeline.json

输入: data/raw_corpus/sushi_meta/东坡乌台诗案.txt
输出: data/corpus/wutai_timeline.json + wutai_documents.jsonl

wutai_timeline.json 字段:
[
  {
    "date":      "1079-07-04",
    "lunar":     "元丰二年七月四日",
    "agent":     "御史台 / 中书",
    "action":    "中书批送下何大正札子",
    "doc_id":    "doc_01",
    "raw_context": "...原文片段..."
  },
  ...
]

wutai_documents.jsonl: 每个札子/状作为独立文档
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw_corpus" / "sushi_meta" / "东坡乌台诗案.txt"
OUT_DIR = PROJECT_ROOT / "data" / "corpus"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_TIMELINE = OUT_DIR / "wutai_timeline.json"
OUT_DOCS = OUT_DIR / "wutai_documents.jsonl"

CN_NUM = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
          "廿": 20, "卅": 30}


def cn_day_to_int(s):
    """中文日期数字 → 阿拉伯, 支持 '二十七' '廿三' '十二' 等"""
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("廿"):
        return 20 + (CN_NUM.get(s[1], 0) if len(s) > 1 else 0)
    if s.startswith("十"):
        return 10 + (CN_NUM.get(s[1], 0) if len(s) > 1 else 0)
    if "十" in s:
        parts = s.split("十")
        tens = CN_NUM.get(parts[0], 0) * 10
        ones = CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens + ones
    return None


# 元丰 1=1078, 2=1079, 3=1080
ERA_GREGORIAN = {"元丰": 1078, "熙宁": 1068}


def parse_lunar(lunar_str):
    """
    '元丰二年七月四日' → ('1079', '07', '04', '1079-07-04')
    粗略折算 (农历月份直接当公历月份, 因果分析里月份级精度够用)
    """
    m = re.match(r"^(元丰|熙宁|元祐|绍圣)(\S+?)年(\S+?)月(\S+?)日$", lunar_str)
    if not m:
        return None
    era, era_year_cn, month_cn, day_cn = m.groups()
    base = ERA_GREGORIAN.get(era)
    if not base:
        return None
    era_year = cn_day_to_int(era_year_cn)
    if era_year is None:
        return None
    year = base + era_year - 1
    month = cn_day_to_int(month_cn)
    day = cn_day_to_int(day_cn)
    if not (month and day):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def main():
    text = RAW.read_text(encoding="utf-8")
    lines = text.split("\n")

    # ---------- 切分文档 ----------
    documents = []
    current_doc = None
    DOC_TITLE_PATTERNS = [
        r"^.*?(札子|状|供状|结按状|检会送到册子)$",  # 标题行通常以这些词结尾
    ]
    DOC_TITLE_RE = re.compile("|".join(DOC_TITLE_PATTERNS))

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s in ["东坡乌台诗案", "宋朋九万撰"]:
            continue
        # 短的且以"札子/状/供状"等结尾的认为是标题
        if len(s) <= 20 and DOC_TITLE_RE.search(s):
            if current_doc:
                documents.append(current_doc)
            current_doc = {
                "doc_id": f"doc_{len(documents)+1:02d}",
                "title": s,
                "body": "",
                "lines": []
            }
        else:
            if current_doc is None:
                # 前置无标题段, 起一个 doc_00 容器
                current_doc = {
                    "doc_id": "doc_00",
                    "title": "前置无题段",
                    "body": "",
                    "lines": []
                }
            current_doc["lines"].append(s)
            current_doc["body"] += s + "\n"

    if current_doc:
        documents.append(current_doc)

    # ---------- 时间轴提取 ----------
    LUNAR_PATTERN = re.compile(
        r"(元丰|熙宁|元祐|绍圣)([元一二三四五六七八九十]+)年"
        r"([元一二三四五六七八九十廿廾卅]+)月"
        r"([元一二三四五六七八九十廿廾卅]+)日"
    )

    timeline = []
    for doc in documents:
        for match in LUNAR_PATTERN.finditer(doc["body"]):
            lunar = match.group(0)
            iso_date = parse_lunar(lunar)
            if not iso_date:
                continue
            # 取上下文 50 字
            start = max(0, match.start() - 50)
            end = min(len(doc["body"]), match.end() + 50)
            context = doc["body"][start:end].replace("\n", " ")
            timeline.append({
                "date": iso_date,
                "lunar": lunar,
                "doc_id": doc["doc_id"],
                "doc_title": doc["title"],
                "context": context,
            })

    # 去重 + 按日期排序
    seen = set()
    timeline_dedup = []
    for ev in timeline:
        key = (ev["date"], ev["doc_id"])
        if key in seen:
            continue
        seen.add(key)
        timeline_dedup.append(ev)
    timeline_dedup.sort(key=lambda e: e["date"])

    # ---------- 关键节点补全 (《东坡先生年谱》中的 1079 重要日子) ----------
    KNOWN_EVENTS = [
        ("1079-04-21", "苏轼到湖州任", "manual"),
        ("1079-07-02", "舒亶 / 李定札子崇政殿进呈", "from_text"),
        ("1079-07-03", "圣旨送御史台根勘", "from_text"),
        ("1079-07-04", "中书批送下何大正札子", "from_text"),
        ("1079-07-28", "中使皇甫遵到湖州勾摄苏轼", "from_supplications"),
        ("1079-08-09", "苏轼自湖州赴京途中", "from_text"),
        ("1079-08-18", "苏轼赴御史台出头, 当日审讯开始", "from_supplications"),
        ("1079-08-20", "苏轼第 1 次供状", "from_supplications"),
        ("1079-08-22", "苏轼第 2 次供状", "from_supplications"),
        ("1079-08-24", "苏轼第 3 次供状", "from_supplications"),
        ("1079-08-30", "苏轼第 4 次供状", "from_supplications"),
        ("1079-10-15", "御宝批见勘治公事, 收坐多人", "from_text"),
        ("1079-11-15", "审议结束准备结按", "from_text"),
        ("1079-11-21", "中书批送下乞勘会苏轼举主", "from_text"),
        ("1079-11-28", "李定按结苏轼公事", "from_text"),
        ("1079-11-30", "御史台结按状奏", "from_text"),
        ("1079-12-29", "圣旨责授检校水部员外郎充黄州团练副使本州安置", "from_yangpu"),
    ]
    # 合并自动 + 已知
    existing_dates = {ev["date"] for ev in timeline_dedup}
    for date, action, source in KNOWN_EVENTS:
        if date not in existing_dates:
            timeline_dedup.append({
                "date": date,
                "lunar": "",
                "doc_id": "",
                "doc_title": "",
                "context": "",
                "action": action,
                "source": source,
            })
    timeline_dedup.sort(key=lambda e: e["date"])

    # ---------- 输出 ----------
    OUT_TIMELINE.write_text(
        json.dumps(timeline_dedup, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    with OUT_DOCS.open("w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps({
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "char_count": len(doc["body"]),
                "body": doc["body"],
            }, ensure_ascii=False) + "\n")

    # ---------- 汇报 ----------
    print(f"=== 解析《东坡乌台诗案》朋九万本 ===")
    print(f"切出文档数: {len(documents)}")
    for d in documents:
        print(f"  {d['doc_id']} {d['title']:20s} {len(d['body']):6d} 字")
    print()
    print(f"=== 时间轴 ({len(timeline_dedup)} 个节点) ===")
    for ev in timeline_dedup:
        src = ev.get("source", "from_pattern")
        action = ev.get("action") or ev.get("doc_title", "")
        print(f"  {ev['date']}  [{src:18s}]  {action}")
    print()
    print(f"=== 输出 ===")
    print(f"  {OUT_TIMELINE}")
    print(f"  {OUT_DOCS}")


if __name__ == "__main__":
    main()
