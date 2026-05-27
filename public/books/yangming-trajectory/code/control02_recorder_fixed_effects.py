"""控制 2: 记录者固定效应回归

担心: "1517 徐爱卒后自我修正 + 实践导向跳跃" 可能是因为 1517 之后记录者从徐爱
      换成了陆澄, 而陆澄本人记录方式就不同 (记录者污染), 不是阳明自己变了.

控制方式: 用 OLS 回归
  score ~ time_period_T2..T6 + recorder_FE

如果时段系数仍然显著 → 即使控制了记录者, 时段效应仍存在, 是真信号
如果时段系数被吸收 → 之前的时段效应被记录者效应解释掉了, 不能归因到事件
"""
import json
from pathlib import Path
from collections import defaultdict

import numpy as np

from personality_markers import DIMENSIONS

ROOT = Path(__file__).resolve().parent.parent
entries = [json.loads(line) for line in
           (ROOT / "data" / "analysis" / "personality_per_entry.jsonl").open(encoding="utf-8")]

# 给每条记录加 recorder (从 chuanxilu_enriched 来)
enriched = {}
for line in (ROOT / "data" / "corpus" / "chuanxilu_343.jsonl").open(encoding="utf-8"):
    e = json.loads(line)
    enriched[e["id"]] = e

for e in entries:
    e["recorder"] = enriched[e["id"]].get("recorder_or_addressee") or "(无)"


# ============================================================================
# OLS: score_i ~ alpha + sum beta_p * I(period==p) + sum gamma_r * I(recorder==r) + eps
# 用 dummy 编码, 基线: T1 + 徐爱
# ============================================================================
def ols_with_recorder_fe(records, dim, baseline_period="T1", baseline_recorder="徐爱"):
    """返回时段系数 + SE + t."""
    periods   = ["T1", "T2", "T3", "T4", "T5", "T6"]
    recorders = sorted(set(r["recorder"] for r in records))

    p_dummies = [p for p in periods if p != baseline_period]
    r_dummies = [r for r in recorders if r != baseline_recorder]

    # 构建 X 矩阵
    n = len(records)
    k = 1 + len(p_dummies) + len(r_dummies)  # 1 = intercept
    X = np.zeros((n, k))
    y = np.zeros(n)
    for i, e in enumerate(records):
        X[i, 0] = 1  # intercept
        for j, p in enumerate(p_dummies):
            if e["time_period"] == p:
                X[i, 1 + j] = 1
        for j, r in enumerate(r_dummies):
            if e["recorder"] == r:
                X[i, 1 + len(p_dummies) + j] = 1
        y[i] = e["scores"][dim]["net"]

    # 解 normal equation
    try:
        XtX_inv = np.linalg.inv(X.T @ X + 1e-8 * np.eye(k))
    except np.linalg.LinAlgError:
        return None
    beta = XtX_inv @ X.T @ y
    y_hat = X @ beta
    resid = y - y_hat
    sigma2 = float(np.sum(resid ** 2) / max(n - k, 1))
    var_beta = sigma2 * np.diag(XtX_inv)
    se = np.sqrt(np.maximum(var_beta, 0))

    coef = {"intercept": float(beta[0])}
    se_d = {"intercept": float(se[0])}
    for j, p in enumerate(p_dummies):
        coef[f"period_{p}"] = float(beta[1 + j])
        se_d[f"period_{p}"] = float(se[1 + j])
    for j, r in enumerate(r_dummies):
        coef[f"recorder_{r}"] = float(beta[1 + len(p_dummies) + j])
        se_d[f"recorder_{r}"] = float(se[1 + len(p_dummies) + j])
    return {"coef": coef, "se": se_d, "n": n, "k": k}


def ols_period_only(records, dim, baseline_period="T1"):
    """无记录者 FE 的对照: score ~ period only"""
    periods = ["T1", "T2", "T3", "T4", "T5", "T6"]
    p_dummies = [p for p in periods if p != baseline_period]
    n = len(records)
    k = 1 + len(p_dummies)
    X = np.zeros((n, k))
    y = np.zeros(n)
    for i, e in enumerate(records):
        X[i, 0] = 1
        for j, p in enumerate(p_dummies):
            if e["time_period"] == p:
                X[i, 1 + j] = 1
        y[i] = e["scores"][dim]["net"]
    try:
        XtX_inv = np.linalg.inv(X.T @ X + 1e-8 * np.eye(k))
    except np.linalg.LinAlgError:
        return None
    beta = XtX_inv @ X.T @ y
    y_hat = X @ beta
    resid = y - y_hat
    sigma2 = float(np.sum(resid ** 2) / max(n - k, 1))
    var_beta = sigma2 * np.diag(XtX_inv)
    se = np.sqrt(np.maximum(var_beta, 0))
    coef, se_d = {"intercept": float(beta[0])}, {"intercept": float(se[0])}
    for j, p in enumerate(p_dummies):
        coef[f"period_{p}"] = float(beta[1 + j])
        se_d[f"period_{p}"] = float(se[1 + j])
    return {"coef": coef, "se": se_d, "n": n, "k": k}


