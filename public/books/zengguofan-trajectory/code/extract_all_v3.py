"""
extract_all_v3.py
v3 完整抽取 EPUB 31 册全部内容:
  - 奏稿 + 批牍 (part0001-3018)  → memorials.jsonl + pidu.jsonl
  - 日记 (part3513-3598)  → diary_daily.jsonl (按日切到日条目)
  - 家书 (part3606-5126)  → letters_v3.jsonl (含 1872 补全)
  - 信札 (part5131-5925)  → shuzha_v3.jsonl
  - 续编/补遗 (part5926-13577)  → letters_continued.jsonl + shuzha_continued.jsonl
"""
import json
import re
from pathlib import Path

EPUB_TEXT = Path("/tmp/zgf_epub_unpack/zgf31_unpacked/OEBPS/Text")
NCX = Path("/tmp/zgf_epub_unpack/zgf31_unpacked/OEBPS/toc.ncx")
ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
CORPUS.mkdir(parents=True, exist_ok=True)


def part_path(p):
    """处理 part 编号变长 (1-9999 = 4 位补零, 10000+ 原样)"""
    if p < 10000:
        return EPUB_TEXT / f"part{p:04d}.xhtml"
    return EPUB_TEXT / f"part{p}.xhtml"


ERA_BASE = {"嘉庆": 1796, "道光": 1821, "咸丰": 1851, "同治": 1862, "光绪": 1875}
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


SECTION_HEADER_RE = re.compile(
    r"^\s*(嘉庆|道光|咸丰|同治|光绪)\s*([元一二三四五六七八九十]+)\s*年\s*$"
)
TITLE_DATE_RE = re.compile(
    r"(闰)?([元一二三四五六七八九十廿卅正腊]+)\s*月"
    r"(?:\s*(初)?([元一二三四五六七八九十廿卅]+)\s*日)?"
)


def parse_date_from_title(title):
    m = TITLE_DATE_RE.search(title)
    if not m:
        return None, None
    month = cn_to_int(m.group(2))
    day_cn = m.group(4)
    day = cn_to_int(day_cn) if day_cn else None
    return month, day


def html_to_text(html):
    m = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    body = m.group(1) if m else html
    text = re.sub(r"<[^>]+>", " ", body)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_ncx_titles():
    ncx = NCX.read_text(encoding="utf-8")
    naps = re.findall(
        r'<navPoint[^>]*>\s*<navLabel>\s*<text>([^<]+)</text>\s*</navLabel>\s*<content src="([^"]+)"',
        ncx
    )
    out = {}
    for name, src in naps:
        m = re.search(r"part(\d+)", src)
        if m:
            part = int(m.group(1))
            if part not in out:
                out[part] = name.strip()
    return out


# ============================================================
# 标题分类
# ============================================================
def classify_memorial(title):
    """奏稿: 多以"折"/"片"结尾, 编号 + 内容
    判定: 数字开头 + ("折"|"片"|"奏") 出现"""
    head = title[:50]
    if re.match(r"^\d{1,4}．\s*[^折片奏]*(折|片|奏)", head):
        return "memorial"
    if re.match(r"^\d{1,4}\s*[^折片奏]*(折|片|奏)", head):
        return "memorial"
    return None


def classify_pidu(title):
    """批牍: '批X' 开头 或 标题含'批'"""
    head = title[:30]
    if re.match(r"^\d{0,4}．?\s*批", head):
        return "pidu"
    return None


def classify_family_letter(title):
    """家书: 禀父母 / 致诸弟 / 谕纪泽 等"""
    head = title[:30]
    if re.match(r"^\d{1,4}．?\s*禀(父母|父|母|祖父母|祖父|祖母|叔父|叔)", head):
        return "父母长辈"
    if re.match(r"^\d{1,4}．?\s*致(诸弟|两弟|温弟|澄弟|沅弟|季弟)", head):
        return "兄弟"
    if "致澄" in head[:15] or "致沅" in head[:15] or "致温" in head[:15] or "致季" in head[:15]:
        return "兄弟"
    if re.match(r"^\d{1,4}．?\s*谕(纪泽|纪鸿|纪寿)", head):
        return "儿子"
    if "谕纪" in head[:15]:
        return "儿子"
    return None


