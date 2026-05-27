"""
extract_and_analyze.py
顾炎武项目一站式抽取 + 分析

数据特点: 顾炎武主集缺少编年信息 (日知录是 30 年累积札记, 诗文集大多书信无年份)。
本项目改用非时序对照框架: 跨作者散度 (顾 vs 王 vs 黄) + 跨主题画像 + 跨文体对比。

输出:
  data/corpus/gu_rizhilu.jsonl          日知录按卷+条目切分
  data/corpus/gu_shiwen.jsonl           诗文集按卷+篇目切分
  data/corpus/cross_author_divergence.json    顾 vs 王 vs 黄 概念分布散度
  data/corpus/topic_profile.json        顾炎武 9 主题画像 + 8 维人格
  data/corpus/genre_compare.json        日知录 vs 诗文集 体裁差异
"""
import json
import re
import math
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concept_vocabulary import PERSONALITY_DIMENSIONS, CORE_CONCEPTS, all_concepts_flat

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_corpus"
CORPUS = ROOT / "data" / "corpus"
CORPUS.mkdir(parents=True, exist_ok=True)


# ============================================================
# 日知录 切分: ●卷X 标卷, ○条目名 标条目
# ============================================================
def extract_rizhilu():
    text = (RAW / "gu_main" / "日知录.txt").read_text(encoding="utf-8")
    lines = text.split("\n")

    records = []
    current_vol = None
    current_topic = None
    current_body = []
    rec_idx = 1

    def flush():
        nonlocal current_body, rec_idx
        if current_topic and current_body:
            body = "\n".join(current_body).strip()
            chars = len(re.findall(r"[一-鿿]", body))
            if chars >= 30:
                records.append({
                    "id": f"rzl_{rec_idx:04d}",
                    "source": "日知录",
                    "volume": current_vol,
                    "topic": current_topic,
                    "char_count": chars,
                    "text": body[:10000],
                })
                rec_idx += 1
        current_body = []

    vol_re = re.compile(r"●卷([一二三四五六七八九十百○]+)")
    topic_re = re.compile(r"^[　\s]*[●○]([^●○]{2,30})$")

    for line in lines:
        s = line.strip().lstrip("　").strip()
        if not s:
            continue
        m_v = vol_re.search(s)
        # 卷标 + 条目混在同一行: "●卷一○三易夫子言..."
        if m_v:
            flush()
            current_vol = m_v.group(0)
            # 看是否有 ○...
            after_vol = s[m_v.end():]
            if after_vol.startswith("○"):
                # ○ 后跟首条目名
                topic_match = re.match(r"○([^○\s]{2,30})", after_vol)
                if topic_match:
                    current_topic = topic_match.group(1)
                    body_part = after_vol[topic_match.end():]
                    if body_part.strip():
                        current_body.append(body_part)
            continue
        # ○ 起始 = 新条目
        if s.startswith("○"):
            flush()
            topic_match = re.match(r"○([^○\s]{2,30})", s)
            if topic_match:
                current_topic = topic_match.group(1)
                body_part = s[topic_match.end():]
                if body_part.strip():
                    current_body.append(body_part)
            continue
        # 行内含 ○ (条目在段中部) — 切多个
        if "○" in s:
            parts = s.split("○")
            # parts[0] 是前一条目尾巴
            if parts[0].strip() and current_topic:
                current_body.append(parts[0])
            flush()
            for p in parts[1:]:
                topic_match = re.match(r"([^○\s]{2,30})", p)
                if topic_match:
                    current_topic = topic_match.group(1)
                    body_part = p[topic_match.end():]
                    if body_part.strip():
                        current_body.append(body_part)
                    # 不 flush, 让下一行继续累积
            continue
        # 普通行 -> body
        if current_topic:
            current_body.append(s)
    flush()
    return records


