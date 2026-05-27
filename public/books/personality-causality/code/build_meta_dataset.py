"""
build_meta_dataset.py
合并阳明 / 苏轼 / 曾国藩三本书的 ITS 结果, 生成跨被试 meta-analysis 数据集。

每个案例 × 每个维度 → 一条记录, 含:
  - subject (阳明 / 苏轼 / 曾国藩)
  - treatment (1506 / 1079 / 1853)
  - dim (D1 ... D8 + 9 主题)
  - beta (level shift)
  - t_stat
  - se (从 beta / t 反推)
  - n_year (pre + post 年份数)
"""

import json
from pathlib import Path

BASE = Path(__file__).parent.parent.parent

SUSHI_FILE = BASE / "SushiTrajectory/data/corpus/its_wutai_results.json"
ZENG_FILE = BASE / "ZengGuofanTrajectory/data/corpus/its_results_v2.json"
GU_FILE = BASE / "GuYanwuTrajectory/data/corpus/its_poems.json"


def load_sushi():
    """苏轼 ITS 文件结构: { dim_name: {beta_level: ..., t_level: ..., n_year: ...} }"""
    data = json.load(open(SUSHI_FILE))
    records = []
    for dim, d in data.items():
        if not isinstance(d, dict):
            continue
        beta = d.get("beta2_level_shift") or d.get("beta_level") or d.get("level") or d.get("β2")
        t = d.get("t_level_shift") or d.get("t_level") or d.get("t") or d.get("t_β2")
        n_year = d.get("n") or d.get("n_year") or 37
        if beta is None or t is None:
            continue
        records.append({
            "subject": "苏轼",
            "treatment_year": 1079,
            "treatment_event": "乌台诗案",
            "dim": dim,
            "beta": float(beta),
            "t_stat": float(t),
            "se": abs(float(beta) / float(t)) if abs(float(t)) > 0.01 else None,
            "n_year": int(n_year),
        })
    return records


def load_zeng():
    """曾国藩 ITS: { '1853': { dim: {beta, t, ...} }, ... }"""
    data = json.load(open(ZENG_FILE))
    records = []
    for year_str, dims in data.items():
        year = int(year_str)
        # 只取 1853 作为核心 treatment (与阳明 1506、苏轼 1079 对应)
        if year != 1853:
            continue
        for dim, d in dims.items():
            if not isinstance(d, dict):
                continue
            beta = d.get("beta2") or d.get("beta_level") or d.get("beta") or d.get("level")
            t = d.get("t_stat") or d.get("t_level") or d.get("t")
            n_year = d.get("n") or d.get("n_year") or 25
            if beta is None or t is None:
                continue
            records.append({
                "subject": "曾国藩",
                "treatment_year": year,
                "treatment_event": "创湘军",
                "dim": dim,
                "beta": float(beta),
                "t_stat": float(t),
                "se": abs(float(beta) / float(t)) if abs(float(t)) > 0.01 else None,
                "n_year": int(n_year),
            })
    return records


def load_yangming_from_text():
    """
    阳明 ITS 没有独立 json, 从 chap01.tex 等已经写好的章节里硬编码核心数字。
    数字来源: YangmingTrajectory/chapters/chap01.tex 的 ITS 结果表
    1506 廷杖 treatment, 8 维 + 部分主题
    """
    # 阳明 chap01 实际报告的 ITS β / t 值 (1506 廷杖)
    yangming_its = {
        "D1_政治姿态":     {"beta": -0.42, "t": -0.68, "n_year": 24},
        "D2_自我修正":     {"beta": +2.18, "t": +1.95, "n_year": 24},
        "D3_实践导向":     {"beta": +1.83, "t": +2.14, "n_year": 24},
        "D4_处变能力":     {"beta": -7.05, "t": -3.21, "n_year": 24},
        "D5_决断力":       {"beta": +0.55, "t": +0.42, "n_year": 24},
        "D6_情感深度":     {"beta": +1.04, "t": +0.81, "n_year": 24},
        "D7_隐逸倾向":     {"beta": +2.91, "t": +1.62, "n_year": 24},
        "D8_三教融合":     {"beta": +3.18, "t": +1.78, "n_year": 24},
    }
    records = []
    for dim, d in yangming_its.items():
        records.append({
            "subject": "阳明",
            "treatment_year": 1506,
            "treatment_event": "廷杖",
            "dim": dim,
            "beta": d["beta"],
            "t_stat": d["t"],
            "se": abs(d["beta"] / d["t"]) if abs(d["t"]) > 0.01 else None,
            "n_year": d["n_year"],
        })
    return records


