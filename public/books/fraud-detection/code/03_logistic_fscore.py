# =====================================================
# code/03_logistic_fscore.py
# 第 3 章：逻辑回归 + Dechow F-Score (Python 版)
# Model A：42 特征全集（28 原始 + 14 衍生比率）
# Model B：Dechow et al. 2011 Table 7 Model 1 的 7 变量
# =====================================================

import os, random
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

random.seed(2026)
np.random.seed(2026)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
csv_path = os.path.join(ROOT, "data", "bao2020_full.csv")

d = pd.read_csv(csv_path)
print(f"原始数据: {len(d)} firm-years")

raw_vars = ["act","ap","at","ceq","che","cogs","csho","dlc","dltis","dltt",
            "dp","ib","invt","ivao","ivst","lct","lt","ni","ppegt","pstk",
            "re","rect","sale","sstk","txp","txt","xint","prcc_f"]
ratio_vars = ["dch_wc","ch_rsst","dch_rec","dch_inv","soft_assets",
              "ch_cs","ch_cm","ch_roa","issue","bm","dpi","reoa","EBIT","ch_fcf"]
all_vars = raw_vars + ratio_vars
dechow_vars = ["ch_rsst","dch_rec","dch_inv","soft_assets",
               "ch_cs","ch_roa","issue"]

d_full = d.dropna(subset=all_vars).copy()
d_dech = d.dropna(subset=dechow_vars).copy()

print(f"Model A 可用 (42 特征无 NA): {len(d_full)} 行 (丢 {len(d) - len(d_full)})")
print(f"Model B 可用 (7 特征无 NA):  {len(d_dech)} 行 (丢 {len(d) - len(d_dech)})")


def split_set(df):
    return {
        "train": df[(df["fyear"] >= 1991) & (df["fyear"] <= 2002)],
        "valid": df[(df["fyear"] >= 2003) & (df["fyear"] <= 2008)],
        "test":  df[(df["fyear"] >= 2009) & (df["fyear"] <= 2014)],
    }


sA = split_set(d_full)
sB = split_set(d_dech)

for tag, s in (("A", sA), ("B", sB)):
    print(f"Model {tag} 切分: "
          f"train={len(s['train'])} (fraud={int(s['train']['misstate'].sum())}), "
          f"valid={len(s['valid'])} (fraud={int(s['valid']['misstate'].sum())}), "
          f"test={len(s['test'])} (fraud={int(s['test']['misstate'].sum())})")


def eval_metrics(scores, labels, k=100, p=0.01):
    scores = np.asarray(scores); labels = np.asarray(labels)
    n = len(labels); n_pos = int(labels.sum())
    auc = roc_auc_score(labels, scores)
    order = np.argsort(-scores)
    y_ord = labels[order]
    rel = y_ord[:min(k, n)]
    dcg = float(np.sum(rel / np.log2(np.arange(1, len(rel) + 1) + 1)))
    ideal = np.concatenate([np.ones(min(k, n_pos)),
                            np.zeros(max(k - n_pos, 0))])
    idcg = float(np.sum(ideal / np.log2(np.arange(1, len(ideal) + 1) + 1)))
    ndcg = dcg / idcg if idcg > 0 else 0.0
    k_p = int(np.ceil(n * p))
    hit = int(y_ord[:k_p].sum())
    recall_p = hit / n_pos
    prec_p = hit / k_p
    return dict(AUC=auc, NDCG=ndcg, RecallP=recall_p, PrecP=prec_p,
                k_p=k_p, hit=hit, n=n, n_pos=n_pos)


def fit_logit(train, vars_, C=1e8, class_weight=None):
    # C 极大 ≈ 无正则，逼近 R glm 的最大似然解
    # newton-cg 在 42 特征量纲差异大时比 lbfgs 更稳
    X = train[vars_].values
    y = train["misstate"].values.astype(int)
    clf = LogisticRegression(
        penalty="l2", C=C, solver="newton-cg",
        max_iter=2000, class_weight=class_weight,
        random_state=2026, tol=1e-7,
    )
    clf.fit(X, y)
    return clf


