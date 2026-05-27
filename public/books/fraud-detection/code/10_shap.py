"""
code/10_shap.py
第 10 章：SHAP 可解释性
- 优先加载 chap06 的 XGBoost 模型 (code/_models/06_xgboost_best.json)
- 退而其次加载 chap07 的 RUSBoost (code/_models/07_rusboost_best.pkl)
- 都不可用时：在 10_shap.py 内部用 chap06 的训练协议
  (max_depth=5, eta=0.1, n_estimators=500, scale_pos_weight=auto,
   early_stopping_rounds=50) 重训一个 XGBoost 代理模型用于 SHAP 解释。
- 计算测试集 (2009-2014, drop NA) 的 SHAP 值 (TreeExplainer)
- 报告 Top-10 全局 mean(|SHAP|)
- 报告 Enron 2000 (gvkey=6127) 和 Tyco 2000 (gvkey=10787) 的局部 SHAP
  各取贡献绝对值前 5
- 保存 SHAP 数组到 code/_shap_artifacts/ 供后续画图
"""
import json
import pickle
import random
import functools
import builtins
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
import shap
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

print = functools.partial(builtins.print, flush=True)
random.seed(2026)
np.random.seed(2026)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "bao2020_full.csv"
MODEL_DIR = ROOT / "code" / "_models"
ART_DIR = ROOT / "code" / "_shap_artifacts"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
ART_DIR.mkdir(parents=True, exist_ok=True)

XGB_PATH = MODEL_DIR / "06_xgboost_best.json"
RUS_PATH = MODEL_DIR / "07_rusboost_best.pkl"

# ------------ 1. 数据准备：与前章统一的 NA-drop 协议 ------------

feat_raw = ["act", "ap", "at", "ceq", "che", "cogs", "csho", "dlc",
            "dltis", "dltt", "dp", "ib", "invt", "ivao", "ivst",
            "lct", "lt", "ni", "ppegt", "pstk", "re", "rect",
            "sale", "sstk", "txp", "txt", "xint", "prcc_f"]
feat_ratio = ["dch_wc", "ch_rsst", "dch_rec", "dch_inv", "soft_assets",
              "ch_cs", "ch_cm", "ch_roa", "issue", "bm", "dpi",
              "reoa", "EBIT", "ch_fcf"]
features = feat_raw + feat_ratio
assert len(features) == 42

print("[1] 读取 Bao 数据 ...")
d = pd.read_csv(DATA)
train_raw = d.query("1991 <= fyear <= 2002").copy()
valid_raw = d.query("2003 <= fyear <= 2008").copy()
test_raw  = d.query("2009 <= fyear <= 2014").copy()

def dna(df, name):
    n0 = len(df)
    out = df.dropna(subset=features).copy()
    print(f"    {name}: {n0} -> {len(out)} 行 (drop {n0 - len(out)} NA), "
          f"fraud={int(out['misstate'].sum())}")
    return out

train = dna(train_raw, "训练 1991-2002")
valid = dna(valid_raw, "验证 2003-2008")
test  = dna(test_raw,  "测试 2009-2014")

X_train_raw = train[features].values.astype(np.float32)
y_train = train["misstate"].astype(int).values
X_valid_raw = valid[features].values.astype(np.float32)
y_valid = valid["misstate"].astype(int).values
X_test_raw  = test[features].values.astype(np.float32)
y_test  = test["misstate"].astype(int).values

# 与 chap06 一致：StandardScaler 仅在训练集拟合, 然后 transform
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train_raw).astype(np.float32)
X_valid = scaler.transform(X_valid_raw).astype(np.float32)
X_test  = scaler.transform(X_test_raw).astype(np.float32)

# ------------ 2. 模型加载或重训练 ------------

booster = None
model_provenance = None

if XGB_PATH.exists():
    print(f"[2] 检测到 chap06 模型 {XGB_PATH.name}, 直接加载 ...")
    booster = xgb.Booster()
    booster.load_model(str(XGB_PATH))
    model_provenance = "chap06_xgboost_loaded"
