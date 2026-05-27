# =====================================================
# code/06_xgboost.py
# 第 6 章：梯度提升 XGBoost（Python 主线，R xgboost 不可用）
# 输入：data/bao2020_full.csv
# 输出：
#   1) 网格搜索 + 早停 -> 最优超参 + 验证集 AUC
#   2) 用最优超参在 train 上训练；test 集 AUC / NDCG@100 / Recall@1% / Precision@1%
#   3) Enron 2000 (gvkey=6127) 与 Tyco 2000 (gvkey=10787) 概率
#   4) Top-10 feature importance (gain)
#   5) 训练时间
#   6) 保存模型到 code/_models/06_xgboost_best.json
# =====================================================

import time
import json
import random
import itertools
import numpy as np
import pandas as pd
from pathlib import Path

import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

random.seed(2026)
np.random.seed(2026)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "bao2020_full.csv"
MODELS = ROOT / "code" / "_models"
MODELS.mkdir(parents=True, exist_ok=True)

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

train_raw = d[(d.fyear >= 1991) & (d.fyear <= 2002)].copy()
val_raw   = d[(d.fyear >= 2003) & (d.fyear <= 2008)].copy()
test_raw  = d[(d.fyear >= 2009) & (d.fyear <= 2014)].copy()

train_c = train_raw.dropna(subset=features).reset_index(drop=True)
val_c   = val_raw.dropna(subset=features).reset_index(drop=True)
test_c  = test_raw.dropna(subset=features).reset_index(drop=True)

print(f"训练 1991-2002: {len(train_raw)} -> {len(train_c)} "
      f"(drop {len(train_raw) - len(train_c)} NA), fraud {int(train_c.misstate.sum())}")
print(f"验证 2003-2008: {len(val_raw)} -> {len(val_c)} "
      f"(drop {len(val_raw) - len(val_c)} NA), fraud {int(val_c.misstate.sum())}")
print(f"测试 2009-2014: {len(test_raw)} -> {len(test_c)} "
      f"(drop {len(test_raw) - len(test_c)} NA), fraud {int(test_c.misstate.sum())}")

X_train_raw = train_c[features].values.astype(np.float32)
y_train = train_c["misstate"].astype(int).values
X_val_raw   = val_c[features].values.astype(np.float32)
y_val   = val_c["misstate"].astype(int).values
X_test_raw  = test_c[features].values.astype(np.float32)
y_test  = test_c["misstate"].astype(int).values

# 标准化（XGBoost 不严格要求，但保持与其它章节口径一致，并便于案例公司比较）
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train_raw)
X_val   = scaler.transform(X_val_raw)
X_test  = scaler.transform(X_test_raw)

n_pos = int(y_train.sum())
n_neg = int(len(y_train) - n_pos)
spw = n_neg / max(1, n_pos)
print(f"\nscale_pos_weight = {n_neg}/{n_pos} = {spw:.4f}")


# ---------- 1. 网格搜索 + 早停（验证集驱动） ----------

grid = {
    "max_depth":        [3, 5, 7],
    "eta":              [0.05, 0.1],
    "subsample":        [0.7, 1.0],
    "colsample_bytree": [0.7, 1.0],
}
keys = list(grid.keys())
combos = list(itertools.product(*[grid[k] for k in keys]))
print(f"\n网格搜索 {len(combos)} 组超参，每组最多 2000 棵树 + early_stopping_rounds=50")

dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=features)
dval   = xgb.DMatrix(X_val,   label=y_val,   feature_names=features)
dtest  = xgb.DMatrix(X_test,  label=y_test,  feature_names=features)

results = []
t_grid_start = time.time()

for combo in combos:
    params = dict(zip(keys, combo))
    full_params = {
        "objective":        "binary:logistic",
        "tree_method":      "hist",
        "eval_metric":      "auc",
        "scale_pos_weight": spw,
        "max_depth":        params["max_depth"],
        "eta":              params["eta"],
        "subsample":        params["subsample"],
        "colsample_bytree": params["colsample_bytree"],
        "seed":             2026,
        "verbosity":        0,
    }
    booster = xgb.train(
        full_params,
        dtrain,
        num_boost_round=2000,
        evals=[(dval, "val")],
        early_stopping_rounds=50,
        verbose_eval=False,
    )
    val_auc = booster.best_score
    best_round = booster.best_iteration + 1
    results.append({
        **params,
        "val_auc":    val_auc,
        "best_round": best_round,
    })
    print(f"  depth={params['max_depth']}  eta={params['eta']}  "
          f"sub={params['subsample']}  col={params['colsample_bytree']}  "
          f"-> val_AUC={val_auc:.4f}  best_round={best_round}")

t_grid = time.time() - t_grid_start
print(f"\n网格搜索总耗时 {t_grid:.1f} 秒")

results = sorted(results, key=lambda r: -r["val_auc"])
best = results[0]
print(f"\n>>> 最优组合: max_depth={best['max_depth']}  eta={best['eta']}  "
      f"subsample={best['subsample']}  colsample_bytree={best['colsample_bytree']}  "
      f"n_estimators={best['best_round']}  val_AUC={best['val_auc']:.4f}")


# ---------- 2. 用最优超参在 train 上重训（固定 n_estimators 为早停命中值） ----------

