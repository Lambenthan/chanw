# =====================================================
# code/07_rusboost.py
# 第 7 章：RUSBoost 复刻 Bao et al. (2020 JAR)
# 输入：data/bao2020_full.csv
# 主线：imblearn.ensemble.RUSBoostClassifier 在 28 个原始
#       Compustat 变量上，按 Bao 调参协议挑 n_estimators
#       并与 SMOTE+LogReg / class_weight 平衡 LogReg /
#       普通 LogReg 在同一测试集上做并列对比。
# 评估：AUC / NDCG@100 / Recall@1% / Precision@1%
# 案例：Enron 2000 + Tyco 2000 RUSBoost 概率
# 模型：保存最优 RUSBoost 到 code/_models/07_rusboost_best.pkl
# =====================================================

import time
import random
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from imblearn.ensemble import RUSBoostClassifier
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

random.seed(2026)
np.random.seed(2026)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "bao2020_full.csv"
MODEL_DIR = ROOT / "code" / "_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Bao 主结果使用 28 个原始 Compustat 变量（不含 14 个衍生比率）
features_raw = ["act", "ap", "at", "ceq", "che", "cogs", "csho", "dlc",
                "dltis", "dltt", "dp", "ib", "invt", "ivao", "ivst",
                "lct", "lt", "ni", "ppegt", "pstk", "re", "rect",
                "sale", "sstk", "txp", "txt", "xint", "prcc_f"]
assert len(features_raw) == 28
features = features_raw

d = pd.read_csv(DATA)
print(f"全样本: {d.shape}")

# ---------- 1. 时间切分 + drop NA ----------
sub_train  = d[(d.fyear >= 1991) & (d.fyear <= 1999)].copy()
sub_valid  = d[(d.fyear == 2001)].copy()
full_train = d[(d.fyear >= 1991) & (d.fyear <= 2002)].copy()
test       = d[(d.fyear >= 2009) & (d.fyear <= 2014)].copy()

def clean(df, label):
    n_before = len(df)
    fr_before = int(df.misstate.sum())
    df_c = df.dropna(subset=features).reset_index(drop=True)
    n_after = len(df_c)
    fr_after = int(df_c.misstate.sum())
    print(f"  {label}: {n_before} -> {n_after}  fraud {fr_before} -> {fr_after}")
    return df_c

print("\n--- 时间切分 + drop NA（28 个原始变量） ---")
sub_train_c  = clean(sub_train,  "sub-train 1991-1999")
sub_valid_c  = clean(sub_valid,  "sub-valid 2001    ")
full_train_c = clean(full_train, "full-train 1991-2002")
test_c       = clean(test,       "test  2009-2014   ")

X_subtr  = sub_train_c[features].values
y_subtr  = sub_train_c["misstate"].astype(int).values
X_subval = sub_valid_c[features].values
y_subval = sub_valid_c["misstate"].astype(int).values
X_train  = full_train_c[features].values
y_train  = full_train_c["misstate"].astype(int).values
X_test   = test_c[features].values
y_test   = test_c["misstate"].astype(int).values

n_test = len(y_test)
k_test = max(1, int(np.ceil(0.01 * n_test)))
print(f"\n测试集 1% 名额 k = {k_test}")

# ---------- 2. 评估函数 ----------
def eval_metrics(prob, label, name):
    auc_val = roc_auc_score(label, prob)
    k = 100
    order = np.argsort(-prob, kind="mergesort")
    hits = label[order]
    pos = np.arange(1, k + 1)
    discounts = 1.0 / np.log2(pos + 1)
    dcg = float(np.sum(hits[:k] * discounts))
    ideal = np.sort(label)[::-1][:k]
    idcg = float(np.sum(ideal * discounts))
    ndcg = dcg / idcg if idcg > 0 else float("nan")

    topk = max(1, int(np.ceil(0.01 * len(prob))))
    topk_hits = int(np.sum(label[order][:topk]))
    recall_1 = topk_hits / int(label.sum())
    prec_1   = topk_hits / topk
    print(f"[{name:<28s}] AUC={auc_val:.4f}  NDCG@100={ndcg:.4f}  "
          f"Recall@1%={recall_1:.4f}  Precision@1%={prec_1:.4f}")
    return dict(auc=auc_val, ndcg=ndcg, recall1=recall_1, prec1=prec_1)


# ---------- 3. Bao 调参协议：单年验证 ----------
print("\n========== Bao 调参协议：1991-1999 拟合，2001 验证 ==========")
n_grid = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1500, 2000, 2500, 3000]
print(f"n_estimators 候选: {n_grid}")

# Bao 2020 协议：MATLAB fitensemble RUSBoost 默认使用 unconstrained 单棵树
# + min_samples_leaf=5（MATLAB MinLeafSize），learning rate 0.1
# 在 imblearn 里指定等价 base learner
def make_base():
    return DecisionTreeClassifier(min_samples_leaf=5, random_state=2026)

tune_log = []
t0 = time.time()
for n_est in n_grid:
    rb = RUSBoostClassifier(
        estimator=make_base(),
        n_estimators=n_est,
        learning_rate=0.1,
        sampling_strategy="auto",
        replacement=False,
        random_state=2026,
    )
    t_fit = time.time()
    rb.fit(X_subtr, y_subtr)
    t_fit = time.time() - t_fit
    val_prob = rb.predict_proba(X_subval)[:, 1]
    val_auc = roc_auc_score(y_subval, val_prob)
    n_used = len(rb.estimators_)
    tune_log.append((n_est, n_used, val_auc, t_fit))
    print(f"  n_est={n_est:<4d}  used={n_used:<4d}  val AUC={val_auc:.4f}  fit={t_fit:.1f}s")

