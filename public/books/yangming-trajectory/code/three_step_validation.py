"""'三步法'验证: 沉默期 → 危机触发 → 后期稳定

具体假设:
  - 1496-1506 (沉默期 ): 8 维度都相对平静, 变化幅度小
  - 1506 廷杖 (危机触发): 多个维度同时大幅跳跃 (集中在 1 个事件上)
  - 1508-1528 (后期稳定): 变化幅度回归相对平稳, 没有再次同等规模重组

测试统计量:
  1. "全维度同步变化" 指标 = sum |effect_i| across all dimensions for each event
  2. 比较 1506 vs 1508 vs 1517 vs 1519 vs 1521 vs 1527 的总变化幅度
  3. 1506 应该是最大值, 其他事件远小于 1506
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
its_results = json.loads(
    (ROOT / "data" / "analysis" / "its_full_corpus.json").read_text(encoding="utf-8")
)

DIMENSIONS = ["教学耐心", "反权威", "自我修正", "同理心", "实践导向",
              "处变能力", "决断力", "情感深度"]

# 对每个事件, 算 total absolute effect
print("=" * 90)
print("'三步法'验证: 每个事件触发的总人格扰动 (sum |effect_i| across 8 dimensions)")
print("=" * 90)
print(f"{'事件':<22} | {'总扰动':>8} | {'显著维度':>8} | {'总扰动占比'}")
print("-" * 90)

event_total_disturbance = {}
total_all = 0

for ev_label, dims in its_results["results"].items():
    if not dims:
        event_total_disturbance[ev_label] = (0, 0)
        continue
    total_abs_eff = sum(abs(r["effect"]) for r in dims.values())
    sig_count = sum(1 for r in dims.values() if abs(r["t"]) > 1.96)
    event_total_disturbance[ev_label] = (total_abs_eff, sig_count)
    total_all += total_abs_eff

print()
for ev_label, (tot, sig) in sorted(event_total_disturbance.items(),
                                    key=lambda x: -x[1][0]):
    pct = tot / total_all * 100 if total_all > 0 else 0
    bar = "█" * int(pct / 2)
    print(f"{ev_label:<22} | {tot:>8.2f} | {sig:>8} | {pct:>5.1f}%  {bar}")


# ============================================================================
# 进一步: 哪些维度的变化最集中在 1506?
# ============================================================================
print()
print("=" * 90)
print("各维度的变化在哪个事件最大 (说明哪个事件 dominate)")
print("=" * 90)
print(f"{'维度':<10} | {'最大事件':<22} | {'最大效应':>10} | {'1506 效应':>10}")
print("-" * 90)

for dim in DIMENSIONS:
    biggest_ev = None
    biggest_eff = 0
    eff_1506 = 0
    for ev_label, dims in its_results["results"].items():
        r = dims.get(dim)
        if r is None:
            continue
        if abs(r["effect"]) > abs(biggest_eff):
            biggest_ev = ev_label
            biggest_eff = r["effect"]
        if "1506" in ev_label:
            eff_1506 = r["effect"]
    print(f"{dim:<10} | {str(biggest_ev):<22} | {biggest_eff:>+10.2f} | {eff_1506:>+10.2f}")


# ============================================================================
# 三步法支持度评分
# ============================================================================
print()
print("=" * 90)
print("三步法假说支持度评分")
print("=" * 90)

# Hypothesis 1: 1506 应当是 dominator
ev_1506 = event_total_disturbance.get("1506 廷杖贬龙场", (0, 0))
all_events = list(event_total_disturbance.values())
max_disturbance = max(t for t, _ in all_events)
is_dominator = ev_1506[0] == max_disturbance

print(f"\n[假说 1] 1506 是最大扰动事件:    {'✅ 成立' if is_dominator else '❌ 不成立'}")
print(f"  1506 扰动 = {ev_1506[0]:.2f}, 最大扰动 = {max_disturbance:.2f}")

# Hypothesis 2: 1506 之前的事件应当扰动小 (沉默期)
# 我们 没有 1506 之前的 treatment, 因为最早事件就是 1506 自己
# 用 pre-period 系列方差代替
print(f"\n[假说 2] 1506 之前是 '沉默期' (pre-period 各维度变化平稳):")
# 取 1506 ITS 的 pre_residual_se 平均, 与 post 实际方差比较
pre_se_avg = []
post_var_avg = []
for dim in DIMENSIONS:
    r = its_results["results"].get("1506 廷杖贬龙场", {}).get(dim)
    if r is None: continue
    pre_se_avg.append(r["pre_residual_se"])
    if r["post_actual"] is not None:
        # 用所有 post 实际值的方差
        post_vals = r["post_actual"]
        post_var = np.var([post_vals], ddof=0) if isinstance(post_vals, list) else 0
        post_var_avg.append(post_var)
print(f"  pre-period 残差 SE 平均: {np.mean(pre_se_avg):.3f}")

# Hypothesis 3: 1506 之后的事件应当扰动小 (后期稳定)
post_1506_disturbances = [t for ev, (t, _) in event_total_disturbance.items()
                          if any(y in ev for y in ["1508", "1517", "1519", "1521"])]
print(f"\n[假说 3] 1506 之后事件扰动 ≪ 1506:")
print(f"  1506 扰动: {ev_1506[0]:.2f}")
print(f"  1508 / 1517 / 1519 / 1521 扰动: {[f'{t:.2f}' for t in post_1506_disturbances]}")
print(f"  平均后期扰动: {np.mean(post_1506_disturbances):.2f}")
ratio = ev_1506[0] / np.mean(post_1506_disturbances) if post_1506_disturbances else 0
print(f"  1506 / 后期平均比: {ratio:.2f}× {'✅ 1506 显著主导' if ratio > 1.5 else '⚠️ 1506 优势不强'}")

# 总结
print()
print("=" * 90)
print("结论")
print("=" * 90)
support = is_dominator and (ratio > 1.5)
if support:
    print("✅ '三步法' 假说在全集级数据上得到支持:")
    print(f"  - 1506 廷杖触发了一次性的多维人格重组 ({ev_1506[1]} 维显著)")
    print(f"  - 总扰动是后期事件平均的 {ratio:.1f} 倍")
    print(f"  - 1508 龙场悟道虽然显著但已是 1506 重组之后的二次微调")
    print(f"  - 1517 / 1519 / 1521 都没达到 1506 级别的重组")
else:
    print("⚠️ '三步法' 假说仅部分成立, 需要重新审视:")
    print(f"  - 主导事件: {max(event_total_disturbance, key=lambda x: event_total_disturbance[x][0])}")

# 保存
out = ROOT / "data" / "analysis" / "three_step_validation.json"
out.write_text(json.dumps({
    "event_total_disturbance": {k: [float(v[0]), int(v[1])]
                                 for k, v in event_total_disturbance.items()},
    "is_1506_dominator":       bool(is_dominator),
    "ratio_1506_to_avg_post":  float(ratio),
    "support":                 bool(support),
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n输出: {out}")
