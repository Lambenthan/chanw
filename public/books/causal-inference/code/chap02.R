# Chapter 2: 因果结构与识别条件
# DAG + dagitty 推导调整集

library(dagitty)
set.seed(2026)

# ── 定义 RHC 的因果结构 ──────────────────────────────────
# 三组协变量都是混杂，每组既影响医生是否决定上 RHC，也影响病人结局
rhc_dag <- dagitty("dag {
  severity   [pos=\"1,0\"]
  comorbidity [pos=\"2,0\"]
  demographics [pos=\"0,0\"]
  A          [pos=\"0.5,1.5\"]
  Y          [pos=\"2,1.5\"]
  severity -> A
  severity -> Y
  comorbidity -> A
  comorbidity -> Y
  demographics -> A
  demographics -> Y
  A -> Y
}")
exposures(rhc_dag) <- "A"
outcomes(rhc_dag)  <- "Y"

# dagitty 自动推导最小调整集
adjustmentSets(rhc_dag, type = "minimal")
