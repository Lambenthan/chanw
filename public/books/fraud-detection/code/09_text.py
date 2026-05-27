# =====================================================
# code/09_text.py
# 第 9 章：文本特征 —— MD&A 与 Loughran-McDonald 词典
# =====================================================
#
# 计划选择说明（Plan B）
# ----------------------
# 真实世界的方案是 Plan A：从 SEC EDGAR 抓取 Bao 样本对应公司的 10-K
# MD&A 章节，套用 Loughran-McDonald 2011 财务情感词典，配合 Fog Index
# 可读性指标，再把这批文本特征拼到第 6 章 XGBoost 上看增量 AUC。
#
# Plan A 在本书第一版未能完成，根本卡点是：Bao 公开复制包只给 gvkey，
# 不给 ticker，也不给 CIK。把 gvkey 映射到 EDGAR 的 CIK 需要 Compustat
# 提供的 link table（CRSP/CCM 或 WRDS Compustat-CIK link），这两个
# 资源都需要 WRDS 订阅。即便手工映射前 50 家舞弊公司，再走 EDGAR 限速
# 抓取 + 解析 10-K MD&A，整套工程在 30 分钟预算之外。
#
# 因此本章采取 Plan B：
#   1. 用模拟特征演示完整管线 —— LM 四类情感比率、Fog Index、句长方差。
#   2. 模拟值并非纯随机：在舞弊样本里给负面、不确定、诉讼三类词频以
#      "略高于非舞弊样本"的分布偏移，反映文献里的常见发现，但读者必须
#      明白这是受控注入的合成信号，不是真实 10-K 文本测出来的结果。
#   3. 跑一遍基线 XGBoost（财务 42 特征）+ 增强 XGBoost（42 + 6 文本
#      特征），把"如果文本真的有 Δ 信号，AUC 会怎么动"的轮廓算出来。
#   4. 章节正文以及 _NUMBERS.md 都明确标注 Plan B / 合成信号。
#
# 后续版本接入真实 EDGAR 数据后，本脚本的接口（read_csv → fit XGBoost
# → 评估）保持不变，只需把 simulate_text_features() 替换为
# extract_real_text_features()。
# =====================================================

import random
import numpy as np
import pandas as pd
from pathlib import Path

import xgboost as xgb
from sklearn.metrics import roc_auc_score, ndcg_score

random.seed(2026)
np.random.seed(2026)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "bao2020_full.csv"

features_raw = ["act", "ap", "at", "ceq", "che", "cogs", "csho", "dlc",
                "dltis", "dltt", "dp", "ib", "invt", "ivao", "ivst",
                "lct", "lt", "ni", "ppegt", "pstk", "re", "rect",
                "sale", "sstk", "txp", "txt", "xint", "prcc_f"]
features_ratio = ["dch_wc", "ch_rsst", "dch_rec", "dch_inv", "soft_assets",
                  "ch_cs", "ch_cm", "ch_roa", "issue", "bm", "dpi",
                  "reoa", "EBIT", "ch_fcf"]
fin_features = features_raw + features_ratio
assert len(fin_features) == 42

text_features = [
    "lm_positive_ratio",
    "lm_negative_ratio",
    "lm_uncertainty_ratio",
    "lm_litigious_ratio",
    "fog_index",
    "sentence_length_sd",
]


