"""
ocr_sanity_check.py
对殆知阁苏轼语料做 OCR 质量 sanity check

策略:
  1. 内部一致性: 同一篇作品在 苏轼集 / 东坡诗集注 / 东坡词 多处出现时,做字级 diff
  2. 外部对照: 与 wikisource 的标准文本对照 (留待手动)

抽检篇目 (3 篇地标):
  - 前赤壁赋 (1082)
  - 念奴娇·赤壁怀古 (1082)
  - 和子由渑池怀旧 (1061)
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw_corpus" / "sushi_main"

ANCHORS = {
    "前赤壁赋": "壬戌之秋",            # 首句
    "念奴娇·赤壁怀古": "大江东去",     # 首句
    "和子由渑池怀旧": "人生到处知何似",  # 首句
}


def extract_passage(text, anchor, window=300):
    """在 text 中找到 anchor 出现位置,提取后 window 字符的段落"""
    idx = text.find(anchor)
    if idx < 0:
        return None, -1
    return text[idx:idx + window], idx


def normalize(s):
    """归一化: 去标点 / 空白 / 全角"""
    s = re.sub(r"[，。！？；：、,.!?;:\s　·]", "", s)
    s = re.sub(r"[（）()【】「」“”\"']", "", s)
    return s


def check_anchor(anchor_name, anchor_str, files):
    print(f"\n=== 抽检篇目: {anchor_name} ({anchor_str}) ===")
    samples = []
    for fname in files:
        path = RAW / fname
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        passage, idx = extract_passage(text, anchor_str, window=200)
        if passage is None:
            print(f"  [{fname:25s}] 未找到 anchor")
            continue
        norm = normalize(passage)
        print(f"  [{fname:25s}] 位置 {idx:8d}, 抽 200 字归一化后 {len(norm)} 字符")
        print(f"    {norm[:120]}")
        samples.append((fname, norm))

    # diff 两两对比
    if len(samples) >= 2:
        for i in range(len(samples)):
            for j in range(i+1, len(samples)):
                a, b = samples[i][1], samples[j][1]
                # 取共同前缀
                common = 0
                for k in range(min(len(a), len(b))):
                    if a[k] == b[k]:
                        common += 1
                    else:
                        break
                total = min(len(a), len(b))
                pct = common / total * 100 if total else 0
                print(f"  {samples[i][0]} <-> {samples[j][0]}: 共同前缀 {common}/{total} ({pct:.1f}%)")
                if common < total and total > 0:
                    # 显示首个分歧点
                    if k < min(len(a), len(b)):
                        print(f"    首个分歧 @ pos {k}: ...{a[max(0,k-5):k]}[{a[k]}|{b[k]}]{a[k+1:k+15]}...")


def main():
    files_for_poem = ["苏轼集.txt", "东坡诗集注.txt", "东坡全集.txt"]
    files_for_ci = ["苏轼集.txt", "东坡乐府.txt", "东坡词.txt"]
    files_for_fu = ["苏轼集.txt", "东坡全集.txt"]

    check_anchor("和子由渑池怀旧 (诗)", "人生到处知何似", files_for_poem)
    check_anchor("念奴娇·赤壁怀古 (词)", "大江东去", files_for_ci)
    check_anchor("前赤壁赋 (赋)", "壬戌之秋", files_for_fu)


if __name__ == "__main__":
    main()