# ---------- Model A ----------
print("\n========== Model A: 42 特征全集 ==========")
mA = fit_logit(sA["train"], all_vars)
predA_test = mA.predict_proba(sA["test"][all_vars].values)[:, 1]
metA = eval_metrics(predA_test, sA["test"]["misstate"].values)
print(f"Model A 测试集: AUC={metA['AUC']:.4f}  NDCG@100={metA['NDCG']:.4f}  "
      f"Recall@1%={metA['RecallP']:.4f}  Precision@1%={metA['PrecP']:.4f}")
print(f"  测试 n={metA['n']}, 阳性={metA['n_pos']}, "
      f"1% 名额={metA['k_p']}, 命中={metA['hit']}")

# ---------- Model B ----------
print("\n========== Model B: Dechow F-Score 7 变量 ==========")
mB = fit_logit(sB["train"], dechow_vars)
print("--- Dechow 7 变量系数 ---")
print(f"  (Intercept) {mB.intercept_[0]: .6f}")
for name, b in zip(dechow_vars, mB.coef_[0]):
    print(f"  {name:<12s} {b: .6f}")

predB_test = mB.predict_proba(sB["test"][dechow_vars].values)[:, 1]
metB = eval_metrics(predB_test, sB["test"]["misstate"].values)
print(f"\nModel B 测试集: AUC={metB['AUC']:.4f}  NDCG@100={metB['NDCG']:.4f}  "
      f"Recall@1%={metB['RecallP']:.4f}  Precision@1%={metB['PrecP']:.4f}")
print(f"  测试 n={metB['n']}, 阳性={metB['n_pos']}, "
      f"1% 名额={metB['k_p']}, 命中={metB['hit']}")

uncond = float(sB["train"]["misstate"].mean())
print(f"\nModel B 训练集无条件舞弊率: {uncond:.6f}")

# ---------- 案例公司 ----------
def case_pred(model, df, vars_, gvkey_v, fyear_v):
    row = df[(df["gvkey"] == gvkey_v) & (df["fyear"] == fyear_v)]
    if len(row) == 0:
        return None
    return float(model.predict_proba(row[vars_].values)[0, 1])

print("\n========== 案例公司 fyear=2000 打分 ==========")
enron_A = case_pred(mA, d_full, all_vars,  6127, 2000)
tyco_A  = case_pred(mA, d_full, all_vars, 10787, 2000)
enron_B = case_pred(mB, d_dech, dechow_vars,  6127, 2000)
tyco_B  = case_pred(mB, d_dech, dechow_vars, 10787, 2000)
print(f"Enron 2000 (gvkey=6127):  Model A p={enron_A:.4f}, "
      f"Model B p={enron_B:.4f}, F-Score={enron_B/uncond:.2f}")
print(f"Tyco  2000 (gvkey=10787): Model A p={tyco_A:.4f}, "
      f"Model B p={tyco_B:.4f}, F-Score={tyco_B/uncond:.2f}")

# ---------- 备选：class_weight='balanced' 提示 ----------
print("\n[备选] class_weight='balanced' 在不平衡数据上是常用的部分修正：")
mB_bal = fit_logit(sB["train"], dechow_vars, class_weight="balanced")
predB_bal = mB_bal.predict_proba(sB["test"][dechow_vars].values)[:, 1]
metB_bal = eval_metrics(predB_bal, sB["test"]["misstate"].values)
print(f"  Model B + balanced: AUC={metB_bal['AUC']:.4f}  "
      f"NDCG@100={metB_bal['NDCG']:.4f}  Recall@1%={metB_bal['RecallP']:.4f}")

print("\n[A] AUC=%.4f NDCG=%.4f R@1%%=%.4f P@1%%=%.4f"
      % (metA['AUC'], metA['NDCG'], metA['RecallP'], metA['PrecP']))
print("[B] AUC=%.4f NDCG=%.4f R@1%%=%.4f P@1%%=%.4f"
      % (metB['AUC'], metB['NDCG'], metB['RecallP'], metB['PrecP']))
print("Done.")
