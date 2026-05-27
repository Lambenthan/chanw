"""
annotate_metadata.py
给 sushi_main_dated.jsonl 加三类元数据标注:
  1. is_ghostwriting: 内制/外制 section → True (翰林学士代笔, 1086-1089)
  2. social_function: 词的应酬性分类 (self_expression / social_courtesy / commemoration / topic_painting / funereal)
  3. variant_normalized: 异体字归一化文本副本

输入:  data/corpus/sushi_main_dated.jsonl
输出:  data/corpus/sushi_main_annotated.jsonl
       data/corpus/annotation_stats.json
"""
import json
import re
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IN_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_main_dated.jsonl"
OUT_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_main_annotated.jsonl"
OUT_STATS = PROJECT_ROOT / "data" / "corpus" / "annotation_stats.json"

# ============================================================
# 1. 异体字归一化表 (基于 OCR 抽检发现的对照 + Unicode 异体字常见列)
# ============================================================
VARIANT_MAP = {
    # OCR 抽检直接发现的
    "壊": "坏",
    "巳": "已",
    "嵗": "岁",
    "嵳": "差",
    "崎": "崎",
    "﨑": "崎",  # CJK 异体
    "髪": "发",
    "酧": "酬",
    "防": "防",  # 已对
    "逰": "游",
    "爲": "为",
    "於": "于",
    "與": "与",
    "對": "对",
    "個": "个",
    # 常见简繁混排修正
    "傳": "传",
    "經": "经",
    "義": "义",
    "禮": "礼",
    "聖": "圣",
    "賢": "贤",
    "學": "学",
    "問": "问",
    "讀": "读",
    "書": "书",
    "詩": "诗",
    "詞": "词",
    "賦": "赋",
    "歸": "归",
    "閑": "闲",
    "閒": "闲",
    "歎": "叹",
    "嘆": "叹",
    "氣": "气",
    "無": "无",
    "為": "为",
}


def normalize_variants(text):
    if not text:
        return ""
    return "".join(VARIANT_MAP.get(c, c) for c in text)


# ============================================================
# 2. 词的应酬性规则: 基于词题 + 序文关键词
# ============================================================
# 关键词指向不同 social_function
SOCIAL_KEYWORDS = {
    "social_courtesy": ["和", "次韵", "酬", "答", "赠", "送", "寄", "戏作", "戏",
                        "侑酒", "席上", "宴", "饯", "代", "诵韵", "再和", "用韵"],
    "commemoration": ["寿", "贺", "庆", "席间", "祝", "归省"],
    "topic_painting": ["题", "题画", "画", "图", "屏", "扇"],
    "funereal": ["挽", "悼", "祭", "哀", "亡"],
}


def classify_social_function(title, text, genre):
    """词 / 诗的应酬性分类"""
    if genre != "词":
        # 非词暂不分类
        return None
    title = title or ""
    text_head = (text or "")[:80]
    # 题首关键词
    for category, keywords in SOCIAL_KEYWORDS.items():
        for kw in keywords:
            if kw in title or kw in text_head:
                return category
    # 默认 self_expression
    return "self_expression"


# ============================================================
# 3. 代笔识别: section 含 "内制" 或 "外制"
# ============================================================
def is_ghostwriting(section):
    if not section:
        return False
    return "内制" in section or "外制" in section


# ============================================================
# 主流程
# ============================================================
def main():
    annotated = []
    stats = {
        "total": 0,
        "ghostwriting": 0,
        "social_function": Counter(),
        "normalized_diff_count": 0,
    }
    with IN_JSONL.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            stats["total"] += 1

            # 代笔标注
            gw = is_ghostwriting(r.get("section"))
            r["is_ghostwriting"] = gw
            if gw:
                stats["ghostwriting"] += 1

            # 词应酬性标注
            sf = classify_social_function(r.get("title"), r.get("text"), r.get("genre_raw"))
            r["social_function"] = sf
            if sf:
                stats["social_function"][sf] += 1

            # 异体字归一化文本
            orig = r.get("text", "")
            normed = normalize_variants(orig)
            if normed != orig:
                stats["normalized_diff_count"] += 1
            r["text_normalized"] = normed

            annotated.append(r)

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in annotated:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats["social_function"] = dict(stats["social_function"])
    OUT_STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    # 汇报
    print(f"=== 元数据标注 ===")
    print(f"  总篇目: {stats['total']}")
    print(f"  代笔标注 (is_ghostwriting=true): {stats['ghostwriting']} 篇")
    print(f"  异体字修正篇数: {stats['normalized_diff_count']} 篇")
    print()
    print(f"  词应酬性分布:")
    for k, v in sorted(stats["social_function"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:20s} {v:4d}")
    print()
    print(f"输出: {OUT_JSONL}")
    print(f"     {OUT_STATS}")


if __name__ == "__main__":
    main()