# ============================================================================
# 跑 5 个维度
# ============================================================================
print("=" * 100)
print("时段系数 (相对于基线 T1): 无 vs 有记录者 FE")
print("=" * 100)
print(f"{'维度':<8} | {'时段':<6} | {'无 FE β':>9} {'(SE)':>9} | "
      f"{'+记录者 FE β':>12} {'(SE)':>9} | {'变化':>10}")
print("-" * 100)

results = {}
for dim in DIMENSIONS:
    r_no_fe = ols_period_only(entries, dim)
    r_fe    = ols_with_recorder_fe(entries, dim)
    if r_no_fe is None or r_fe is None:
        continue

    results[dim] = {"no_fe": r_no_fe, "fe": r_fe}

    for p in ["T2", "T3", "T4", "T5", "T6"]:
        b1 = r_no_fe["coef"][f"period_{p}"]
        s1 = r_no_fe["se"][f"period_{p}"]
        b2 = r_fe["coef"][f"period_{p}"]
        s2 = r_fe["se"][f"period_{p}"]
        change = abs(b2 - b1) / max(abs(b1), 1e-6) * 100
        t1 = b1/s1 if s1 > 1e-6 else 0
        t2 = b2/s2 if s2 > 1e-6 else 0
        sig1 = "★★★" if abs(t1) > 2.58 else "★★" if abs(t1) > 1.96 else "★" if abs(t1) > 1.64 else ""
        sig2 = "★★★" if abs(t2) > 2.58 else "★★" if abs(t2) > 1.96 else "★" if abs(t2) > 1.64 else ""
        change_str = f"{change:.0f}%"
        if abs(b2) > abs(b1):
            change_str = "↑" + change_str
        elif abs(b2) < abs(b1):
            change_str = "↓" + change_str
        print(f"{dim:<8} | {p:<6} | {b1:>9.3f}{sig1:<3} {s1:>5.2f} | "
              f"{b2:>9.3f}{sig2:<3} {s2:>5.2f} | {change_str:>10}")
    print()

# ============================================================================
# 关键问: 1517 徐爱卒后效应在控制记录者后是否仍存在?
# T2/T3/T4 vs T1 的系数应该和"徐爱卒后" pre/post 差异有方向一致性
# ============================================================================
print("\n" + "=" * 100)
print("关键问: 1517 徐爱卒后效应在控制记录者后是否仍存在?")
print("       (T2 系数 = T2 相对 T1 / 徐爱 的差异; 显著 ★★ 即可视为存在)")
print("=" * 100)
print(f"{'维度':<10} | {'无 FE T2 β':<14} | {'+FE T2 β':<14} | {'解读'}")
print("-" * 100)

for dim in DIMENSIONS:
    if dim not in results:
        continue
    r1 = results[dim]
    b1 = r1["no_fe"]["coef"]["period_T2"]
    s1 = r1["no_fe"]["se"]["period_T2"]
    b2 = r1["fe"]["coef"]["period_T2"]
    s2 = r1["fe"]["se"]["period_T2"]
    t1 = b1/s1 if s1 > 1e-6 else 0
    t2 = b2/s2 if s2 > 1e-6 else 0
    sig1 = "★★★" if abs(t1) > 2.58 else "★★" if abs(t1) > 1.96 else "★" if abs(t1) > 1.64 else "ns"
    sig2 = "★★★" if abs(t2) > 2.58 else "★★" if abs(t2) > 1.96 else "★" if abs(t2) > 1.64 else "ns"

    if "★" in sig1 and "★" in sig2:
        verdict = "✓ 控制记录者后仍显著, 是真信号"
    elif "★" in sig1 and "ns" == sig2:
        verdict = "✗ 控制后消失, 之前发现可能被记录者效应混淆"
    elif "ns" == sig1 and "★" in sig2:
        verdict = "△ 控制后才显著, 控制前被记录者效应掩盖"
    else:
        verdict = "— 两种规格都不显著"
    print(f"{dim:<10} | {b1:+7.2f}({sig1:>3}) | {b2:+7.2f}({sig2:>3}) | {verdict}")

# 保存
out = ROOT / "data" / "analysis" / "control_recorder_fe.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")