# ============================================================
# 诗文集切分: 亭林文集 / 亭林诗集 卷一 / 卷二 篇目
# ============================================================
def extract_shiwen():
    text = (RAW / "gu_main" / "顾亭林诗文集.txt").read_text(encoding="utf-8")
    lines = text.split("\n")

    records = []
    current_collection = None  # 亭林文集 / 亭林诗集 / 余集
    current_vol = None
    current_title = None
    current_body = []
    rec_idx = 1
    in_toc = True  # 跳过目录

    # 检测目录结束: 第一次出现 \r"亭林文集" 或 \r"亭林诗集" 作为单独行 (含简短 < 8 字)
    def flush():
        nonlocal current_body, rec_idx
        if current_title and current_body:
            body = "\n".join(current_body).strip()
            chars = len(re.findall(r"[一-鿿]", body))
            if chars >= 20:
                records.append({
                    "id": f"sw_{rec_idx:04d}",
                    "source": "顾亭林诗文集",
                    "collection": current_collection,
                    "volume": current_vol,
                    "title": current_title,
                    "char_count": chars,
                    "text": body[:10000],
                    "genre": "诗" if current_collection and "诗" in current_collection else "文",
                })
                rec_idx += 1
        current_body = []

    coll_names = ["亭林文集", "亭林诗集", "亭林馀集", "亭林佚文辑补"]
    vol_re = re.compile(r"^卷[一二三四五六七八九十]+\s*$")
    # 目录里有 "卷一" 缩进 -> 跳过
    seen_first_real_title = False

    # 简化做法: 目录结束标志是出现"编例"后的下一个真正篇目内容 (>200 字行)
    # 或者直接按"亭林文集"出现两次切分
    coll_first_seen = {n: False for n in coll_names}

    for line in lines:
        s = line.strip().lstrip("　").strip()
        if not s:
            continue
        # 集名
        if s in coll_names:
            if coll_first_seen[s]:
                # 第二次见 -> 进入正文
                flush()
                current_collection = s
                current_vol = None
                in_toc = False
            else:
                coll_first_seen[s] = True
            continue
        if in_toc:
            continue
        # 卷标
        if vol_re.match(s):
            flush()
            current_vol = s
            current_title = None
            continue
        # 篇题: 一行短文 (< 30 字) 且不在 body 累积中
        # 简化判定: 没明显标点结尾, 且单独成行
        if len(s) <= 30 and not s.endswith("。") and not s.endswith(",") and not s.endswith(",") and not s.endswith("，"):
            # 但要排除一些非标题的短行
            if current_title and current_body and len("\n".join(current_body)) < 100:
                # body 还很短, 这行可能是上篇延续
                current_body.append(s)
            else:
                flush()
                current_title = s
            continue
        # 长行 -> body
        if current_title:
            current_body.append(s)
    flush()
    return records


# ============================================================
# 评分
# ============================================================
def annotate_scores(records):
    for r in records:
        text = r["text"]
        chars = max(r["char_count"], 1)
        for dim, subs in PERSONALITY_DIMENSIONS.items():
            cnt = sum(text.count(w) for sub in subs.values() for w in sub)
            r[f"{dim}_per1k"] = cnt / chars * 1000
        for theme, words in CORE_CONCEPTS.items():
            cnt = sum(text.count(w) for w in words)
            r[f"{theme}_per1k"] = cnt / chars * 1000
    return records


# ============================================================
# 跨作者散度: 顾 vs 王 vs 黄
# ============================================================
def text_to_dist(text, concepts):
    c = {w: text.count(w) for w in concepts}
    tot = sum(c.values())
    if tot == 0:
        return {w: 0.0 for w in concepts}
    return {w: c[w] / tot for w in c}


def js(p, q):
    m = {w: (p[w] + q[w]) / 2 for w in p}
    def kl(a, b):
        s = 0.0
        for w in a:
            if a[w] > 0 and b[w] > 0:
                s += a[w] * math.log2(a[w] / b[w])
        return s
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def run_cross_author():
    concepts = all_concepts_flat()
    # 三作者全文合并
    gu_text = ((RAW / "gu_main" / "日知录.txt").read_text(encoding="utf-8") +
               (RAW / "gu_main" / "顾亭林诗文集.txt").read_text(encoding="utf-8"))
    wang_text = ((RAW / "wang_fuzhi" / "读通鉴论.txt").read_text(encoding="utf-8") +
                 (RAW / "wang_fuzhi" / "船山思问录.txt").read_text(encoding="utf-8") +
                 (RAW / "wang_fuzhi" / "船山经义.txt").read_text(encoding="utf-8"))
    huang_text = (RAW / "huang_zongxi" / "明儒学案.txt").read_text(encoding="utf-8")
    gu_d = text_to_dist(gu_text, concepts)
    wang_d = text_to_dist(wang_text, concepts)
    huang_d = text_to_dist(huang_text, concepts)
    return {
        "JS_gu_wang": js(gu_d, wang_d),
        "JS_gu_huang": js(gu_d, huang_d),
        "JS_wang_huang": js(wang_d, huang_d),
        "gu_text_chars": len(re.findall(r"[一-鿿]", gu_text)),
        "wang_text_chars": len(re.findall(r"[一-鿿]", wang_text)),
        "huang_text_chars": len(re.findall(r"[一-鿿]", huang_text)),
        "gu_top_concepts": dict(sorted(gu_d.items(), key=lambda x: -x[1])[:10]),
        "wang_top_concepts": dict(sorted(wang_d.items(), key=lambda x: -x[1])[:10]),
        "huang_top_concepts": dict(sorted(huang_d.items(), key=lambda x: -x[1])[:10]),
    }


