"""王阳明全集结构化抽取 (v2 — 处理 EPUB 跨文件 split 的卷头/内容)

输入: data/extracted/yangming_full/text/
输出:
  data/corpus/yangming_full.jsonl       (阳明本人语料)
  data/corpus/qiandehong_nianpu.jsonl   (钱德洪年谱, 单独存放)

设计要点:
  1. 按文件名顺序遍历 (split_000 在前, split_001 在后)
  2. 维护当前 vol_info 状态, h2 头部出现时更新, 否则沿用上一卷
  3. h2.sigilnotintoc1 + h2.calibre8 都能作为卷头
  4. 单篇文档 = <h3 class="sigilnotintoc"> ... 到下一个 h3 之前的所有 p.calibre6
  5. h3 中 <sub> 内容作为 date_annotation
"""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# Genre 识别
# ============================================================================
def detect_genre(text):
    """根据卷头文字判断 genre"""
    text = (text or "").strip()
    # 顺序敏感, 长串先匹配
    patterns = [
        ("祭文",   "祭文"),
        ("传记",   "祭文"),     # "祭文传记补编"
        ("世德纪", "世德纪"),
        ("年谱",   "年谱"),
        ("奏疏",   "奏疏"),
        ("公移",   "公移"),
        ("文录",   "文录"),
        ("外集",   "外集"),
        ("续编",   "续编"),
        ("语录",   "语录"),       # 卷一二三 = 传习录
        ("传习录", "语录"),
    ]
    for kw, g in patterns:
        if kw in text:
            return g
    return None


def parse_volume_number(text):
    """从 '卷一'/'卷三十一' 提取卷号"""
    m = re.search(r"卷([一二三四五六七八九十百\d]+)", text or "")
    if not m:
        return None
    s = m.group(1)
    if s.isdigit():
        return int(s)
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9}
    if s == "十": return 10
    if len(s) == 1: return cn.get(s)
    if s.startswith("十"): return 10 + cn.get(s[1:], 0)
    if s.endswith("十"):   return cn[s[0]] * 10
    if "十" in s:
        a, b = s.split("十")
        return cn[a] * 10 + cn.get(b, 0)
    return None


def clean_paragraph(node):
    """从 <p> 提取纯文本, 去 <sup>"""
    for sup in node.find_all("sup"):
        sup.decompose()
    text = node.get_text(strip=True)
    return re.sub(r"\s+", "", text)


# ============================================================================
# 排除的 genre
# ============================================================================
EXCLUDE_FROM_MAIN = {"年谱", "世德纪", "祭文"}
SAVE_NIANPU = {"年谱"}


def detect_volume_info(soup):
    """从 soup 里检测卷信息. 返回 None 表示该文件没有卷头."""
    # 优先 sigilnotintoc1
    h2_main = soup.find("h2", class_="sigilnotintoc1")
    h2_group = soup.find("h2", class_="calibre8")

    if not h2_main and not h2_group:
        return None

    main_text = h2_main.get_text(strip=True) if h2_main else ""
    group_text = h2_group.get_text(strip=True) if h2_group else ""

    # 用两个 h2 文字综合判断 genre
    genre = detect_genre(main_text) or detect_genre(group_text)
    vol_num = parse_volume_number(main_text) or parse_volume_number(group_text)

    if not genre and not vol_num:
        return None

    return {
        "vol_id":     vol_num,
        "vol_name":   main_text or group_text,
        "vol_group":  group_text,
        "genre":      genre,
    }


