"""
extract_from_epub.py
从岳麓书社 2012 版《曾国藩全集》(31 册 EPUB) 抽取:
  - 日记 (part3513-3598)
  - 家书 (part3606-5126, 致家人)
  - 信札 (part5131-5925, 致朋友同僚, 作为可选 corpus)

EPUB 解压目录: /tmp/zgf_epub_unpack/zgf31_unpacked/OEBPS/Text/

每条记录:
{
  "id":              "diary_xxx" / "letter_xxx" / "shuzha_xxx",
  "category":        "diary" / "letter_family" / "letter_friend",
  "title":           原始 TOC 标题 (如 "001．禀父母　二月初九日")
  "recipient_raw":   收信人原文 (家书/信札适用)
  "recipient_class": 父母长辈 / 兄弟 / 儿子 / 朋友同僚
  "year":            int (公历)
  "month":           int (农历月)
  "day":             int (农历日)
  "year_source":     "from_section_header" / "from_title" / "from_text"
  "char_count":      int
  "text":            正文 (HTML 已剥)
}
"""
import json
import re
from pathlib import Path

EPUB_TEXT = Path("/tmp/zgf_epub_unpack/zgf31_unpacked/OEBPS/Text")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
NCX_FILE = Path("/tmp/zgf_epub_unpack/zgf31_unpacked/OEBPS/toc.ncx")
OUT_DIARY = PROJECT_ROOT / "data" / "corpus" / "diary.jsonl"
OUT_LETTERS = PROJECT_ROOT / "data" / "corpus" / "letters_v2.jsonl"
OUT_SHUZHA = PROJECT_ROOT / "data" / "corpus" / "shuzha.jsonl"

# ============================================================
# 农历年号 → 公历年
# ============================================================
ERA_BASE = {
    "嘉庆": 1796, "道光": 1821, "咸丰": 1851, "同治": 1862, "光绪": 1875,
}
CN_NUM = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
          "廿": 20, "卅": 30, "正": 1, "腊": 12}


def cn_to_int(s):
    if not s:
        return None
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("廿"):
        return 20 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    if s.startswith("十"):
        return 10 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    if "十" in s:
        parts = s.split("十", 1)
        tens = (CN_NUM.get(parts[0], 1) if parts[0] else 1) * 10
        ones = CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens + ones
    return None


# 标题里的日期: "二月初九日" / "正月十七日" / "闰五月" / "三月初四日辰刻"
TITLE_DATE_RE = re.compile(
    r"(闰)?([元一二三四五六七八九十廿卅正腊]+)\s*月"
    r"(?:\s*(初)?([元一二三四五六七八九十廿卅]+)\s*日)?"
    r"(?:\s*([元一二三四五六七八九十廿卅]+)\s*(更|刻|时|夜|早|鼓))?"
)
# 段落里的全日期 (可能在日记 part section header): "咸丰元年七月初一日"
FULL_DATE_RE = re.compile(
    r"(嘉庆|道光|咸丰|同治|光绪)\s*([元一二三四五六七八九十廿卅]+)\s*年"
    r"\s*(?:闰)?([元一二三四五六七八九十廿卅正腊]+)\s*月"
    r"(?:\s*(初)?([元一二三四五六七八九十廿卅]+)\s*日)?"
)


def parse_year_from_section(text):
    """从段落开头/部分头找'咸丰元年'类年号"""
    m = re.search(r"(嘉庆|道光|咸丰|同治|光绪)\s*([元一二三四五六七八九十]+)\s*年", text[:200])
    if not m:
        return None
    era = m.group(1)
    era_year = cn_to_int(m.group(2))
    base = ERA_BASE.get(era)
    if not base or era_year is None:
        return None
    return base + era_year - 1