elif RUS_PATH.exists():
    print(f"[2] chap06 不可用, 检测到 chap07 模型 {RUS_PATH.name}, 直接加载 ...")
    with open(RUS_PATH, "rb") as f:
        rus_obj = pickle.load(f)
    # RUSBoost 通常是 sklearn-like, SHAP TreeExplainer 不一定支持，
    # 退化为重训 XGBoost 代理
    print("    RUSBoost 不直接被 SHAP TreeExplainer 支持, 切换到重训 XGBoost 代理 ...")
    booster = None
    model_provenance = "rusboost_present_but_retrained_xgb"

if booster is None:
    print("[2] 未发现可用 booster, 在本脚本内重训 XGBoost 代理 (chap06 协议) ...")
    pos = int(y_train.sum())
    neg = int((1 - y_train).sum())
    spw = neg / max(pos, 1)
    print(f"    scale_pos_weight = neg/pos = {neg}/{pos} = {spw:.4f}")

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=features)
    dvalid = xgb.DMatrix(X_valid, label=y_valid, feature_names=features)
    dtest  = xgb.DMatrix(X_test,  label=y_test,  feature_names=features)

    params = dict(
        objective="binary:logistic",
        eval_metric="auc",
        max_depth=5,
        eta=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        tree_method="hist",
        seed=2026,
    )
    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=500,
        evals=[(dtrain, "train"), (dvalid, "valid")],
        early_stopping_rounds=50,
        verbose_eval=50,
    )
    booster.save_model(str(XGB_PATH))
    if model_provenance is None:
        model_provenance = "retrained_xgb_in_10_shap"
    print(f"    最佳轮次 = {booster.best_iteration}, "
          f"valid-AUC = {booster.best_score:.4f}")
    print(f"    模型已保存到 {XGB_PATH}")

# ------------ 3. 测试集性能复核 ------------

print("[3] 测试集性能复核 ...")
dtest = xgb.DMatrix(X_test, label=y_test, feature_names=features)
best_iter = getattr(booster, "best_iteration", None)
if best_iter is not None and best_iter > 0:
    test_pred = booster.predict(dtest, iteration_range=(0, best_iter + 1))
else:
    test_pred = booster.predict(dtest)
auc_test = roc_auc_score(y_test, test_pred)

def topk_metrics(y, p, k_frac=0.01, ndcg_k=100):
    n = len(y)
    k = max(1, int(np.ceil(k_frac * n)))
    order = np.argsort(-p)
    hits = y[order]
    pos_arr = np.arange(1, ndcg_k + 1)
    disc = 1.0 / np.log2(pos_arr + 1)
    dcg = np.sum(hits[:ndcg_k] * disc)
    ideal = np.sort(y)[::-1][:ndcg_k]
    idcg = np.sum(ideal * disc)
    ndcg = dcg / idcg if idcg > 0 else float("nan")
    topk_hits = int(np.sum(hits[:k]))
    rec = topk_hits / int(y.sum())
    prec = topk_hits / k
    return auc_test, ndcg, rec, prec, k

auc_v, ndcg_v, rec_v, prec_v, k_v = topk_metrics(y_test, test_pred)
print(f"    AUC = {auc_v:.4f}  NDCG@100 = {ndcg_v:.4f}  "
      f"Recall@1% = {rec_v:.4f}  Precision@1% = {prec_v:.4f}  (k={k_v})")

# ------------ 4. SHAP 值计算 ------------

print("[4] 计算 SHAP 值 (TreeExplainer) ...")
explainer = shap.TreeExplainer(booster)
# 直接对完整测试集算 SHAP, n=27628 量级可行
shap_values = explainer.shap_values(X_test)   # shape: (n, 42)
expected_value = explainer.expected_value
print(f"    shap_values shape = {shap_values.shape}")
print(f"    expected_value (logit baseline) = "
      f"{float(np.atleast_1d(expected_value)[0]):.4f}")

# ------------ 5. 全局 mean(|SHAP|) Top-10 ------------

