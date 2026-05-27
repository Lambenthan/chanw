"""
parse_biography.py
将《东坡先生年谱》(王宗稷 撰, 宋本) 解析为 sushi_biography.json

输入: data/raw_corpus/sushi_meta/东坡先生年谱.txt
输出: data/corpus/sushi_biography.json

每条记录:
{
  "year":         1079,
  "age":          43,
  "era":          "元丰",
  "era_year":     2,
  "ganzhi":       "己未",
  "emperor":      "神宗",
  "events":       [...],            # 该年大事散文段切分
  "significance": 5,                # 1-5, 5=思想史/人生关键
  "raw_text":     "原文整段..."
}
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw_corpus" / "sushi_meta" / "东坡先生年谱.txt"
OUT_DIR = PROJECT_ROOT / "data" / "corpus"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = OUT_DIR / "sushi_biography.json"

# 中文数字 → 阿拉伯数字
CN_NUM = {
    "元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
}

# 帝号: 苏轼一生跨四帝
EMPERORS = ["仁宗皇帝", "英宗皇帝", "神宗皇帝", "哲宗皇帝", "徽宗皇帝"]

# 年号编年 (帝号, 年号, 起始公历年, 干支起始)
# 苏轼 1037-1101 覆盖
REIGN_TABLE = [
    ("仁宗", "景祐", 1034),
    ("仁宗", "宝元", 1038),
    ("仁宗", "康定", 1040),
    ("仁宗", "庆历", 1041),
    ("仁宗", "皇祐", 1049),
    ("仁宗", "至和", 1054),
    ("仁宗", "嘉祐", 1056),
    ("英宗", "治平", 1064),
    ("神宗", "熙宁", 1068),
    ("神宗", "元丰", 1078),
    ("哲宗", "元祐", 1086),
    ("哲宗", "绍圣", 1094),
    ("哲宗", "元符", 1098),
    ("徽宗", "建中靖国", 1101),
]


def cn_to_int(s):
    """简单中文数字转换 (限 1-30)"""
    if s == "元":
        return 1
    if s in CN_NUM:
        return CN_NUM[s]
    # 二十、二十一 等
    if s.startswith("十"):
        if len(s) == 1:
            return 10
        return 10 + CN_NUM.get(s[1], 0)
    if "十" in s:
        parts = s.split("十")
        tens = CN_NUM.get(parts[0], 0) * 10
        ones = CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens + ones
    return None


ERA_NAMES = [name for _, name, _ in REIGN_TABLE]


def parse_year_marker(line):
    """
    解析诸如 '●仁宗皇帝景祐三年丙子' / '●二年丁丑' / '●元丰元年戊午' 的标记行
    返回 (emperor, era, era_year, ganzhi) 或 (None, era, era_year, ganzhi) 续年
    """
    line = line.replace("　", "").replace(" ", "")
    if not line.startswith("●"):
        return None
    body = line[1:]
    emp = None
    for e in EMPERORS:
        if body.startswith(e):
            emp = e[:-2]  # 仁宗皇帝 → 仁宗
            body = body[len(e):]
            break

    # 现在 body 形如:
    # - "景祐三年丙子" / "元丰元年戊午"  (含年号 + 年数 + 干支)
    # - "二年丁丑" / "元年戊午"         (只有年数 + 干支, 年号续上)

    # 必须以 "X年YY" 结尾, YY 是干支两字
    if "年" not in body:
        return None

    year_idx = body.rfind("年")
    after_year = body[year_idx + 1:]
    if len(after_year) != 2:
        return None
    ganzhi = after_year

    before_year = body[:year_idx]
    # before_year 形如 "景祐三" / "二" / "元丰元" / "元"
    # 末尾是年数 (中文数字), 前面可能是年号
    # 先尝试匹配已知年号开头
    era = None
    era_year_str = before_year
    for name in ERA_NAMES:
        if before_year.startswith(name):
            era = name
            era_year_str = before_year[len(name):]
            break

    if not era_year_str:
        return None
    era_year = cn_to_int(era_year_str)
    if era_year is None:
        return None

    return {
        "emperor": emp,
        "era": era,
        "era_year": era_year,
        "ganzhi": ganzhi,
    }


def reign_to_gregorian(era, era_year):
    """元丰二年 → 1079"""
    for emp, name, start in REIGN_TABLE:
        if name == era:
            return start + era_year - 1
    return None


def parse_biography(text):
    """主解析: 把年谱拆为按年的字典列表"""
    lines = text.split("\n")
    records = []
    current = None
    current_era = None
    current_emp = None
    buffer = []

    for line in lines:
        stripped = line.strip().lstrip("　").lstrip()
        marker = parse_year_marker(stripped) if stripped.startswith("●") else None
        if marker:
            # 保存上一年
            if current is not None:
                current["raw_text"] = "\n".join(buffer).strip()
                records.append(current)
            # 新年
            era = marker["era"] or current_era
            emp = marker["emperor"] or current_emp
            if marker["era"]:
                current_era = marker["era"]
            if marker["emperor"]:
                current_emp = marker["emperor"]
            year = reign_to_gregorian(era, marker["era_year"])
            current = {
                "year": year,
                "era": era,
                "era_year": marker["era_year"],
                "ganzhi": marker["ganzhi"],
                "emperor": emp,
                "age": year - 1037 if year else None,
            }
            buffer = []
        else:
            if current is not None and stripped:
                buffer.append(stripped)

    if current is not None:
        current["raw_text"] = "\n".join(buffer).strip()
        records.append(current)

    return records


def annotate_significance(records):
    """
    对每年标 significance 1-5:
    5 = 思想史/生命级关键 (中进士、廷杖式打击、贬地起点、卒)
    4 = 政治/家庭重大 (升迁、丧亲、北归)
    3 = 一般任职变动
    2 = 平常 (有诗文创作)
    1 = 几乎空白 (无重大事件)
    """
    # 已知关键年份
    SIG5 = {1057, 1066, 1079, 1080, 1094, 1097, 1101}
    SIG4 = {1071, 1086, 1089, 1093, 1100}
    for r in records:
        y = r.get("year")
        if y in SIG5:
            r["significance"] = 5
        elif y in SIG4:
            r["significance"] = 4
        elif r.get("raw_text", "") == "":
            r["significance"] = 1
        elif len(r.get("raw_text", "")) < 50:
            r["significance"] = 2
        else:
            r["significance"] = 3
    return records


def main():
    text = RAW.read_text(encoding="utf-8")
    records = parse_biography(text)
    records = annotate_significance(records)

    # 加事件类别 (基于已知 treatment 节点)
    EVENT_LABELS = {
        1037: "生于眉山",
        1057: "中进士",
        1061: "授大理评事、凤翔府签判",
        1066: "父苏洵卒",
        1071: "上书反新法, 通判杭州",
        1074: "知密州",
        1077: "知徐州",
        1079: "湖州任上被捕, 乌台诗案",
        1080: "谪黄州团练副使",
        1082: "作前后赤壁赋、念奴娇赤壁怀古",
        1085: "神宗崩, 旧党起复",
        1086: "翰林学士",
        1089: "知杭州 (修苏堤)",
        1091: "召还",
        1093: "哲宗亲政, 新党起复",
        1094: "谪惠州",
        1097: "谪儋州 (海南)",
        1100: "哲宗崩, 量移廉州",
        1101: "卒于江苏常州",
    }
    for r in records:
        if r.get("year") in EVENT_LABELS:
            r["event"] = EVENT_LABELS[r["year"]]

    OUT_JSON.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 摘要打印
    print(f"=== Parsed {len(records)} years from 东坡先生年谱 ===")
    print(f"年份范围: {records[0]['year']} - {records[-1]['year']}")
    print(f"覆盖跨度: {records[-1]['year'] - records[0]['year'] + 1} 年")
    print()
    print("=== significance=5 关键年份 ===")
    for r in records:
        if r.get("significance") == 5:
            event = r.get("event", "")
            text_len = len(r.get("raw_text", ""))
            print(f"  {r['year']} (岁 {r['age']:2d}, {r.get('emperor')}{r.get('era')}{r['era_year']}年{r['ganzhi']}) "
                  f"{event} [正文 {text_len} 字]")

    print()
    print(f"=== 输出 ===")
    print(f"  {OUT_JSON}")
    print(f"  共 {len(records)} 条记录")


if __name__ == "__main__":
    main()