def extract_from_file(html_path, current_vol):
    """从一个 HTML 文件抽文档.

    current_vol: 上一个文件留下的 vol_info (None 表示首次)
    返回 (new_vol_or_unchanged, list[doc])
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    # 优先更新 vol_info
    detected = detect_volume_info(soup)
    if detected is not None:
        # 但要小心: 如果只检测到 group, 应该和 current 的 main 合并
        if detected.get("vol_name") or detected.get("vol_group"):
            vol_info = detected
        else:
            vol_info = current_vol
    else:
        vol_info = current_vol

    if vol_info is None:
        # 还没遇到任何卷头, 无法分类, 跳过
        return None, []

    # 抽 h3 文档
    docs = []
    h3_nodes = soup.find_all("h3", class_="sigilnotintoc")

    if not h3_nodes:
        # 没 h3 切分, 整文件视为一篇
        all_paras = soup.find_all("p", class_="calibre6")
        text = "".join(clean_paragraph(p) for p in all_paras)
        if text:
            # 用卷名作 fallback 标题
            docs.append({
                **vol_info,
                "title":           vol_info.get("vol_name", "未知"),
                "date_annotation": "",
                "text":            text,
                "char_count":      len(text),
            })
        return vol_info, docs

    for h3 in h3_nodes:
        # 提 sub 注释
        h3_copy = BeautifulSoup(str(h3), "html.parser")
        sub = h3_copy.find("sub")
        date_anno = sub.get_text(strip=True) if sub else ""
        if sub:
            sub.decompose()
        title = re.sub(r"\s+", "", h3_copy.get_text(strip=True))

        # 收 p.calibre6 直到下一个 h3
        parts = []
        for sib in h3.next_siblings:
            if sib.name == "h3":
                break
            if sib.name == "p":
                cls = sib.get("class", [])
                if "calibre6" in cls:
                    t = clean_paragraph(sib)
                    if t:
                        parts.append(t)

        text = "".join(parts)
        docs.append({
            **vol_info,
            "title":           title,
            "date_annotation": date_anno,
            "text":            text,
            "char_count":      len(text),
        })

    return vol_info, docs


def main():
    src_dir = ROOT / "data" / "extracted" / "yangming_full" / "text"
    out_main = ROOT / "data" / "corpus" / "yangming_full.jsonl"
    out_nianpu = ROOT / "data" / "corpus" / "qiandehong_nianpu.jsonl"

    parts = sorted(src_dir.glob("part*.html"))
    current_vol = None
    all_main, all_nianpu, all_excluded = [], [], []

    for p in parts:
        new_vol, docs = extract_from_file(p, current_vol)
        if new_vol is not None:
            current_vol = new_vol
        for d in docs:
            g = d.get("genre")
            if g in SAVE_NIANPU:
                all_nianpu.append(d)
            elif g in EXCLUDE_FROM_MAIN:
                all_excluded.append(d)
            else:
                all_main.append(d)

    # 编号
    for i, d in enumerate(all_main, 1):
        d["id"] = f"ymf_{i:04d}"
    for i, d in enumerate(all_nianpu, 1):
        d["id"] = f"qnp_{i:04d}"

    # 写
    def write_jsonl(path, records):
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    write_jsonl(out_main, all_main)
    write_jsonl(out_nianpu, all_nianpu)

    # 报告
    from collections import Counter

    main_chars     = sum(d["char_count"] for d in all_main)
    nianpu_chars   = sum(d["char_count"] for d in all_nianpu)
    excluded_chars = sum(d["char_count"] for d in all_excluded)

    print("=" * 70)
    print("王阳明全集抽取报告")
    print("=" * 70)

    print(f"\n■ 阳明本人语料 (yangming_full.jsonl)")
    print(f"  文档数:  {len(all_main):>5}")
    print(f"  字数:    {main_chars:>9,}")
    print(f"  按 genre 分布:")
    by_genre = Counter(d.get("genre") for d in all_main)
    for g, n in by_genre.most_common():
        chars = sum(d["char_count"] for d in all_main if d.get("genre") == g)
        with_date = sum(1 for d in all_main
                        if d.get("genre") == g and d["date_annotation"])
        print(f"    {str(g):<8}: {n:>4} 文档, {chars:>8,} 字, {with_date:>4} 篇含日期注释")

    print(f"\n■ 钱德洪年谱 (qiandehong_nianpu.jsonl)")
    print(f"  文档数:  {len(all_nianpu):>5}")
    print(f"  字数:    {nianpu_chars:>9,}")

    print(f"\n■ 排除 (世德纪 / 祭文 / 他人写阳明)")
    print(f"  文档数:  {len(all_excluded):>5}")
    print(f"  字数:    {excluded_chars:>9,}")

    print(f"\n  累计字数: 主 {main_chars:,} + 年谱 {nianpu_chars:,} + 排除 {excluded_chars:,} "
          f"= {main_chars + nianpu_chars + excluded_chars:,}")


if __name__ == "__main__":
    main()