def classify_friend_letter(title):
    """信札 (致友朋): 致XXX / 与XXX / 复XXX, 不是家人"""
    head = title[:30]
    if classify_family_letter(title):
        return None
    m = re.match(r"^\d{1,4}．?\s*(致|与|复|加|上|寄|答)([一-鿿]{2,5})", head)
    if m:
        return f"朋友:{m.group(2)}"
    return None


# ============================================================
# 抽取单 part
# ============================================================
def extract_part(p, title):
    path = part_path(p)
    if not path.exists():
        return None
    html = path.read_text(encoding="utf-8", errors="replace")
    text = html_to_text(html)
    char_count = len(re.findall(r"[一-鿿]", text))
    return text, char_count


# ============================================================
# 抽取一类 (奏稿 / 批牍 / 家书 / 信札)
# ============================================================
def extract_category(part_titles, part_start, part_end, classifier, label):
    out = []
    current_year = None
    rec_idx = 1
    for part in range(part_start, part_end + 1):
        title = part_titles.get(part, "")
        sh = SECTION_HEADER_RE.match(title)
        if sh:
            era = sh.group(1)
            era_year = cn_to_int(sh.group(2))
            base = ERA_BASE.get(era)
            if base and era_year:
                current_year = base + era_year - 1
            continue
        if not title or "人名索引" in title or "提要" in title or len(title.strip()) < 5:
            continue
        cls = classifier(title)
        if not cls:
            continue
        res = extract_part(part, title)
        if not res:
            continue
        text, char_count = res
        if char_count < 20:
            continue
        month, day = parse_date_from_title(title)
        out.append({
            "id": f"{label[:4]}_{rec_idx:05d}",
            "category": label,
            "part": part,
            "title": title,
            "recipient_class": cls,
            "year": current_year,
            "month": month,
            "day": day,
            "char_count": char_count,
            "text": text[:20000],
        })
        rec_idx += 1
    return out


# ============================================================
# 日记按日切分
# ============================================================
MONTH_RE = re.compile(r"(?:^|\s|。|，)(闰)?([元一二三四五六七八九十正腊]{1,2})月(?![日])")
# 日: "初一日" / "廿三日" / "十一日"
DAY_RE = re.compile(r"(?:^|\s|。|，)(初[元一二三四五六七八九十]|[元一二三四五六七八九十廿卅]{1,3})日")


def extract_diary_daily(part_titles, part_start=3513, part_end=3598):
    """每个 part 是某一年日记。 月只标一次, 日逐条出现。 状态机切分:
    遍历文本, 维护 current_month, 遇月号更新, 遇日号切日条目。"""
    out = []
    rec_idx = 1
    for part in range(part_start, part_end + 1):
        path = part_path(part)
        if not path.exists():
            continue
        title = part_titles.get(part, "")
        # 从 title 推年
        sh_year = None
        m = re.search(r"(嘉庆|道光|咸丰|同治|光绪)\s*([元一二三四五六七八九十]+)\s*年", title)
        if m:
            era = m.group(1)
            era_year = cn_to_int(m.group(2))
            base = ERA_BASE.get(era)
            if base and era_year:
                sh_year = base + era_year - 1
        html = path.read_text(encoding="utf-8", errors="replace")
        text = html_to_text(html)
        # 收集所有 month 和 day 的位置
        events = []  # (pos, 'month' or 'day', month_int 或 day_int)
        for m in MONTH_RE.finditer(text):
            mo = cn_to_int(m.group(2))
            if mo and 1 <= mo <= 12:
                events.append((m.start(), 'month', mo))
        for m in DAY_RE.finditer(text):
            day_str = m.group(1)
            if day_str.startswith("初"):
                day = cn_to_int(day_str[1:])
            else:
                day = cn_to_int(day_str)
            if day and 1 <= day <= 31:
                events.append((m.start(), 'day', day))
        events.sort()
        # 状态机
        current_month = None
        day_positions = []
        for pos, kind, val in events:
            if kind == 'month':
                current_month = val
            elif kind == 'day' and current_month is not None:
                day_positions.append((pos, current_month, val))
        if not day_positions:
            continue
        # 切日条目
        for i, (start, mo, day) in enumerate(day_positions):
            next_start = day_positions[i+1][0] if i+1 < len(day_positions) else len(text)
            body = text[start:next_start].strip()
            char_count = len(re.findall(r"[一-鿿]", body))
            if char_count < 5:
                continue
            out.append({
                "id": f"d_{rec_idx:06d}",
                "category": "diary_day",
                "part": part,
                "title_section": title,
                "year": sh_year,
                "month": mo,
                "day": day,
                "char_count": char_count,
                "text": body[:5000],
            })
            rec_idx += 1
    return out