def parse_date_from_title(title, fallback_year=None):
    """从标题如'001．禀父母 二月初九日'解析月日"""
    m = TITLE_DATE_RE.search(title)
    if not m:
        return None, None
    month = cn_to_int(m.group(2))
    day_cn = m.group(4)
    day = cn_to_int(day_cn) if day_cn else None
    return month, day


# ============================================================
# HTML 解析
# ============================================================
def html_to_text(html):
    """简单 HTML → 文本: 去 tag + 去 entity + 归一空白"""
    # 优先取 <body> 内容
    m = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    body = m.group(1) if m else html
    text = re.sub(r"<[^>]+>", " ", body)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# 收信人分类
# ============================================================
def classify_recipient_from_title(title):
    """从标题如'禀父母二月初九日' / '致沅弟正月元旦' / '谕纪泽十一月初八日'"""
    head = title[:30]
    # 家书类
    if re.search(r"禀(父母|父|母|祖父母|祖父|祖母|叔父|叔)", head):
        return "父母长辈", "family"
    if re.search(r"致(诸弟|两弟|温弟|澄弟|沅弟|季弟|温甫|澄侯|沅甫|季洪)", head) or "致澄" in head or "致沅" in head or "致温" in head or "致季" in head:
        return "兄弟", "family"
    if re.search(r"谕(纪泽|纪鸿|纪寿)", head):
        return "儿子", "family"
    # 信札类 (给朋友同僚)
    if re.match(r"^\d+．\s*(致|与|复|加|答|上|寄)", head) or re.match(r"^\d+\.", head):
        # 提取人名
        m = re.search(r"(致|与|复|加|答|上|寄)([一-鿿]{2,5})", head)
        if m:
            return f"朋友:{m.group(2)}", "friend"
        return "朋友其他", "friend"
    return None, None


# ============================================================
# 主抽取
# ============================================================
def parse_ncx_titles():
    """读 NCX, 返回 {part_num: title}"""
    ncx = NCX_FILE.read_text(encoding="utf-8")
    naps = re.findall(
        r'<navPoint[^>]*>\s*<navLabel>\s*<text>([^<]+)</text>\s*</navLabel>\s*<content src="([^"]+)"',
        ncx
    )
    out = {}
    for name, src in naps:
        m = re.search(r"part(\d+)", src)
        if not m:
            continue
        part = int(m.group(1))
        if part not in out:  # 取第一个 (主标题)
            out[part] = name.strip()
    return out


def extract_diary(part_titles):
    """抽取 part3513-3598 日记"""
    out = []
    rec_idx = 1
    current_year = None
    for part in range(3513, 3599):
        path = EPUB_TEXT / f"part{part:04d}.xhtml"
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        text = html_to_text(html)
        if len(text) < 50:
            continue
        # 年份: 从 part 标题(NCX) 提取, 否则文本里搜
        title = part_titles.get(part, "")
        y = parse_year_from_section(title) or parse_year_from_section(text)
        if y:
            current_year = y
        char_count = len(re.findall(r"[一-鿿]", text))
        out.append({
            "id": f"diary_{rec_idx:04d}",
            "category": "diary",
            "part": part,
            "title": title,
            "year": current_year,
            "month": None,
            "day": None,
            "year_source": "from_section_header",
            "char_count": char_count,
            "text": text[:30000],  # 单 part 上限 (避免过大)
        })
        rec_idx += 1
    return out


SECTION_HEADER_RE = re.compile(
    r"^\s*(嘉庆|道光|咸丰|同治|光绪)\s*([元一二三四五六七八九十]+)\s*年\s*$"
)


