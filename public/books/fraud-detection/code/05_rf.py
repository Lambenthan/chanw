# =====================================================
# code/05_rf.py
# 第 5 章：决策树与随机森林（Python 等价实现）
# 输入：data/bao2020_full.csv
# 输出：sklearn DecisionTreeClassifier (depth=5) +
#       RandomForestClassifier (500 trees, max_features=6)
# =====================================================

import time
import random
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

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
features = features_raw + features_ratio
assert len(features) == 42

d = pd.read_csv(DATA)

train = d[(d.fyear >= 1991) & (d.fyear <= 2002)].copy()
test  = d[(d.fyear >= 2009) & (d.fyear <= 2014)].copy()

n_train_before = len(train)
n_test_before  = len(test)

train_c = train.dropna(subset=features).reset_index(drop=True)
test_c  = test.dropna(subset=features).reset_index(drop=True)

print(f"训练集: {n_train_before} -> {len(train_c)} "
      f"(drop {n_train_before - len(train_c)} NA-rows), "
      f"fraud {int(train_c.misstate.sum())}")
print(f"测试集: {n_test_before} -> {len(test_c)} "
      f"(drop {n_test_before - len(test_c)} NA-rows), "
      f"fraud {int(test_c.misstate.sum())}")

X_train = train_c[features].values
y_train = train_c["misstate"].astype(int).values
X_test  = test_c[features].values
y_test  = test_c["misstate"].astype(int).values


# ---------- 1. 单棵决策树 (max_depth=5) ----------

print("\n========== 单棵决策树 sklearn, max_depth=5 ==========")
t0 = time.time()
tree = DecisionTreeClassifier(
    max_depth=5,
    min_samples_split=30,
    random_state=2026,
)
tree.fit(X_train, y_train)
tree_time = time.time() - t0
print(f"单棵树训练时间: {tree_time:.3f} 秒")

print("\n--- 树结构（截断到 depth=5） ---")
print(export_text(tree, feature_names=features, max_depth=5))

tree_prob_test = tree.predict_proba(X_test)[:, 1]


# ---------- 2. 随机森林（500 trees, max_features=6） ----------

print("\n========== 随机森林 sklearn, n_estimators=500, max_features=6 ==========")
t0 = time.time()
rf = RandomForestClassifier(
    n_estimators=500,
    max_features=6,           # mtry = sqrt(42) ≈ 6
    min_samples_leaf=5,        # 类比 ranger min.node.size=5
    n_jobs=4,
    oob_score=True,
    random_state=2026,
)
rf.fit(X_train, y_train)
rf_time = time.time() - t0
print(f"随机森林训练时间: {rf_time:.2f} 秒")
print(f"OOB score (accuracy): {rf.oob_score_:.6f}")
print(f"OOB error rate:        {1 - rf.oob_score_:.6f}")

rf_prob_test = rf.predict_proba(X_test)[:, 1]


# ---------- 3. 评估 ----------

def eval_metrics(prob, label, name):
    auc_val = roc_auc_score(label, prob)
    k = 100
    order = np.argsort(-prob)
    hits = label[order]
    pos = np.arange(1, k + 1)
    discounts = 1.0 / np.log2(pos + 1)
    dcg = np.sum(hits[:k] * discounts)
    ideal_hits = np.sort(label)[::-1][:k]
    idcg = np.sum(ideal_hits * discounts)
    ndcg = dcg / idcg if idcg > 0 else float("nan")

    topk = max(1, int(np.ceil(0.01 * len(prob))))
    topk_hits = int(np.sum(label[order][:topk]))
    recall_1 = topk_hits / int(label.sum())
    prec_1   = topk_hits / topk
    print(f"[{name}] AUC={auc_val:.4f}  NDCG@100={ndcg:.4f}  "
          f"Recall@1%={recall_1:.4f}  Precision@1%={prec_1:.4f}")
    return dict(auc=auc_val, ndcg=ndcg, recall1=recall_1,
                prec1=prec_1, topk=topk)


print("\n========== 测试集性能 ==========")
m_tree = eval_metrics(tree_prob_test, y_test, "单棵树 max_depth=5")
m_rf   = eval_metrics(rf_prob_test,   y_test, "随机森林 sklearn")


# ---------- 4. 变量重要性 ----------

print("\n========== RF 变量重要性 Top-10 (MDI = impurity) ==========")
mdi = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
print(mdi.head(10).round(4).to_string())

print("\n========== RF 变量重要性 Top-10 (MDA = permutation) ==========")
print("（permutation_importance 需要在 hold-out 上跑，使用测试集）")
t0 = time.time()
perm = permutation_importance(rf, X_test, y_test, n_repeats=5,
                              random_state=2026, n_jobs=4,
                              scoring="roc_auc")
perm_time = time.time() - t0
mda = pd.Series(perm.importances_mean, index=features).sort_values(ascending=False)
print(mda.head(10).round(6).to_string())
print(f"permutation_importance 用时: {perm_time:.2f} 秒")


# ---------- 5. 案例公司打分 ----------

case_filter = (((d.gvkey == 6127)  & (d.fyear == 2000)) |
               ((d.gvkey == 10787) & (d.fyear == 2000)))
case_rows = d[case_filter].dropna(subset=features).copy()

if len(case_rows) > 0:
    case_X = case_rows[features].values
    case_prob = rf.predict_proba(case_X)[:, 1]
    print("\n========== 案例公司 RF 舞弊概率（fyear=2000） ==========")
    for i, row in case_rows.reset_index(drop=True).iterrows():
        name = "Enron" if int(row.gvkey) == 6127 else "Tyco International"
        print(f"{name:<22s} gvkey={int(row.gvkey)}  fyear={int(row.fyear)}  "
              f"misstate={int(row.misstate)}  RF p(misstate=1)={case_prob[i]:.4f}")
else:
    print("\n[警告] 案例公司行被 NA 过滤掉了")


# ---------- 6. 汇总 ----------

print("\n========== 汇总 ==========")
print(f"单棵树训练时间: {tree_time:.3f} 秒")
print(f"随机森林训练时间: {rf_time:.2f} 秒")
print(f"OOB accuracy: {100 * rf.oob_score_:.4f}%")
print(f"OOB error:    {100 * (1 - rf.oob_score_):.4f}%")
print(f"[zero baseline 测试集舞弊率: {100 * y_test.mean():.4f}%]")
