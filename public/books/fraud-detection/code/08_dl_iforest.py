# =====================================================
# code/08_dl_iforest.py
# 第 8 章：表格深度学习与无监督异常检测
# Method 1: sklearn MLPClassifier（监督）
# Method 2: sklearn IsolationForest（无监督）
# 输入：data/bao2020_full.csv
# =====================================================

import time
import random
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")

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

X_train_raw = train_c[features].values
y_train = train_c["misstate"].astype(int).values
X_test_raw  = test_c[features].values
y_test  = test_c["misstate"].astype(int).values

# z-score：仅在训练集上拟合，再 transform 测试集
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train_raw)
X_test  = scaler.transform(X_test_raw)


# ---------- 评估函数 ----------

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
          f"Recall@1%={recall_1:.4f}  Precision@1%={prec_1:.4f}  "
          f"(top-k={topk}, hits={topk_hits})")
    return dict(auc=auc_val, ndcg=ndcg, recall1=recall_1,
                prec1=prec_1, topk=topk)


# ---------- 1. MLP 监督学习 ----------

print("\n========== MLPClassifier hidden=[64, 32], ReLU ==========")
t0 = time.time()
mlp = MLPClassifier(
    hidden_layer_sizes=(64, 32),
    activation="relu",
    solver="adam",
    batch_size=256,
    max_iter=200,
    early_stopping=True,
    validation_fraction=0.15,
    random_state=2026,
)
mlp.fit(X_train, y_train)
mlp_time = time.time() - t0
print(f"MLP 训练时间: {mlp_time:.2f} 秒")
print(f"MLP 实际迭代次数 n_iter_: {mlp.n_iter_}")
print(f"MLP early-stopping best validation score: {mlp.best_validation_score_:.4f}")

mlp_prob_test = mlp.predict_proba(X_test)[:, 1]


# ---------- 2. Isolation Forest 无监督 ----------

print("\n========== IsolationForest n_estimators=200, contamination=0.0066 ==========")
t0 = time.time()
iforest = IsolationForest(
    n_estimators=200,
    contamination=0.0066,
    random_state=2026,
    n_jobs=4,
)
# 无监督：只喂 X_train，不喂 y_train
iforest.fit(X_train)
iforest_time = time.time() - t0
print(f"IsolationForest 训练时间: {iforest_time:.2f} 秒")

# 异常分数：iforest.decision_function 越小越异常
# 取负号让"越大越异常"，便于对齐 Recall@k 的"高分=可疑"约定
iforest_score_test = -1.0 * iforest.decision_function(X_test)


# ---------- 3. 测试集性能 ----------

print("\n========== 测试集性能 ==========")
m_mlp     = eval_metrics(mlp_prob_test,     y_test, "MLP supervised  ")
m_iforest = eval_metrics(iforest_score_test, y_test, "IsolationForest ")


# ---------- 4. 案例公司打分 ----------

case_filter = (((d.gvkey == 6127)  & (d.fyear == 2000)) |
               ((d.gvkey == 10787) & (d.fyear == 2000)))
case_rows = d[case_filter].dropna(subset=features).copy()

if len(case_rows) > 0:
    case_X_raw = case_rows[features].values
    case_X = scaler.transform(case_X_raw)
    case_mlp = mlp.predict_proba(case_X)[:, 1]
    case_iforest = -1.0 * iforest.decision_function(case_X)
    print("\n========== 案例公司打分（fyear=2000，真实 misstate=1） ==========")
    for i, row in case_rows.reset_index(drop=True).iterrows():
        name = "Enron" if int(row.gvkey) == 6127 else "Tyco International"
        print(f"{name:<20s} gvkey={int(row.gvkey)}  fyear={int(row.fyear)}  "
              f"misstate={int(row.misstate)}  "
              f"MLP p={case_mlp[i]:.4f}  IF score={case_iforest[i]:.4f}")
else:
    print("\n[警告] 案例公司行被 NA 过滤掉了")


# ---------- 5. 汇总 ----------

print("\n========== 汇总 ==========")
print(f"MLP            训练时间: {mlp_time:.2f} 秒,  "
      f"测试 AUC = {m_mlp['auc']:.4f}")
print(f"IsolationForest 训练时间: {iforest_time:.2f} 秒, "
      f"测试 AUC = {m_iforest['auc']:.4f}")
print(f"[zero baseline 测试集舞弊率: {100 * y_test.mean():.4f}%]")

# 与 chap05 RF 对照锚点
print("\n[参考锚点] chap05 RF Python: AUC=0.6974, Enron 0.4734, Tyco 0.3004")
print("[参考锚点] chap04 LASSO Python: AUC≈0.6882, Enron 0.7292, Tyco 0.0925")