best_params = {
    "objective":        "binary:logistic",
    "tree_method":      "hist",
    "eval_metric":      "auc",
    "scale_pos_weight": spw,
    "max_depth":        best["max_depth"],
    "eta":              best["eta"],
    "subsample":        best["subsample"],
    "colsample_bytree": best["colsample_bytree"],
    "seed":             2026,
    "verbosity":        0,
}

t_fit_start = time.time()
final_booster = xgb.train(
    best_params,
    dtrain,
    num_boost_round=best["best_round"],
    evals=[(dval, "val")],
    verbose_eval=False,
)
t_fit = time.time() - t_fit_start
print(f"\n最终模型训练时间 {t_fit:.2f} 秒（固定 n_estimators={best['best_round']}）")


# ---------- 3. 测试集评估 ----------

prob_test = final_booster.predict(dtest)


def eval_metrics(prob, label, name):
    auc_val = roc_auc_score(label, prob)
    k = 100
    order = np.argsort(-prob)
    hits = label[order]
    pos = np.arange(1, k + 1)
    discounts = 1.0 / np.log2(pos + 1)
    dcg = float(np.sum(hits[:k] * discounts))
    ideal_hits = np.sort(label)[::-1][:k]
    idcg = float(np.sum(ideal_hits * discounts))
    ndcg = dcg / idcg if idcg > 0 else float("nan")

    topk = max(1, int(np.ceil(0.01 * len(prob))))
    topk_hits = int(np.sum(label[order][:topk]))
    recall_1 = topk_hits / int(label.sum())
    prec_1   = topk_hits / topk
    print(f"[{name}] AUC={auc_val:.4f}  NDCG@100={ndcg:.4f}  "
          f"Recall@1%={recall_1:.4f}  Precision@1%={prec_1:.4f}  "
          f"(topk={topk}, hits={topk_hits})")
    return dict(auc=auc_val, ndcg=ndcg, recall1=recall_1, prec1=prec_1)


print("\n========== 测试集性能 ==========")
m_xgb = eval_metrics(prob_test, y_test, "XGBoost (best)")


# ---------- 4. 案例公司打分（Enron 2000, Tyco 2000） ----------

case_filter = (((d.gvkey == 6127)  & (d.fyear == 2000)) |
               ((d.gvkey == 10787) & (d.fyear == 2000)))
case_rows = d[case_filter].dropna(subset=features).copy()

print("\n========== 案例公司 XGBoost 舞弊概率（fyear=2000） ==========")
if len(case_rows) > 0:
    case_X_raw = case_rows[features].values.astype(np.float32)
    case_X = scaler.transform(case_X_raw)
    case_d = xgb.DMatrix(case_X, feature_names=features)
    case_prob = final_booster.predict(case_d)
    for i, row in case_rows.reset_index(drop=True).iterrows():
        nm = "Enron" if int(row.gvkey) == 6127 else "Tyco International"
        print(f"{nm:<22s} gvkey={int(row.gvkey)}  fyear={int(row.fyear)}  "
              f"misstate={int(row.misstate)}  XGB p(misstate=1)={case_prob[i]:.4f}")
else:
    print("[警告] 案例公司行被 NA 过滤掉")


# ---------- 5. Feature importance (gain) Top-10 ----------

print("\n========== Top-10 Feature Importance (gain) ==========")
imp_gain = final_booster.get_score(importance_type="gain")
imp_gain_full = {f: imp_gain.get(f, 0.0) for f in features}
imp_series = pd.Series(imp_gain_full).sort_values(ascending=False)
print(imp_series.head(10).round(4).to_string())


# ---------- 6. 保存模型 + 元数据 ----------

model_path = MODELS / "06_xgboost_best.json"
final_booster.save_model(str(model_path))
print(f"\n模型已保存: {model_path}")

meta_path = MODELS / "06_xgboost_meta.json"
meta = {
    "best_params": {
        "max_depth":        best["max_depth"],
        "eta":              best["eta"],
        "subsample":        best["subsample"],
        "colsample_bytree": best["colsample_bytree"],
        "n_estimators":     best["best_round"],
        "scale_pos_weight": spw,
    },
    "val_auc":     best["val_auc"],
    "test_metrics": m_xgb,
    "train_time_s": t_fit,
    "grid_time_s":  t_grid,
    "n_train":      len(train_c),
    "n_val":        len(val_c),
    "n_test":       len(test_c),
    "n_train_pos":  int(y_train.sum()),
    "n_val_pos":    int(y_val.sum()),
    "n_test_pos":   int(y_test.sum()),
    "top10_gain":   {k: float(v) for k, v in imp_series.head(10).items()},
}
with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2, default=float)
print(f"元数据已保存: {meta_path}")


# ---------- 7. 汇总 ----------

print("\n========== 汇总 ==========")
print(f"网格搜索时间    {t_grid:.1f} 秒")
print(f"最终训练时间    {t_fit:.2f} 秒")
print(f"验证集 AUC      {best['val_auc']:.4f}")
print(f"测试集 AUC      {m_xgb['auc']:.4f}")
print(f"测试集 NDCG@100 {m_xgb['ndcg']:.4f}")
print(f"测试集 Recall@1% {m_xgb['recall1']:.4f}")
print(f"测试集 Precision@1% {m_xgb['prec1']:.4f}")
print(f"[zero baseline 测试集舞弊率: {100 * y_test.mean():.4f}%]")
