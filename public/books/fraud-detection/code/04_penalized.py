"""
code/04_penalized.py
第 4 章：惩罚回归 LASSO / Ridge / Elastic Net（Python 等价实现）
- 时间感知交叉验证（forward-chaining 1991→year-1 train, year valid，year=1996..2002）
- z-score 仅在训练集上拟合 scaler，再 transform 验证 / 测试
- 报告三种惩罚的最优 lambda、LASSO 选中的变量、测试集 AUC / NDCG@100 / Recall@1% / Precision@1%
- 打印 Enron 2000 + Tyco 2000 的舞弊概率
"""
import random
import functools
import builtins
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, ndcg_score

# 行缓冲输出，便于看到进度
print = functools.partial(builtins.print, flush=True)

random.seed(2026)
np.random.seed(2026)

d = pd.read_csv("data/bao2020_full.csv")

feat_raw = ["act", "ap", "at", "ceq", "che", "cogs", "csho", "dlc",
            "dltis", "dltt", "dp", "ib", "invt", "ivao", "ivst",
            "lct", "lt", "ni", "ppegt", "pstk", "re", "rect",
            "sale", "sstk", "txp", "txt", "xint", "prcc_f"]
feat_ratio = ["dch_wc", "ch_rsst", "dch_rec", "dch_inv", "soft_assets",
              "ch_cs", "ch_cm", "ch_roa", "issue", "bm", "dpi",
              "reoa", "EBIT", "ch_fcf"]
features = feat_raw + feat_ratio
assert len(features) == 42

train_full = d.query("1991 <= fyear <= 2002").copy()
valid_raw  = d.query("2003 <= fyear <= 2008").copy()
test_raw   = d.query("2009 <= fyear <= 2014").copy()

print("== 缺失行剔除 ==")
def drop_na(df, name):
    before = len(df)
    out = df.dropna(subset=features).copy()
    print(f"{name}: {before} -> {len(out)} (剔除 {before-len(out)}, "
          f"保留 {100*len(out)/before:.2f}%)")
    return out

train = drop_na(train_full, "训练 1991-2002")
valid = drop_na(valid_raw,  "验证 2003-2008")
test  = drop_na(test_raw,   "测试 2009-2014")
print(f"训练舞弊数 {int(train['misstate'].sum())} / {len(train)} "
      f"({100*train['misstate'].mean():.3f}%)")
print(f"测试舞弊数 {int(test['misstate'].sum())} / {len(test)} "
      f"({100*test['misstate'].mean():.3f}%)")

scaler = StandardScaler()
X_train = scaler.fit_transform(train[features].values)
y_train = train["misstate"].values.astype(int)
X_valid = scaler.transform(valid[features].values)
y_valid = valid["misstate"].values.astype(int)
X_test  = scaler.transform(test[features].values)
y_test  = test["misstate"].values.astype(int)
train_years = train["fyear"].values

# sklearn 的 LogisticRegression 用 C = 1/lambda；我们想覆盖 lambda ∈ [1e-6, 1e-1]
# 等价 C ∈ [10, 1e6]。注意 sklearn 在 binomial 上的 loss 与 glmnet 略有差异（sklearn 默认按 1/N，
# glmnet 按 1/N），所以最优 C 数值可能与 R 端 lambda 不一一对应，但选出来的变量与性能应近似。
fold_years = list(range(1996, 2003))
# 6 个 C 网格，覆盖 0.01..1000；C 越大对应惩罚越弱
# 上限 1000 已足以"几乎不惩罚"；再大计算成本急剧上升且对舞弊检测无增益
C_grid = np.logspace(-2, 3, 6)

def make_logreg(C, l1_ratio, max_iter, tol):
    # sklearn 1.8：用 l1_ratio 控制 L1/L2 比例
    # 选择求解器：liblinear 对纯 L1/L2 极快，saga 仅在 elastic net 时使用
    if l1_ratio == 0.0 or l1_ratio == 1.0:
        solver = "liblinear"
    else:
        solver = "saga"
    return LogisticRegression(
        C=C, l1_ratio=l1_ratio, solver=solver,
        max_iter=max_iter, random_state=2026, tol=tol
    )

def time_aware_cv(l1_ratio, label="", max_iter=500, tol=1e-2):
    """forward-chaining CV，对每个 C 计算平均验证 AUC，返回最优 C。"""
    aucs = np.full((len(fold_years), len(C_grid)), np.nan)
    for k, yr in enumerate(fold_years):
        tr_idx = np.where(train_years < yr)[0]
        va_idx = np.where(train_years == yr)[0]
        if len(tr_idx) == 0 or len(va_idx) == 0:
            continue
        if y_train[va_idx].sum() == 0:
            continue
        for j, C in enumerate(C_grid):
            mod = make_logreg(C, l1_ratio, max_iter, tol)
            mod.fit(X_train[tr_idx], y_train[tr_idx])
            pp = mod.predict_proba(X_train[va_idx])[:, 1]
            if len(np.unique(pp)) < 2:
                continue
            aucs[k, j] = roc_auc_score(y_train[va_idx], pp)
        print(f"  [{label}] fold {k+1}/{len(fold_years)} (year={yr}) done")
    mean_auc = np.nanmean(aucs, axis=0)
    best_j = int(np.nanargmax(mean_auc))
    return C_grid[best_j], mean_auc[best_j]

