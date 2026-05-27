"""
extract_external.py
把王安石、黄庭坚的外部对照集按卷切分为 jsonl
四库本结构: '巻一 古诗一' / '巻二 古诗二' / ...

输出:
  data/corpus/wang_anshi.jsonl
  data/corpus/huang_tingjian.jsonl
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WANG = PROJECT_ROOT / "data" / "raw_corpus" / "wang_anshi" / "临川文集.txt"
HUANG = PROJECT_ROOT / "data" / "raw_corpus" / "huang_tingjian" / "山谷全集.txt"
OUT_WANG = PROJECT_ROOT / "data" / "corpus" / "wang_anshi.jsonl"
OUT_HUANG = PROJECT_ROOT / "data" / "corpus" / "huang_tingjian.jsonl"

# 四库本的卷标记: 巻一 / 巻一百 / 巻二十三 ...
VOLUME_RE = re.compile(r"^\s*巻[一二三四五六七八九十百]+\s*$")
# 卷题第二行 (古诗一 / 律诗一 / 词 / ...)
GENRE_RE = re.compile(r"^\s*(古诗|律诗|词|赋|奏|表|状|记|序|跋|碑|铭|论|启|尺牍|杂著|乐府|长短句|绝句|题跋|墓志|墓铭|墓碑|策|疏|文|集|遗文)\s*[一二三四五六七八九十百]*\s*$")


def extract(path, author_name):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # 跳过目录前 ~10 行 (提要、序文等)
    # 找到第一个看起来像正文的 "巻一"
    records = []
    current_vol = None
    current_genre = "unknown"
    buf = []
    vol_idx = 0

    for line in lines:
        s = line.strip().lstrip("　").strip()
        if not s:
            continue

        m_vol = VOLUME_RE.match(s)
        m_genre = GENRE_RE.match(s)

        if m_vol:
            if current_vol is not None and buf:
                content = "\n".join(buf).strip()
                if content:
                    records.append({
                        "id": f"{author_name}_v{vol_idx:03d}",
                        "author": author_name,
                        "volume_label": current_vol,
                        "genre_raw": current_genre,
                        "text": content,
                        "char_count": len(content.replace("　", "").replace(" ", "").replace("\n", "")),
                    })
            vol_idx += 1
            current_vol = s
            current_genre = "unknown"
            buf = []
        elif m_genre and not buf:
            # 卷下第一行是体裁标记
            current_genre = m_genre.group(1)
        else:
            buf.append(s)

    if current_vol is not None and buf:
        content = "\n".join(buf).strip()
        if content:
            records.append({
                "id": f"{author_name}_v{vol_idx:03d}",
                "author": author_name,
                "volume_label": current_vol,
                "genre_raw": current_genre,
                "text": content,
                "char_count": len(content.replace("　", "").replace(" ", "").replace("\n", "")),
            })
    return records


def main():
    for path, out_path, author in [
        (WANG, OUT_WANG, "wang_anshi"),
        (HUANG, OUT_HUANG, "huang_tingjian"),
    ]:
        recs = extract(path, author)
        with out_path.open("w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        from collections import Counter
        genres = Counter(r["genre_raw"] for r in recs)
        total_chars = sum(r["char_count"] for r in recs)
        print(f"=== {author} ===")
        print(f"  切出 {len(recs)} 卷, 总 {total_chars:,} 字")
        print(f"  体裁分布: {dict(genres.most_common(10))}")
        print(f"  输出: {out_path}")
        print()


if __name__ == "__main__":
    main()