def simulate_text_features(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """合成 LM 四类情感比率、Fog Index 与句长方差。

    设计原则：
      * 非舞弊样本的均值参数取自 Loughran-McDonald 2011 报告的 10-K 总体
        分布（positive 0.75%, negative 1.39%, uncertainty 1.20%,
        litigious 0.85%；Fog Index 均值 19.8）。
      * 舞弊样本在 negative / uncertainty / litigious 三个维度上抬升一个
        小幅 delta，模拟文献观察到的"舞弊年管理层口径更负面、更不确定、
        更涉诉"现象。
      * 同时在 fog_index 与 sentence_length_sd 上抬升，模拟舞弊年报披露
        更冗长、更难读。
      * 注意：所有 delta 都是为演示管线注入的合成偏移；本脚本输出的 AUC
        增量仅供方法学说明，禁止当成真实文本特征的实证结论。
    """
    n = len(df)
    y = df["misstate"].values

    # 基线（非舞弊）
    pos = rng.normal(0.0075, 0.0020, n).clip(min=0)
    neg = rng.normal(0.0139, 0.0030, n).clip(min=0)
    unc = rng.normal(0.0120, 0.0025, n).clip(min=0)
    lit = rng.normal(0.0085, 0.0022, n).clip(min=0)
    fog = rng.normal(19.8, 1.5, n).clip(min=8.0)
    sent_sd = rng.normal(8.0, 1.2, n).clip(min=2.0)

    # 舞弊样本注入小幅偏移（合成信号）
    # delta 故意压得很弱，让 AUC 增量落在文献常见的 1-3 个百分点区间，
    # 避免模拟特征"过度好用"误导读者。
    fraud_mask = (y == 1)
    neg[fraud_mask] += rng.normal(0.0008, 0.0010, fraud_mask.sum()).clip(min=0)
    unc[fraud_mask] += rng.normal(0.0006, 0.0010, fraud_mask.sum()).clip(min=0)
    lit[fraud_mask] += rng.normal(0.0005, 0.0008, fraud_mask.sum()).clip(min=0)
    fog[fraud_mask] += rng.normal(0.15, 0.30, fraud_mask.sum())
    sent_sd[fraud_mask] += rng.normal(0.10, 0.25, fraud_mask.sum())

    out = pd.DataFrame({
        "lm_positive_ratio": pos,
        "lm_negative_ratio": neg,
        "lm_uncertainty_ratio": unc,
        "lm_litigious_ratio": lit,
        "fog_index": fog,
        "sentence_length_sd": sent_sd,
    }, index=df.index)
    return out


def fit_xgb(X_train, y_train, X_valid, y_valid, X_test, y_test, label):
    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    spw = neg / max(pos, 1)
    clf = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        eval_metric="auc",
        early_stopping_rounds=30,
        tree_method="hist",
        random_state=2026,
        n_jobs=4,
    )
    clf.fit(X_train, y_train,
            eval_set=[(X_valid, y_valid)],
            verbose=False)
    p_test = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, p_test)
    n = len(y_test)
    k = max(1, int(round(0.01 * n)))
    order = np.argsort(-p_test)
    top_k = order[:k]
    recall_k = float((y_test[top_k] == 1).sum() / max(int(y_test.sum()), 1))
    precision_k = float((y_test[top_k] == 1).sum() / k)
    rel = np.zeros_like(y_test, dtype=float)
    rel = y_test.astype(float)
    ndcg100 = float(ndcg_score(rel.reshape(1, -1), p_test.reshape(1, -1), k=100))
    print(f"[{label}]")
    print(f"  特征数      : {X_train.shape[1]}")
    print(f"  best_iter   : {clf.best_iteration}")
    print(f"  AUC         : {auc:.4f}")
    print(f"  NDCG@100    : {ndcg100:.4f}")
    print(f"  Recall@1%   : {recall_k:.4f}  (k = {k})")
    print(f"  Precision@1%: {precision_k:.4f}")
    return {
        "label": label,
        "n_features": X_train.shape[1],
        "auc": auc,
        "ndcg100": ndcg100,
        "recall_at_1pct": recall_k,
        "precision_at_1pct": precision_k,
        "best_iter": int(clf.best_iteration) if clf.best_iteration is not None else -1,
        "model": clf,
        "p_test": p_test,
    }


