"""
传习录 公版原文抽取脚本

输入: 上海古籍 全本全注全译版 EPUB 解包后的 text/ 目录
输出: chuanxilu.jsonl, 每行一条记录
       { id, volume, chapter, recorder_or_addressee, item_no_zh, item_no, text, char_count }

只保留公版原文 (CSS class = "bodytext1"), 丢弃:
  - 现代校注 ("preface-text1", "preface-text2", "bodytext-zh")
  - 现代翻译 ("bodytext-kt-*")
  - 注脚标记 (<sup class="calibre1">［一］</sup> etc.)
  - 卷中收信人原信 ("bodytext-copy") —— 这些不是阳明的话
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 章节元数据: part 文件 → (卷, 章节标题, 记录者/收信人)
# 卷中各书信对象作为 "addressee" 字段, 卷上下各学生作为 "recorder"
# 时间断代不放进抽取脚本, 留给单独的 metadata 文件做
# ---------------------------------------------------------------------------
CHAPTER_META = {
    "part0005.html": ("上", "徐爱录", "徐爱"),
    "part0006.html": ("上", "陆澄录", "陆澄"),
    "part0007.html": ("上", "薛侃录", "薛侃"),
    "part0010.html": ("中", "答顾东桥书", "顾东桥"),
    "part0011.html": ("中", "答周道通书", "周道通"),
    "part0012.html": ("中", "答陆原静书", "陆原静"),
    "part0013.html": ("中", "又(答陆原静)", "陆原静"),
    "part0014.html": ("中", "答欧阳崇一", "欧阳崇一"),
    "part0015.html": ("中", "答罗整庵少宰书", "罗整庵"),
    "part0016.html": ("中", "答聂文蔚一", "聂文蔚"),
    "part0017.html": ("中", "答聂文蔚二", "聂文蔚"),
    "part0018.html": ("中", "训蒙大意示教读刘伯颂等", "刘伯颂等"),
    "part0019.html": ("中", "教约", None),
    "part0021.html": ("下", "陈九川录", "陈九川"),
    "part0022.html": ("下", "黄直录", "黄直"),
    "part0023.html": ("下", "黄修易录", "黄修易"),
    "part0024.html": ("下", "黄省曾录", "黄省曾"),
    "part0025.html": ("下", "黄以方录", "黄以方"),
}

# 中文圆圈数字转阿拉伯数字, 用于 item_no
ZH_DIGIT = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def zh_to_int(zh: str) -> int:
    """把 〇〇一 / 一三一 / 三四三 这种纯位数中文数字转成 int. 不处理"十""百"."""
    return int("".join(str(ZH_DIGIT[c]) for c in zh))


def clean_text(node) -> str:
    """从一个 <p> 节点提取纯文本, 去掉 <sup> 注脚标记和 ［一］［二］残留."""
    # 删除所有 <sup>
    for sup in node.find_all("sup"):
        sup.decompose()
    text = node.get_text(strip=True)
    # 兜底: 即使没有 <sup> 的位置有时也会留下 ［一］/［二］ 注脚标记
    text = re.sub(r"［[一二三四五六七八九十〇\d]+］", "", text)
    # 删除多余空白
    text = re.sub(r"\s+", "", text)
    return text


def extract_chapter(html_path: Path, volume: str, chapter: str, recorder: str | None):
    """抽一个 part 文件里的所有条目, 返回 list[dict]."""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    records = []

    h3_nodes = soup.find_all("h3", class_="text-title-3-c")
    for h3 in h3_nodes:
        item_no_zh = h3.get_text(strip=True)
        try:
            item_no = zh_to_int(item_no_zh)
        except KeyError:
            # 有些条目编号可能含特殊字符, 跳过
            continue

        # 收集这个 h3 后面到下一个 h3 或 <hr> 之前的所有 bodytext1 段落
        parts = []
        for sib in h3.next_siblings:
            if sib.name == "h3":
                break
            if sib.name == "hr":
                # 遇到分割线说明进入校注/翻译区, 停止
                break
            if sib.name == "p":
                cls = sib.get("class", [])
                if "bodytext1" in cls:
                    parts.append(clean_text(sib))

        if not parts:
            # 没收到原文 (可能纯粹是引用的对方来信, 卷中部分条目会这样)
            # 仍然记录, 把 text 留空, 标记一下
            text = ""
        else:
            text = "".join(parts)

        records.append({
            "id": f"cxl_{item_no:03d}",
            "volume": volume,
            "chapter": chapter,
            "recorder_or_addressee": recorder,
            "item_no_zh": item_no_zh,
            "item_no": item_no,
            "text": text,
            "char_count": len(text),
        })

    return records


def main():
    ROOT = Path(__file__).resolve().parent.parent
    src_dir = ROOT / "data" / "extracted" / "chuanxilu" / "text"
    out_dir = ROOT / "data" / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "chuanxilu_343_raw.jsonl"

    all_records = []
    for fname, (vol, ch, rec) in CHAPTER_META.items():
        path = src_dir / fname
        if not path.exists():
            print(f"WARN: 缺失 {path}")
            continue
        recs = extract_chapter(path, vol, ch, rec)
        all_records.extend(recs)
        print(f"  {fname}  {vol}卷  {ch}: {len(recs)} 条")

    # 按 item_no 排序
    all_records.sort(key=lambda r: r["item_no"])

    # 检查编号连续性
    expected = list(range(1, len(all_records) + 1))
    actual = [r["item_no"] for r in all_records]
    if expected != actual:
        gaps = [i for i, (e, a) in enumerate(zip(expected, actual)) if e != a]
        print(f"  编号不连续, 首个不一致位置: {gaps[:5] if gaps else 'N/A'}")
    else:
        print(f"  编号 1..{len(all_records)} 完全连续")

    # 写 JSONL
    with out_path.open("w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 基本统计
    total_chars = sum(r["char_count"] for r in all_records)
    empty = sum(1 for r in all_records if r["char_count"] == 0)
    print(f"\n总条目数: {len(all_records)}")
    print(f"总字数:   {total_chars:,}")
    print(f"空条目:   {empty}")
    print(f"输出:     {out_path}")


if __name__ == "__main__":
    main()