tune_total = time.time() - t0
tune_df = pd.DataFrame(tune_log,
                       columns=["n_estimators", "n_used", "val_auc", "fit_seconds"])
# Bao 协议：取验证 AUC 最高，平局取最小 n_estimators
max_auc = tune_df["val_auc"].max()
best_idx = int(tune_df[tune_df["val_auc"] == max_auc]
               .sort_values("n_estimators").index[0])
best_n = int(tune_df.loc[best_idx, "n_estimators"])
best_val_auc = float(tune_df.loc[best_idx, "val_auc"])
print(f"\n调参总耗时: {tune_total:.1f}s")
print(f"最优 n_estimators = {best_n}  (sub-validate AUC = {best_val_auc:.4f})")

# ---------- 4. 用最优 n_estimators 在完整 1991-2002 上重训 ----------
print(f"\n========== 用最优 n_estimators={best_n} 在 1991-2002 上重训 ==========")
t0 = time.time()
rusboost = RUSBoostClassifier(
    estimator=make_base(),
    n_estimators=best_n,
    learning_rate=0.1,
    sampling_strategy="auto",
    replacement=False,
    random_state=2026,
)
rusboost.fit(X_train, y_train)
rusboost_time = time.time() - t0
print(f"实际进入集成的 base learner 数: {len(rusboost.estimators_)}")
print(f"RUSBoost 重训时间: {rusboost_time:.1f}s")

with open(MODEL_DIR / "07_rusboost_best.pkl", "wb") as f:
    pickle.dump({"model": rusboost, "n_estimators": best_n,
                 "features": features}, f)
print(f"模型已保存到 code/_models/07_rusboost_best.pkl")

rb_prob_test = rusboost.predict_proba(X_test)[:, 1]


# ---------- 5. 三种对照方法（同一切分） ----------
print("\n========== 对照方法 1: SMOTE + LogReg ==========")
t0 = time.time()
smote_pipe = ImbPipeline([
    ("scaler", StandardScaler()),
    ("smote",  SMOTE(random_state=2026)),
    ("logit",  LogisticRegression(max_iter=5000, solver="liblinear",
                                   random_state=2026)),
])
smote_pipe.fit(X_train, y_train)
smote_time = time.time() - t0
sm_prob_test = smote_pipe.predict_proba(X_test)[:, 1]
print(f"SMOTE+LogReg 训练时间: {smote_time:.2f}s")

print("\n========== 对照方法 2: balanced LogReg (class_weight='balanced') ==========")
t0 = time.time()
bal_pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("logit",  LogisticRegression(class_weight="balanced", max_iter=5000,
                                   solver="liblinear", random_state=2026)),
])
bal_pipe.fit(X_train, y_train)
bal_time = time.time() - t0
bl_prob_test = bal_pipe.predict_proba(X_test)[:, 1]
print(f"balanced LogReg 训练时间: {bal_time:.2f}s")

print("\n========== 对照方法 3: 普通 LogReg (无加权) ==========")
t0 = time.time()
plain_pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("logit",  LogisticRegression(max_iter=5000, solver="liblinear",
                                   random_state=2026)),
])
plain_pipe.fit(X_train, y_train)
plain_time = time.time() - t0
pl_prob_test = plain_pipe.predict_proba(X_test)[:, 1]
print(f"plain LogReg 训练时间: {plain_time:.2f}s")


# ---------- 6. 测试集性能并列 ----------
print("\n========== 测试集性能（2009-2014, 28 raw vars） ==========")
m_rb    = eval_metrics(rb_prob_test, y_test, "RUSBoost (Bao 复刻)")
m_smote = eval_metrics(sm_prob_test, y_test, "SMOTE + LogReg")
m_bal   = eval_metrics(bl_prob_test, y_test, "balanced LogReg")
m_plain = eval_metrics(pl_prob_test, y_test, "plain LogReg")


# ---------- 7. 案例公司 RUSBoost 打分 ----------
print("\n========== 案例公司 RUSBoost 概率 ==========")
case_filter = (((d.gvkey == 6127)  & (d.fyear == 2000)) |
               ((d.gvkey == 10787) & (d.fyear == 2000)))
case_rows = d[case_filter].dropna(subset=features).copy()
if len(case_rows) > 0:
    case_X = case_rows[features].values
    case_prob_rb = rusboost.predict_proba(case_X)[:, 1]
    for i, row in case_rows.reset_index(drop=True).iterrows():
        name = "Enron" if int(row.gvkey) == 6127 else "Tyco International"
        print(f"  {name:<22s} gvkey={int(row.gvkey)}  fyear={int(row.fyear)}  "
              f"misstate={int(row.misstate)}  RUSBoost p={case_prob_rb[i]:.4f}")
else:
    print("  [警告] 案例公司行被 NA 过滤掉了")


# ---------- 8. 汇总 ----------
print("\n========== 训练时间汇总 ==========")
print(f"  RUSBoost 调参 ({len(n_grid)} 组)：    {tune_total:.1f}s")
print(f"  RUSBoost 在 1991-2002 重训：        {rusboost_time:.1f}s")
print(f"  SMOTE + LogReg：                  {smote_time:.2f}s")
print(f"  balanced LogReg：                 {bal_time:.2f}s")
print(f"  plain LogReg：                    {plain_time:.2f}s")

print("\n========== 测试集舞弊率 ==========")
print(f"  test fraud rate = {100 * y_test.mean():.4f}%  ({int(y_test.sum())}/{n_test})")

print("\n========== 完整调参表 ==========")
print(tune_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