def main():
    print("=" * 60)
    print("Chap 9: 文本特征（Plan B —— 合成 LM 信号演示管线）")
    print("=" * 60)
    print(f"data file   : {DATA}")
    print(f"plan        : B (simulated text features)")
    print(f"text feats  : {text_features}")

    d = pd.read_csv(DATA)

    train = d[(d.fyear >= 1991) & (d.fyear <= 2002)].copy()
    valid = d[(d.fyear >= 2003) & (d.fyear <= 2008)].copy()
    test = d[(d.fyear >= 2009) & (d.fyear <= 2014)].copy()

    n_before = (len(train), len(valid), len(test))
    train = train.dropna(subset=fin_features).reset_index(drop=True)
    valid = valid.dropna(subset=fin_features).reset_index(drop=True)
    test = test.dropna(subset=fin_features).reset_index(drop=True)
    n_after = (len(train), len(valid), len(test))

    print()
    print("--- 样本切分 ---")
    print(f"训练 1991-2002 : {n_before[0]} -> {n_after[0]} (fraud {int(train.misstate.sum())})")
    print(f"验证 2003-2008 : {n_before[1]} -> {n_after[1]} (fraud {int(valid.misstate.sum())})")
    print(f"测试 2009-2014 : {n_before[2]} -> {n_after[2]} (fraud {int(test.misstate.sum())})")

    # ---------- 合成文本特征 ----------
    rng = np.random.default_rng(2026)
    train_text = simulate_text_features(train, rng)
    valid_text = simulate_text_features(valid, rng)
    test_text = simulate_text_features(test, rng)

    print()
    print("--- 合成文本特征：舞弊 vs 非舞弊均值（训练集） ---")
    summary_rows = []
    for col in text_features:
        v_fraud = train_text[col][train.misstate == 1].mean()
        v_clean = train_text[col][train.misstate == 0].mean()
        diff = v_fraud - v_clean
        summary_rows.append((col, v_fraud, v_clean, diff))
        print(f"  {col:24s}  fraud={v_fraud:.4f}  non={v_clean:.4f}  Δ={diff:+.4f}")

    # ---------- 模型 1：财务 42 特征基线 ----------
    print()
    print("=" * 60)
    print("模型 1：XGBoost 基线（42 个财务特征）")
    print("=" * 60)
    Xtr = train[fin_features].values
    Xvl = valid[fin_features].values
    Xte = test[fin_features].values
    ytr = train["misstate"].astype(int).values
    yvl = valid["misstate"].astype(int).values
    yte = test["misstate"].astype(int).values
    res_base = fit_xgb(Xtr, ytr, Xvl, yvl, Xte, yte, "XGBoost-fin42")

    # ---------- 模型 2：财务 + 文本（48 特征） ----------
    print()
    print("=" * 60)
    print("模型 2：XGBoost 增强（42 财务 + 6 合成文本特征）")
    print("=" * 60)
    Xtr2 = np.hstack([Xtr, train_text[text_features].values])
    Xvl2 = np.hstack([Xvl, valid_text[text_features].values])
    Xte2 = np.hstack([Xte, test_text[text_features].values])
    res_aug = fit_xgb(Xtr2, ytr, Xvl2, yvl, Xte2, yte, "XGBoost-fin42+text6")

    # ---------- 增量 ----------
    print()
    print("=" * 60)
    print("增量比较（合成信号；仅作管线演示）")
    print("=" * 60)
    print(f"  ΔAUC      : {res_aug['auc'] - res_base['auc']:+.4f}")
    print(f"  ΔNDCG@100 : {res_aug['ndcg100'] - res_base['ndcg100']:+.4f}")
    print(f"  ΔRecall@1%: {res_aug['recall_at_1pct'] - res_base['recall_at_1pct']:+.4f}")
    print(f"  ΔPrec@1%  : {res_aug['precision_at_1pct'] - res_base['precision_at_1pct']:+.4f}")

    # ---------- 案例公司打分（合成增强模型） ----------
    print()
    print("--- 标志性案例（fyear=2000，真实 misstate=1）---")
    train_full = pd.concat([train.reset_index(drop=True),
                            train_text.reset_index(drop=True)], axis=1)
    cases = train_full[(train_full.gvkey.isin([6127, 10787]))
                       & (train_full.fyear == 2000)]
    if len(cases) > 0:
        Xc = cases[fin_features + text_features].values
        p_aug = res_aug["model"].predict_proba(Xc)[:, 1]
        Xc_base = cases[fin_features].values
        p_base = res_base["model"].predict_proba(Xc_base)[:, 1]
        for i, (_, row) in enumerate(cases.iterrows()):
            tag = "Enron" if int(row["gvkey"]) == 6127 else "Tyco"
            print(f"  {tag:6s} gvkey={int(row['gvkey']):>5d}  "
                  f"p_base={p_base[i]:.4f}  p_aug={p_aug[i]:.4f}")
    else:
        print("  案例公司在训练集中不在 fyear=2000 行（可能因 NA 被剔除）")

    # ---------- 章末汇总输出 ----------
    print()
    print("=" * 60)
    print("章节关键数字（回贴 _NUMBERS.md）")
    print("=" * 60)
    print(f"PLAN              : B (合成文本)")
    print(f"训练 / 验证 / 测试 : {n_after[0]} / {n_after[1]} / {n_after[2]}")
    print(f"测试舞弊数        : {int(test.misstate.sum())}")
    print(f"测试 1% 名额 k    : {max(1, int(round(0.01 * n_after[2])))}")
    print(f"基线 AUC          : {res_base['auc']:.4f}")
    print(f"增强 AUC          : {res_aug['auc']:.4f}")
    print(f"AUC 增量          : {res_aug['auc'] - res_base['auc']:+.4f}")
    print(f"基线 NDCG@100     : {res_base['ndcg100']:.4f}")
    print(f"增强 NDCG@100     : {res_aug['ndcg100']:.4f}")
    print(f"基线 Recall@1%    : {res_base['recall_at_1pct']:.4f}")
    print(f"增强 Recall@1%    : {res_aug['recall_at_1pct']:.4f}")
    print(f"基线 Precision@1% : {res_base['precision_at_1pct']:.4f}")
    print(f"增强 Precision@1% : {res_aug['precision_at_1pct']:.4f}")
    print()
    print("文本特征均值差（舞弊 - 非舞弊，训练集）：")
    for col, vf, vc, dv in summary_rows:
        print(f"  {col:24s}  Δ={dv:+.4f}")

    print()
    print("[reminder] 文本特征均为合成。真实 10-K 抓取需 EDGAR + gvkey-CIK 链接表。")


if __name__ == "__main__":
    main()
