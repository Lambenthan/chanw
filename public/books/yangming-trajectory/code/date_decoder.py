"""日期注释解码器

阳明全集里的 date_annotation 有三种形式:
  1. 年号: "弘治十二年" "正德元年" "嘉靖六年" "十五年八月"
  2. 干支: "甲戌" "壬申" "癸酉" "庚午"
  3. 描述: "时进士" "时官刑部主事" "时官兵部主事"

阳明 1472-1529 之间, 每个干支只出现一次, 所以干支可以唯一定年.
"""
import re

# 明代年号 → 起始公元年
ERA_START = {
    "成化": 1465,  # 1465-1487 (阳明 1472 生)
    "弘治": 1488,  # 1488-1505
    "正德": 1506,  # 1506-1521
    "嘉靖": 1522,  # 1522-1566 (阳明 1529 卒)
}

# 阳明生卒 (1472-1529) 间每个干支只出现一次, 建映射
GANZHI_IN_LIFETIME = {
    # 1472-1529 共 58 年, 干支 60 年循环, 多数干支只出现一次
    "壬辰": 1472,  # 阳明生年
    "癸巳": 1473, "甲午": 1474, "乙未": 1475, "丙申": 1476,
    "丁酉": 1477, "戊戌": 1478, "己亥": 1479, "庚子": 1480,
    "辛丑": 1481, "壬寅": 1482, "癸卯": 1483, "甲辰": 1484,
    "乙巳": 1485, "丙午": 1486, "丁未": 1487, "戊申": 1488,
    "己酉": 1489, "庚戌": 1490, "辛亥": 1491, "壬子": 1492,
    "癸丑": 1493, "甲寅": 1494, "乙卯": 1495, "丙辰": 1496,
    "丁巳": 1497, "戊午": 1498, "己未": 1499, "庚申": 1500,
    "辛酉": 1501, "壬戌": 1502, "癸亥": 1503, "甲子": 1504,
    "乙丑": 1505, "丙寅": 1506, "丁卯": 1507, "戊辰": 1508,  # 戊辰 = 龙场悟道年
    "己巳": 1509, "庚午": 1510, "辛未": 1511, "壬申": 1512,
    "癸酉": 1513, "甲戌": 1514, "乙亥": 1515, "丙子": 1516,
    "丁丑": 1517, "戊寅": 1518, "己卯": 1519, "庚辰": 1520,  # 庚辰 = 平宁王年
    "辛巳": 1521, "壬午": 1522, "癸未": 1523, "甲申": 1524,
    "乙酉": 1525, "丙戌": 1526, "丁亥": 1527, "戊子": 1528,
    "己丑": 1529,  # 阳明卒年
}

# 中文数字 → 阿拉伯
CN_NUM = {
    "元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def parse_cn_year_number(s):
    """'十二' → 12, '元' → 1, '二十一' → 21"""
    s = s.strip()
    if s == "元":
        return 1
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("十"):
        return 10 + CN_NUM.get(s[1:], 0) if len(s) > 1 else 10
    if "十" in s:
        a, b = s.split("十", 1)
        tens = CN_NUM[a] * 10
        ones = CN_NUM.get(b, 0) if b else 0
        return tens + ones
    # 阿拉伯数字
    if s.isdigit():
        return int(s)
    return None


def decode_era(text):
    """从注释里提取年号 + 年数, 返回公元年. 失败返回 None"""
    # "弘治十二年" / "正德元年" / "嘉靖六年"
    for era, start in ERA_START.items():
        m = re.search(rf"{era}([元一二三四五六七八九十\d]+?)年", text)
        if m:
            yr_num = parse_cn_year_number(m.group(1))
            if yr_num is not None:
                return start + yr_num - 1  # 元年 = 起始年
    # "十五年" 这种缺年号的, 暂返回 None (上下文推断要分别处理)
    return None


def decode_ganzhi(text):
    """从注释里找干支并返回对应年份"""
    for gz, yr in GANZHI_IN_LIFETIME.items():
        if gz in text:
            return yr
    return None


def decode_month(text):
    """提取月份, 返回 1-12 或 None"""
    m = re.search(r"([元一二三四五六七八九十\d]+?)月", text)
    if not m:
        return None
    return parse_cn_year_number(m.group(1))


def decode_annotation(text, prev_era=None):
    """主入口: 给定一个 date_annotation, 返回 dict {year, month, confidence, source}

    prev_era: 如果当前注释只有"X 年八月"没说年号, 可以传上篇的年号
    """
    if not text:
        return {"year": None, "month": None, "confidence": None, "source": None}

    text = text.strip()

    # 1. 优先年号
    year = decode_era(text)
    source = "era"

    # 2. 干支
    if year is None:
        year = decode_ganzhi(text)
        source = "ganzhi"

    # 3. 上下文延续 (如"十五年" 接在"弘治十二年"后面)
    if year is None and prev_era:
        m = re.search(r"([元一二三四五六七八九十\d]+)年", text)
        if m:
            yr_num = parse_cn_year_number(m.group(1))
            if yr_num is not None:
                year = ERA_START[prev_era] + yr_num - 1
                source = "context"

    month = decode_month(text)

    if year is None:
        confidence = None
    elif source == "era":
        confidence = "high"
    elif source == "ganzhi":
        confidence = "high"
    elif source == "context":
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "year":       year,
        "month":      month,
        "confidence": confidence,
        "source":     source,
    }


if __name__ == "__main__":
    # 测试
    cases = [
        "弘治十二年，时进士",
        "十五年八月，时官刑部主事",
        "正德元年，时官兵部主事",
        "甲戌",
        "壬申",
        "癸酉",
        "嘉靖六年九月",
        "时官刑部主事",
        "庚辰 时巡抚南赣",
        "戊辰 谪龙场",
    ]
    for c in cases:
        d = decode_annotation(c)
        print(f"  {c:<25} → {d}")
