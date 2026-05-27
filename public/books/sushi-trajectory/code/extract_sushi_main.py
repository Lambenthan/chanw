"""
extract_sushi_main.py
将苏轼集 (唐宋八大家本) + 东坡全集 (四库本) 切分为篇级 jsonl

输入:
  data/raw_corpus/sushi_main/苏轼集.txt
  data/raw_corpus/sushi_main/东坡全集.txt

输出:
  data/corpus/sushi_main.jsonl
  data/corpus/sushi_main_stats.json

每条记录:
{
  "id":           "ss_v01_p01",
  "source":       "苏轼集",
  "volume":       1,
  "section":      "诗四十七首",     # 卷内 ◎类
  "title":        "和子由渑池怀旧",
  "text":         "人生到处知何似...",
  "char_count":   88,
  "genre_raw":    "诗",              # 从 section 推断
  "year":         null,              # 留给后续编年脚本
  "year_confidence": null
}
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw_corpus" / "sushi_main"
OUT_DIR = PROJECT_ROOT / "data" / "corpus"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSONL = OUT_DIR / "sushi_main.jsonl"
OUT_STATS = OUT_DIR / "sushi_main_stats.json"

# 中文数字 → 阿拉伯 (限卷号用)
CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100,
}


def parse_volume_num(s):
    """'卷一百一十三' → 113, '卷一' → 1, '卷三十' → 30"""
    s = s.replace("卷", "").strip()
    if not s:
        return None
    # 处理 "一百一十三"
    val = 0
    hundred = 0
    if "百" in s:
        parts = s.split("百", 1)
        hundred = (CN_NUM_MAP.get(parts[0], 1) if parts[0] else 1) * 100
        s = parts[1]
    if "十" in s:
        parts = s.split("十", 1)
        tens = (CN_NUM_MAP.get(parts[0], 1) if parts[0] else 1) * 10
        ones = CN_NUM_MAP.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        val = tens + ones
    else:
        val = CN_NUM_MAP.get(s, 0)
    return hundred + val if (hundred + val) > 0 else None


def detect_genre(section_label):
    """'诗四十七首' → '诗', '文章十九首' → '文', '词二十三首' → '词'"""
    if not section_label:
        return "unknown"
    s = section_label
    if "诗" in s:
        return "诗"
    if "词" in s or "乐府" in s:
        return "词"
    if "赋" in s:
        return "赋"
    if "奏" in s or "表" in s or "状" in s:
        return "奏议"
    if "记" in s:
        return "记"
    if "序" in s:
        return "序"
    if "书" in s or "尺牍" in s or "尺读" in s or "札" in s:
        return "尺牍"
    if "碑" in s or "铭" in s:
        return "碑铭"
    if "祭" in s:
        return "祭文"
    if "策" in s or "论" in s:
        return "论策"
    if "题跋" in s or "跋" in s:
        return "题跋"
    return "其他"


# 篇题模式: 【...】 包裹
TITLE_RE = re.compile(r"^\s*[【〖]([^】〗]{1,80})[】〗]\s*$")
# 卷标题: ●卷一 / ●卷一百一十三
VOLUME_RE = re.compile(r"^●卷([一二三四五六七八九十百]+)\s*$")
# 小类标识: ◎诗四十七首 / ◎赋
SECTION_RE = re.compile(r"^◎(.+?)$")


def extract_one_file(path, source_name):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # 找到真正的卷一开始位置 (跳过目录)
    # 目录里 ●卷一 ●卷二 ●卷三 是连续行,正文 ●卷一 之后会有 ◎X 或【X】等内容
    in_body = False
    body_start = 0
    consecutive_vol = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if VOLUME_RE.match(s):
            consecutive_vol += 1
        else:
            if consecutive_vol > 0 and s and not s.startswith("●"):
                # 第一次出现非卷标行且前面有卷标 → 这是正文
                # 但目录后通常会有零星卷号穿插,所以更严格的判定:
                # 找到第一个 ◎ 或 【 行,然后回溯找最近的 ●卷
                pass
            consecutive_vol = 0

    # 简化策略: 找第一个 ◎ 行,从那行往前找最近 ●卷 作为正文起点
    first_section_idx = -1
    for i, line in enumerate(lines):
        if SECTION_RE.match(line.strip()):
            first_section_idx = i
            break

    if first_section_idx > 0:
        # 回溯找 ●卷
        for j in range(first_section_idx - 1, -1, -1):
            if VOLUME_RE.match(lines[j].strip()):
                body_start = j
                break
    else:
        # 没找到 ◎,从第一篇【题目】回溯
        first_title_idx = -1
        for i, line in enumerate(lines):
            if TITLE_RE.match(line.strip()):
                first_title_idx = i
                break
        if first_title_idx > 0:
            for j in range(first_title_idx - 1, -1, -1):
                if VOLUME_RE.match(lines[j].strip()):
                    body_start = j
                    break
        else:
            body_start = 0  # fallback

    # ---------- 主切分 ----------
    records = []
    current_volume = None
    current_section = None
    current_title = None
    current_text_lines = []
    rec_idx = 1

    def flush():
        nonlocal current_text_lines, rec_idx
        if current_title and current_text_lines:
            text_body = "\n".join(current_text_lines).strip()
            text_body = re.sub(r"^[　\s]+", "", text_body, flags=re.MULTILINE)
            if text_body:
                rec = {
                    "id": f"{source_name}_v{current_volume:03d}_p{rec_idx:03d}" if current_volume else f"{source_name}_p{rec_idx:03d}",
                    "source": source_name,
                    "volume": current_volume,
                    "section": current_section,
                    "genre_raw": detect_genre(current_section),
                    "title": current_title,
                    "text": text_body,
                    "char_count": len(text_body.replace("\n", "").replace(" ", "").replace("　", "")),
                    "year": None,
                    "year_confidence": None,
                }
                records.append(rec)
                rec_idx += 1
        current_text_lines = []

    for i in range(body_start, len(lines)):
        line = lines[i]
        s = line.strip().lstrip("　")
        if not s:
            current_text_lines.append("")
            continue

        m_vol = VOLUME_RE.match(s)
        m_sec = SECTION_RE.match(s)
        m_title = TITLE_RE.match(s)

        if m_vol:
            flush()
            current_volume = parse_volume_num(m_vol.group(0)[1:])  # 去掉 ●
            current_section = None
            current_title = None
            rec_idx = 1
            continue
        if m_sec:
            flush()
            current_section = m_sec.group(1).strip()
            current_title = None
            continue
        if m_title:
            flush()
            current_title = m_title.group(1).strip()
            continue

        # 正文行
        if current_title:
            current_text_lines.append(s)

    flush()
    return records


def main():
    all_records = []
    for fname, source in [
        ("苏轼集.txt", "ss"),
        ("东坡全集.txt", "dpqj"),
    ]:
        path = RAW_DIR / fname
        if not path.exists():
            print(f"!! 跳过不存在的文件: {path}")
            continue
        recs = extract_one_file(path, source)
        print(f"  {fname:20s} → {len(recs)} 篇")
        all_records.extend(recs)

    # ---------- 写 jsonl ----------
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------- 统计 ----------
    stats = {
        "total_records": len(all_records),
        "by_source": {},
        "by_genre": {},
        "char_total": 0,
    }
    for r in all_records:
        stats["by_source"].setdefault(r["source"], 0)
        stats["by_source"][r["source"]] += 1
        stats["by_genre"].setdefault(r["genre_raw"], 0)
        stats["by_genre"][r["genre_raw"]] += 1
        stats["char_total"] += r["char_count"]

    OUT_STATS.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    print(f"=== 总计 {stats['total_records']} 篇, {stats['char_total']:,} 字 ===")
    print(f"  按来源: {stats['by_source']}")
    print(f"  按体裁:")
    for g, n in sorted(stats["by_genre"].items(), key=lambda kv: -kv[1]):
        print(f"    {g:8s} {n:5d}")
    print()
    print(f"=== 输出 ===")
    print(f"  {OUT_JSONL}")
    print(f"  {OUT_STATS}")

    # 样本 3 条
    print()
    print(f"=== 样本前 3 条 ===")
    for r in all_records[:3]:
        print(f"  [{r['id']}] 卷{r['volume']} 「{r['section']}」 {r['title'][:30]}")
        print(f"    {r['text'][:80].strip()}...")


if __name__ == "__main__":
    main()