# ============================================================
# 9 主题画像 (顾炎武日知录 + 诗文集)
# ============================================================
def run_topic_profile(rzl, shiwen):
    out = {"日知录": {}, "诗文集_文": {}, "诗文集_诗": {}}
    for theme in CORE_CONCEPTS:
        key = f"{theme}_per1k"
        vals_rzl = [r[key] for r in rzl if key in r]
        vals_wen = [r[key] for r in shiwen if r.get("genre") == "文" and key in r]
        vals_shi = [r[key] for r in shiwen if r.get("genre") == "诗" and key in r]
        out["日知录"][theme] = float(np.mean(vals_rzl)) if vals_rzl else 0
        out["诗文集_文"][theme] = float(np.mean(vals_wen)) if vals_wen else 0
        out["诗文集_诗"][theme] = float(np.mean(vals_shi)) if vals_shi else 0
    # 8 维同
    for dim in PERSONALITY_DIMENSIONS:
        key = f"{dim}_per1k"
        vals_rzl = [r[key] for r in rzl if key in r]
        vals_wen = [r[key] for r in shiwen if r.get("genre") == "文" and key in r]
        vals_shi = [r[key] for r in shiwen if r.get("genre") == "诗" and key in r]
        out["日知录"][dim] = float(np.mean(vals_rzl)) if vals_rzl else 0
        out["诗文集_文"][dim] = float(np.mean(vals_wen)) if vals_wen else 0
        out["诗文集_诗"][dim] = float(np.mean(vals_shi)) if vals_shi else 0
    return out


# ============================================================
# 主流程
# ============================================================
def main():
    print("=== Step 1: 切分日知录 ===")
    rzl = extract_rizhilu()
    print(f"  得 {len(rzl)} 条")
    rzl = annotate_scores(rzl)
    with (CORPUS / "gu_rizhilu.jsonl").open("w", encoding="utf-8") as f:
        for r in rzl:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== Step 2: 切分诗文集 ===")
    shiwen = extract_shiwen()
    print(f"  得 {len(shiwen)} 篇")
    from collections import Counter
    genres = Counter(r["genre"] for r in shiwen)
    print(f"  体裁: {dict(genres)}")
    shiwen = annotate_scores(shiwen)
    with (CORPUS / "gu_shiwen.jsonl").open("w", encoding="utf-8") as f:
        for r in shiwen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print()
    print("=== Step 3: 跨作者散度 (顾炎武 vs 王夫之 vs 黄宗羲) ===")
    ca = run_cross_author()
    (CORPUS / "cross_author_divergence.json").write_text(
        json.dumps(ca, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  字数: 顾 {ca['gu_text_chars']:,}, 王 {ca['wang_text_chars']:,}, 黄 {ca['huang_text_chars']:,}")
    print(f"  JS(顾, 王) = {ca['JS_gu_wang']:.4f}")
    print(f"  JS(顾, 黄) = {ca['JS_gu_huang']:.4f}")
    print(f"  JS(王, 黄) = {ca['JS_wang_huang']:.4f}")
    print(f"  顾 top 概念: {list(ca['gu_top_concepts'].keys())[:5]}")
    print(f"  王 top 概念: {list(ca['wang_top_concepts'].keys())[:5]}")
    print(f"  黄 top 概念: {list(ca['huang_top_concepts'].keys())[:5]}")

    print()
    print("=== Step 4: 9 主题 + 8 维度画像 (日知录 / 文 / 诗) ===")
    tp = run_topic_profile(rzl, shiwen)
    (CORPUS / "topic_profile.json").write_text(
        json.dumps(tp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {'主题':10s}  {'日知录':>8s}  {'文':>8s}  {'诗':>8s}")
    for theme in CORE_CONCEPTS:
        print(f"  {theme:10s}  {tp['日知录'][theme]:>8.2f}  {tp['诗文集_文'][theme]:>8.2f}  {tp['诗文集_诗'][theme]:>8.2f}")
    print()
    print(f"  {'维度':18s}  {'日知录':>8s}  {'文':>8s}  {'诗':>8s}")
    for dim in PERSONALITY_DIMENSIONS:
        print(f"  {dim:18s}  {tp['日知录'][dim]:>8.2f}  {tp['诗文集_文'][dim]:>8.2f}  {tp['诗文集_诗'][dim]:>8.2f}")


if __name__ == "__main__":
    main()
