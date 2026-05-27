"""
genre_fe.py
跨体裁人格分析: 8 维度 × 体裁均值 + 体裁固定效应回归

数据: sushi_personality.jsonl 已有 char_count + genre_raw + 8 维度评分
"""
import json
from pathlib import Path
from collections import defaultdict
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSON_JSONL = PROJECT_ROOT / "data" / "corpus" / "sushi_personality.jsonl"
OUT = PROJECT_ROOT / "data" / "corpus" / "genre_fe_results.json"


def main():
    records = []
    with PERSON_JSONL.open(encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    print(f"加载 {len(records)} 篇")

    # 8 维度名
    DIMS = ["D1_政治姿态", "D2_自我修正", "D3_实践导向", "D4_处变能力",
            "D5_决断力", "D6_情感深度", "D7_隐逸倾向", "D8_三教融合"]

    # ---------- 8 维度 × 体裁均值表 ----------
    genre_dim_table = defaultdict(lambda: defaultdict(list))
    for r in records:
        g = r.get("genre_raw")
        if not g or g == "unknown":
            continue
        for dim in DIMS:
            key = f"{dim}__total_per1k"
            if key in r:
                genre_dim_table[g][dim].append(r[key])

    GENRES = sorted(genre_dim_table.keys(),
                    key=lambda g: -len(next(iter(genre_dim_table[g].values()))))

    print()
    print(f"=== 8 维度按体裁的均值 (per1k 字) ===")
    header = f"  {'体裁':10s} {'n':>5s}  " + "  ".join(f"{d.split('_')[0]:>6s}" for d in DIMS)
    print(header)
    print("  " + "-" * (len(header) - 2))
    table_means = {}
    for g in GENRES:
        n = len(genre_dim_table[g][DIMS[0]])
        if n < 5:
            continue
        row_vals = []
        for dim in DIMS:
            vals = genre_dim_table[g][dim]
            m = np.mean(vals) if vals else 0
            row_vals.append(m)
            table_means.setdefault(g, {})[dim] = float(m)
        row_str = "  ".join(f"{v:>6.2f}" for v in row_vals)
        print(f"  {g:10s} {n:>5d}  {row_str}")
    print()

    # ---------- 跨体裁极值与解读 ----------
    print(f"=== 每个维度的极值体裁 ===")
    for dim in DIMS:
        vals_per_genre = [(g, table_means[g][dim]) for g in table_means]
        max_g = max(vals_per_genre, key=lambda x: x[1])
        min_g = min(vals_per_genre, key=lambda x: x[1])
        print(f"  {dim}: 最高 {max_g[0]} ({max_g[1]:.2f}), 最低 {min_g[0]} ({min_g[1]:.2f}), "
              f"跨度 {max_g[1] - min_g[1]:.2f}")
    print()

    # ---------- 双 FE 回归: y = α_g + β_pre + γ_post + ε ----------
    # 对每个维度独立做
    print(f"=== 体裁与时段双 FE 回归 (post=1) on 编年篇目 ===")
    print(f"  {'维度':18s}  {'naive ITS β':>12s}  {'FE β':>10s}  {'FE - naive':>12s}")

    fe_results = {}
    for dim in DIMS:
        rows = []  # (y, genre, post)
        for r in records:
            y = r.get("year")
            if not y or r.get("year_confidence") not in ("high", "medium", "low"):
                continue
            if y == 1079:
                continue
            g = r.get("genre_raw")
            if not g or g == "unknown":
                continue
            key = f"{dim}__total_per1k"
            if key not in r:
                continue
            post = 1.0 if y >= 1080 else 0.0
            rows.append((r[key], g, post))

        if len(rows) < 50:
            continue

        ys = np.array([x[0] for x in rows])
        posts = np.array([x[2] for x in rows])

        # naive: y = α + β * post
        X_naive = np.column_stack([np.ones_like(posts), posts])
        beta_naive = np.linalg.lstsq(X_naive, ys, rcond=None)[0]
        beta_post_naive = beta_naive[1]

        # FE: y = α_g + β * post
        genres_used = sorted(set(x[1] for x in rows))
        G = len(genres_used)
        g_idx = {g: i for i, g in enumerate(genres_used)}
        # 体裁 one-hot 不含截距 (drop 最后一个避免共线)
        X_fe = np.zeros((len(rows), G + 1))  # G - 1 个 dummy + 截距 + post
        for i, (_, g, p) in enumerate(rows):
            j = g_idx[g]
            if j < G - 1:
                X_fe[i, j] = 1.0
            X_fe[i, -2] = 1.0  # 截距 (代表 dropped genre)
            X_fe[i, -1] = p
        beta_fe = np.linalg.lstsq(X_fe, ys, rcond=None)[0]
        beta_post_fe = beta_fe[-1]

        diff = beta_post_fe - beta_post_naive
        fe_results[dim] = {
            "n": len(rows),
            "beta_post_naive": float(beta_post_naive),
            "beta_post_fe": float(beta_post_fe),
            "diff_naive_to_fe": float(diff),
        }
        print(f"  {dim:18s}  {beta_post_naive:>+12.3f}  {beta_post_fe:>+10.3f}  {diff:>+12.3f}")

    OUT.write_text(json.dumps({
        "genre_means": table_means,
        "fe_results": fe_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