# ============================================================
# 主流程
# ============================================================
def main():
    print("=== 读 NCX ===")
    part_titles = parse_ncx_titles()
    print(f"  {len(part_titles)} part titles")

    print()
    print("=== 抽奏稿 (part 1-3018) ===")
    memorials = extract_category(part_titles, 1, 3018, classify_memorial, "memorial")
    print(f"  得 {len(memorials)} 篇")
    yrange = [r['year'] for r in memorials if r['year']]
    print(f"  年范围: {min(yrange) if yrange else None} - {max(yrange) if yrange else None}")
    print(f"  字数: {sum(r['char_count'] for r in memorials):,}")
    with (CORPUS / "memorials.jsonl").open("w", encoding="utf-8") as f:
        for r in memorials:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== 抽批牍 (part 1-3018, 与奏稿同区间) ===")
    pidu = extract_category(part_titles, 1, 3018, classify_pidu, "pidu")
    print(f"  得 {len(pidu)} 篇")
    yrange = [r['year'] for r in pidu if r['year']]
    print(f"  年范围: {min(yrange) if yrange else None} - {max(yrange) if yrange else None}")
    print(f"  字数: {sum(r['char_count'] for r in pidu):,}")
    with (CORPUS / "pidu.jsonl").open("w", encoding="utf-8") as f:
        for r in pidu:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== 抽家书续 (含 1872 部分, part 5926-13577) ===")
    letters_cont = extract_category(part_titles, 5926, 13577, classify_family_letter, "letter_family")
    print(f"  得 {len(letters_cont)} 封")
    yrange = [r['year'] for r in letters_cont if r['year']]
    print(f"  年范围: {min(yrange) if yrange else None} - {max(yrange) if yrange else None}")
    print(f"  字数: {sum(r['char_count'] for r in letters_cont):,}")
    with (CORPUS / "letters_continued.jsonl").open("w", encoding="utf-8") as f:
        for r in letters_cont:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== 抽信札续 (part 5926-13577 致友朋) ===")
    shuzha_cont = extract_category(part_titles, 5926, 13577, classify_friend_letter, "letter_friend")
    print(f"  得 {len(shuzha_cont)} 封")
    yrange = [r['year'] for r in shuzha_cont if r['year']]
    print(f"  年范围: {min(yrange) if yrange else None} - {max(yrange) if yrange else None}")
    print(f"  字数: {sum(r['char_count'] for r in shuzha_cont):,}")
    with (CORPUS / "shuzha_continued.jsonl").open("w", encoding="utf-8") as f:
        for r in shuzha_cont:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== 日记按日切分 (part 3513-3598) ===")
    diary_daily = extract_diary_daily(part_titles)
    print(f"  得 {len(diary_daily)} 个日条目")
    yrange = [r['year'] for r in diary_daily if r['year']]
    print(f"  年范围: {min(yrange) if yrange else None} - {max(yrange) if yrange else None}")
    print(f"  字数: {sum(r['char_count'] for r in diary_daily):,}")
    with (CORPUS / "diary_daily.jsonl").open("w", encoding="utf-8") as f:
        for r in diary_daily:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== v3 总计 ===")
    print(f"  奏稿: {len(memorials)} / 批牍: {len(pidu)}")
    print(f"  家书续: {len(letters_cont)} / 信札续: {len(shuzha_cont)}")
    print(f"  日记日条目: {len(diary_daily)}")
    print(f"  v3 新增总字数: {sum(r['char_count'] for r in memorials+pidu+letters_cont+shuzha_cont+diary_daily):,}")


if __name__ == "__main__":
    main()