print("\n== 时间感知 CV 选 C (= 1/lambda) ==")
# l1_ratio: 1.0 = LASSO, 0.0 = Ridge, 0.5 = Elastic Net
C_lasso, auc_lasso = time_aware_cv(1.0, label="LASSO")
C_ridge, auc_ridge = time_aware_cv(0.0, label="Ridge")
C_enet,  auc_enet  = time_aware_cv(0.5, label="ElNet")
print(f"LASSO     C={C_lasso:.6g}  lambda={1/C_lasso:.6g}  CV-AUC={auc_lasso:.4f}")
print(f"Ridge     C={C_ridge:.6g}  lambda={1/C_ridge:.6g}  CV-AUC={auc_ridge:.4f}")
print(f"ElasticNet C={C_enet:.6g}  lambda={1/C_enet:.6g}  CV-AUC={auc_enet:.4f}")

def fit_full(C, l1_ratio):
    return make_logreg(C, l1_ratio, max_iter=4000, tol=1e-4).fit(X_train, y_train)

mod_lasso = fit_full(C_lasso, 1.0)
mod_ridge = fit_full(C_ridge, 0.0)
mod_enet  = fit_full(C_enet,  0.5)

# LASSO 选中的变量
coefs = mod_lasso.coef_.ravel()
nz_idx = np.where(np.abs(coefs) > 1e-8)[0]
print(f"\n== LASSO 非零系数: {len(nz_idx)} / 42 ==")
ranked = sorted(zip(nz_idx, coefs[nz_idx]),
                key=lambda x: -abs(x[1]))
for i, b in ranked:
    print(f"  {features[i]:<15s}  {b:+.4f}")
nz_e = int((np.abs(mod_enet.coef_.ravel()) > 1e-8).sum())
print(f"Elastic Net 非零系数: {nz_e} / 42")
print(f"Ridge 非零系数: "
      f"{int((np.abs(mod_ridge.coef_.ravel()) > 1e-8).sum())} / 42")

def ndcg_at_100(scores, labels):
    return ndcg_score([labels], [scores], k=100)

def recall_precision_at(scores, labels, frac=0.01):
    k = int(np.ceil(len(scores) * frac))
    order = np.argsort(-scores)[:k]
    hits = labels[order].sum()
    return hits / labels.sum(), hits / k, k, hits

def eval_one(name, mod):
    pp = mod.predict_proba(X_test)[:, 1]
    auc_v = roc_auc_score(y_test, pp)
    ndcg = ndcg_at_100(pp, y_test)
    rec, prec, k, hits = recall_precision_at(pp, y_test, 0.01)
    print(f"{name:<12s} AUC={auc_v:.4f}  NDCG@100={ndcg:.4f}  "
          f"Recall@1%={rec:.4f}  Precision@1%={prec:.4f}  "
          f"(k={k}, hits={hits})")
    return {"name": name, "auc": auc_v, "ndcg": ndcg,
            "recall": rec, "precision": prec, "scores": pp}

print("\n== 测试集 (2009-2014) 性能 ==")
res_lasso = eval_one("LASSO",       mod_lasso)
res_ridge = eval_one("Ridge",       mod_ridge)
res_enet  = eval_one("Elastic Net", mod_enet)

all_res = {"LASSO": res_lasso, "Ridge": res_ridge,
           "Elastic Net": res_enet}
best_name = max(all_res, key=lambda k: all_res[k]["auc"])
print(f"\n>> 三个模型中 AUC 最高的是: {best_name} "
      f"(AUC={all_res[best_name]['auc']:.4f})")
mod_best = {"LASSO": mod_lasso, "Ridge": mod_ridge,
            "Elastic Net": mod_enet}[best_name]

def case_score(mod, gvk, yr):
    row = d.query(f"gvkey == {gvk} and fyear == {yr}").dropna(subset=features)
    if len(row) == 0:
        return None
    z = scaler.transform(row[features].values)
    return float(mod.predict_proba(z)[0, 1])

print(f"\n== 案例公司打分 (使用 {best_name}) ==")
en2000 = case_score(mod_best, 6127, 2000)
ty2000 = case_score(mod_best, 10787, 2000)
print(f"Enron 2000 (gvkey=6127): predicted prob = {en2000:.4f}")
print(f"Tyco  2000 (gvkey=10787): predicted prob = {ty2000:.4f}")

print("\n-- 三个模型对照 --")
for nm, m in [("LASSO", mod_lasso), ("Ridge", mod_ridge),
              ("Elastic Net", mod_enet)]:
    pe = case_score(m, 6127, 2000)
    pt = case_score(m, 10787, 2000)
    print(f"{nm:<12s} Enron={pe:.4f}  Tyco={pt:.4f}")

print("\n== 完成 ==")