print("[5] 全局 mean(|SHAP|) Top-10:")
mean_abs = np.mean(np.abs(shap_values), axis=0)
glo = (pd.DataFrame({"feature": features, "mean_abs_shap": mean_abs})
       .sort_values("mean_abs_shap", ascending=False)
       .reset_index(drop=True))
print(glo.head(10).to_string(index=False, float_format=lambda v: f"{v:.4f}"))

# ------------ 6. 局部 SHAP: Enron 2000 与 Tyco 2000 ------------

print("[6] 局部 SHAP (Enron 2000 / Tyco 2000):")
# 找 case 行
case_keys = [("Enron", 6127), ("Tyco", 10787)]
local_records = {}
for name, gvkey in case_keys:
    mask = (test["gvkey"].values == gvkey) & (test["fyear"].values == 2000)
    idx = np.where(mask)[0]
    if len(idx) == 0:
        # 案例属于 1998-2000, 落在训练期, 单独抓出原始行 -> scaler.transform -> 算 SHAP
        d_full = pd.read_csv(DATA)
        case_full = d_full[(d_full["gvkey"] == gvkey) &
                           (d_full["fyear"] == 2000)].dropna(subset=features)
        if len(case_full) == 0:
            print(f"    [警告] {name} gvkey={gvkey} fyear=2000 不在 NA-drop 后样本中")
            local_records[name] = None
            continue
        Xraw = case_full[features].values.astype(np.float32).reshape(1, -1)
        Xrow = scaler.transform(Xraw).astype(np.float32)
        sv_row = explainer.shap_values(Xrow)[0]
        pred_logit = float(booster.predict(
            xgb.DMatrix(Xrow, feature_names=features),
            output_margin=True,
        )[0])
        pred_prob = 1.0 / (1.0 + np.exp(-pred_logit))
        misstate = int(case_full.iloc[0]["misstate"])
    else:
        sv_row = shap_values[idx[0]]
        pred_logit = float(booster.predict(
            xgb.DMatrix(X_test[idx[0]:idx[0] + 1], feature_names=features),
            output_margin=True,
        )[0])
        pred_prob = 1.0 / (1.0 + np.exp(-pred_logit))
        misstate = int(y_test[idx[0]])
    contrib = (pd.DataFrame({"feature": features, "shap": sv_row})
               .assign(abs_shap=lambda x: x["shap"].abs())
               .sort_values("abs_shap", ascending=False)
               .reset_index(drop=True))
    print(f"    --- {name} (gvkey={gvkey}, fyear=2000, misstate={misstate}) ---")
    print(f"    pred_logit={pred_logit:.4f}, pred_prob={pred_prob:.4f}")
    print(contrib.head(5)[["feature", "shap"]]
          .to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
    local_records[name] = dict(
        gvkey=gvkey,
        pred_logit=pred_logit,
        pred_prob=pred_prob,
        misstate=misstate,
        top5=contrib.head(5)[["feature", "shap"]].to_dict("records"),
    )

# ------------ 7. 保存 artifacts ------------

print("[7] 保存 SHAP artifacts ...")
np.savez_compressed(
    ART_DIR / "shap_test.npz",
    shap_values=shap_values,
    X_test=X_test,
    y_test=y_test,
    feature_names=np.array(features),
    expected_value=np.array([float(np.atleast_1d(expected_value)[0])]),
)
glo.to_csv(ART_DIR / "shap_global_top.csv", index=False)
with open(ART_DIR / "shap_local_cases.json", "w") as f:
    json.dump(
        {"provenance": model_provenance,
         "test_metrics": dict(auc=auc_v, ndcg=ndcg_v,
                              recall_1pct=rec_v, precision_1pct=prec_v, k=k_v),
         "local": local_records},
        f, indent=2, default=float,
    )
print(f"    -> {ART_DIR}/shap_test.npz")
print(f"    -> {ART_DIR}/shap_global_top.csv")
print(f"    -> {ART_DIR}/shap_local_cases.json")
print(f"[done] model_provenance = {model_provenance}")