def load_gu():
    """顾炎武 ITS: { '1660': { dim: {beta2, t_stat, ...} }, '1667': {...}, '1675': {} }"""
    data = json.load(open(GU_FILE))
    records = []
    for year_str, dims in data.items():
        year = int(year_str)
        # 选 1660 作为核心 treatment (北上避难, 顾炎武最显著的外生冲击)
        if year != 1660:
            continue
        for dim, d in dims.items():
            if not isinstance(d, dict):
                continue
            beta = d.get("beta2") or d.get("beta_level") or d.get("level")
            t = d.get("t_stat") or d.get("t_level") or d.get("t")
            n_year = d.get("n") or d.get("n_year") or 5
            if beta is None or t is None:
                continue
            records.append({
                "subject": "顾炎武",
                "treatment_year": year,
                "treatment_event": "北上避难",
                "dim": dim,
                "beta": float(beta),
                "t_stat": float(t),
                "se": abs(float(beta) / float(t)) if abs(float(t)) > 0.01 else None,
                "n_year": int(n_year),
            })
    return records


def main():
    out = []
    out.extend(load_yangming_from_text())
    print(f"  阳明: {len([r for r in out if r['subject']=='阳明'])} 条")
    out.extend(load_sushi())
    print(f"  + 苏轼: {len([r for r in out if r['subject']=='苏轼'])} 条")
    out.extend(load_zeng())
    print(f"  + 曾国藩: {len([r for r in out if r['subject']=='曾国藩'])} 条")
    out.extend(load_gu())
    print(f"  + 顾炎武: {len([r for r in out if r['subject']=='顾炎武'])} 条")
    print(f"  合计: {len(out)} 条记录")

    out_path = Path(__file__).parent.parent / "data" / "meta_dataset.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n输出: {out_path}")

    # 也存 CSV 便于查看
    csv_path = out_path.with_suffix(".csv")
    with open(csv_path, "w") as f:
        f.write("subject,treatment_year,treatment_event,dim,beta,t_stat,se,n_year\n")
        for r in out:
            se_s = f"{r['se']:.3f}" if r["se"] else ""
            f.write(f"{r['subject']},{r['treatment_year']},{r['treatment_event']},{r['dim']},"
                    f"{r['beta']:+.3f},{r['t_stat']:+.3f},{se_s},{r['n_year']}\n")
    print(f"       {csv_path}")

    # 按 dim 汇总 (跨案例的 8 维)
    print("\n=== 8 维人格 × 4 案例的 β level shift / t 值 ===")
    print(f"  {'维度':<14} {'阳明 1506':<18} {'苏轼 1079':<18} {'曾国藩 1853':<18} {'顾炎武 1660':<18}")
    print("  " + "-" * 92)
    by_dim = {}
    for r in out:
        by_dim.setdefault(r["dim"], {})[r["subject"]] = r
    for dim in ["D1_政治姿态", "D2_自我修正", "D3_实践导向", "D4_处变能力",
                "D5_决断力", "D6_情感深度", "D7_隐逸倾向", "D8_三教融合"]:
        line = f"  {dim:<14}"
        for sub in ["阳明", "苏轼", "曾国藩", "顾炎武"]:
            r = by_dim.get(dim, {}).get(sub)
            if r:
                line += f"  β={r['beta']:+.2f} t={r['t_stat']:+.2f}".ljust(18)
            else:
                line += " " * 18
        print(line)


if __name__ == "__main__":
    main()
