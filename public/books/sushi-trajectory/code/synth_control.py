"""
synth_control.py
对 1079 乌台诗案的合成控制分析

目标维度: 8 维 + 9 主题里被 ITS 标为有信号的几个 (D2 自我修正, 贬谪, 黄州)
+ 对照: ITS 不显著的 D7 隐逸 / D8 三教融合, 看合成控制是否能挖出 ITS 漏掉的效应

donor pool: 同源数据中其他不相关概念
"""
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSON_YEARLY = PROJECT_ROOT / "data" / "corpus" / "personality_yearly.json"
CONCEPT_YEARLY = PROJECT_ROOT / "data" / "corpus" / "concept_yearly.json"
OUT = PROJECT_ROOT / "data" / "corpus" / "synth_control_results.json"

TREATMENT = 1079
PRE_START = 1056
POST_END = 1101


def solve_weights(Y_pre_target, X_pre_donors):
    """
    解 min ||Y_pre - X_pre @ w||^2  s.t. w >= 0, sum(w) = 1
    Y_pre_target: (T_pre,)
    X_pre_donors: (T_pre, J)
    """
    J = X_pre_donors.shape[1]
    w0 = np.ones(J) / J

    def loss(w):
        diff = Y_pre_target - X_pre_donors @ w
        return (diff ** 2).sum()

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(0.0, 1.0)] * J
    res = minimize(loss, w0, method="SLSQP",
                   constraints=constraints, bounds=bounds,
                   options={"maxiter": 200, "ftol": 1e-9})
    return res.x, res.fun


def main():
    person = {int(k): v for k, v in json.load(PERSON_YEARLY.open()).items()}
    concept = {int(k): v for k, v in json.load(CONCEPT_YEARLY.open()).items()}

    sample_p = next(iter(person.values()))
    DIMS = [k for k in sample_p if k.startswith("D") and "__" not in k]
    sample_c = next(iter(concept.values()))
    THEMES = [k for k in sample_c if k not in ("n_pieces", "total_chars")]

    # 目标 series 列表 (跨 personality + concept)
    targets = ["D2_自我修正", "D7_隐逸倾向", "D8_三教融合",
               "贬谪", "佛家", "归隐"]
    donor_candidates = ["D1_政治姿态", "D3_实践导向", "D5_决断力", "D6_情感深度",
                        "儒家纲领", "道家", "情感", "君臣", "文学"]

    # 收集所有年份共同 (1056 之前过早, 1079 排除)
    years_all = sorted(set(person) | set(concept))
    years_used = [y for y in years_all if PRE_START <= y <= POST_END and y != TREATMENT]
    years_pre = [y for y in years_used if y < TREATMENT]
    years_post = [y for y in years_used if y > TREATMENT]

    def get_series(name):
        """返回该序列在所有 years_used 上的值"""
        d = person if name in DIMS else concept
        out = []
        for y in years_used:
            if y in d and name in d[y]:
                out.append(d[y][name])
            else:
                out.append(None)
        return out

    # 构造 donor 矩阵
    donor_data = {name: get_series(name) for name in donor_candidates}

    results = {}
    print(f"=== 合成控制结果 (1079 治疗, pre {len(years_pre)} 年, post {len(years_post)} 年) ===")
    print(f"  {'目标':14s}  {'pre 拟合 RMSE':>12s}  {'post 偏离均值':>14s}  {'placebo p (rough)':>17s}")

    for target in targets:
        y = get_series(target)
        # 切 pre / post
        idx_pre = [i for i, year in enumerate(years_used) if year < TREATMENT]
        idx_post = [i for i, year in enumerate(years_used) if year > TREATMENT]

        Y_pre = np.array([y[i] for i in idx_pre], dtype=float)
        Y_post = np.array([y[i] for i in idx_post], dtype=float)

        # 构造 donor 矩阵 (剔除 None)
        valid_donors = []
        donor_names = []
        for dn, dvals in donor_data.items():
            arr = np.array([dvals[i] for i in idx_pre], dtype=float)
            if np.all(np.isfinite(arr)):
                valid_donors.append(arr)
                donor_names.append(dn)
        X_pre = np.column_stack(valid_donors)

        # 解权重
        w, ss = solve_weights(Y_pre, X_pre)
        rmse_pre = math.sqrt(ss / len(Y_pre))

        # post 反事实
        X_post = np.column_stack([np.array([donor_data[dn][i] for i in idx_post], dtype=float)
                                  for dn in donor_names])
        Y_post_counter = X_post @ w
        gap_post = Y_post - Y_post_counter
        mean_gap = gap_post.mean()

        # Placebo: 把每个 donor 当 "假 target", 看它的 post-gap 分布
        placebo_gaps = []
        for placebo_target in donor_names:
            y_pl = np.array([donor_data[placebo_target][i] for i in idx_pre], dtype=float)
            other_donors = [donor_data[dn] for dn in donor_names if dn != placebo_target]
            X_pl = np.column_stack([np.array([od[i] for i in idx_pre], dtype=float)
                                     for od in other_donors])
            w_pl, _ = solve_weights(y_pl, X_pl)
            X_pl_post = np.column_stack([np.array([od[i] for i in idx_post], dtype=float)
                                          for od in other_donors])
            y_pl_post = np.array([donor_data[placebo_target][i] for i in idx_post], dtype=float)
            gap_pl = y_pl_post - X_pl_post @ w_pl
            placebo_gaps.append(gap_pl.mean())

        # p ≈ rank of |mean_gap| 在 placebo + 1 个 real 里的排位
        all_gaps = sorted(placebo_gaps + [mean_gap], key=lambda x: -abs(x))
        p_rough = (all_gaps.index(mean_gap) + 1) / (len(placebo_gaps) + 1)

        results[target] = {
            "rmse_pre": rmse_pre,
            "mean_gap_post": mean_gap,
            "placebo_gaps": placebo_gaps,
            "p_rough": p_rough,
            "donor_weights": {dn: float(wi) for dn, wi in zip(donor_names, w)},
        }
        sig = "***" if p_rough <= 0.10 else "**" if p_rough <= 0.20 else "*" if p_rough <= 0.30 else ""
        print(f"  {target:14s}  {rmse_pre:>12.3f}  {mean_gap:>+14.3f}  {p_rough:>17.3f} {sig}")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