def extract_letters(part_titles, part_start, part_end, category_filter):
    """抽取家书或信札。 section header 只看 NCX title 严格匹配'X朝X年', 不看正文."""
    out = []
    current_year = None
    rec_idx = 1
    for part in range(part_start, part_end + 1):
        path = EPUB_TEXT / f"part{part:04d}.xhtml"
        if not path.exists():
            continue
        title = part_titles.get(part, "")
        # 1. section header? 严格匹配纯年号标题
        sh = SECTION_HEADER_RE.match(title)
        if sh:
            era = sh.group(1)
            era_year = cn_to_int(sh.group(2))
            base = ERA_BASE.get(era)
            if base and era_year:
                current_year = base + era_year - 1
            continue
        # 2. 跳过 "人名索引" 等非信件 part
        if "人名索引" in title or "提要" in title or len(title.strip()) < 5:
            continue
        # 3. 分类
        rec_cls, cat = classify_recipient_from_title(title)
        if cat != category_filter:
            continue
        # 4. 解析正文
        html = path.read_text(encoding="utf-8")
        text = html_to_text(html)
        if len(text) < 30:
            continue
        # 5. 月日
        month, day = parse_date_from_title(title)
        char_count = len(re.findall(r"[一-鿿]", text))
        if char_count < 20:
            continue
        out.append({
            "id": f"{category_filter[:6]}_{rec_idx:04d}",
            "category": "letter_family" if category_filter == "family" else "letter_friend",
            "part": part,
            "title": title,
            "recipient_class": rec_cls,
            "year": current_year,
            "month": month,
            "day": day,
            "year_source": "from_section_header",
            "char_count": char_count,
            "text": text[:20000],
        })
        rec_idx += 1
    return out


def main():
    print("=== Step 1: 读 NCX 标题 ===")
    part_titles = parse_ncx_titles()
    print(f"  解析 {len(part_titles)} 个 part 标题")

    print()
    print("=== Step 2: 抽取日记 (part3513-3598) ===")
    diary = extract_diary(part_titles)
    print(f"  得到 {len(diary)} 个日记 part")
    total_chars = sum(r["char_count"] for r in diary)
    print(f"  总字数: {total_chars:,}")
    with OUT_DIARY.open("w", encoding="utf-8") as f:
        for r in diary:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  → {OUT_DIARY}")

    print()
    print("=== Step 3: 抽取家书 (part3606-5126, 致家人) ===")
    letters = extract_letters(part_titles, 3606, 5126, "family")
    print(f"  得到 {len(letters)} 封家书")
    # 年份分布
    from collections import Counter
    rec_dist = Counter(r["recipient_class"] for r in letters)
    year_min = min((r["year"] for r in letters if r["year"]), default=None)
    year_max = max((r["year"] for r in letters if r["year"]), default=None)
    print(f"  年份范围: {year_min} - {year_max}")
    print(f"  收信人分布: {dict(rec_dist)}")
    print(f"  总字数: {sum(r['char_count'] for r in letters):,}")
    with OUT_LETTERS.open("w", encoding="utf-8") as f:
        for r in letters:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  → {OUT_LETTERS}")

    print()
    print("=== Step 4: 抽取信札 (part5131-5925, 致朋友同僚) ===")
    shuzha = extract_letters(part_titles, 5131, 5925, "friend")
    print(f"  得到 {len(shuzha)} 封信札")
    year_min2 = min((r["year"] for r in shuzha if r["year"]), default=None)
    year_max2 = max((r["year"] for r in shuzha if r["year"]), default=None)
    print(f"  年份范围: {year_min2} - {year_max2}")
    print(f"  总字数: {sum(r['char_count'] for r in shuzha):,}")
    with OUT_SHUZHA.open("w", encoding="utf-8") as f:
        for r in shuzha:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  → {OUT_SHUZHA}")

    print()
    print("=== 总计 ===")
    print(f"  日记 part: {len(diary)} 个 / {sum(r['char_count'] for r in diary):,} 字")
    print(f"  家书: {len(letters)} 封 / {sum(r['char_count'] for r in letters):,} 字")
    print(f"  信札: {len(shuzha)} 封 / {sum(r['char_count'] for r in shuzha):,} 字")
    print(f"  合计: {sum(r['char_count'] for r in diary + letters + shuzha):,} 字")


if __name__ == "__main__":
    main()
