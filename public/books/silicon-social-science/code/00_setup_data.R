# 00_setup_data.R —— GSS 2016 数据 + persona 池 + 关键态度题
# 数据：socviz::gss_sm（GSS 2016，2867 受访者 × 32 变量）
# 输出：
#   data/gss_personas.csv  —— 100 受访者人口学 + 真实回答
#   data/gss_full.csv      —— 完整 2867 行（用于真实分布基准）
#   data/gss_questions.csv —— 10 个态度题 + 选项标签

suppressPackageStartupMessages({
  library(socviz)
  library(dplyr)
  library(here)
  library(readr)
})

# 1. 完整 GSS subset 落盘（用于真实分布基准）
data(gss_sm)
gss <- as.data.frame(gss_sm)
# 选 demographics + 关键态度
demo_vars <- c("year", "id", "age", "sex", "race", "region", "degree",
               "income16", "relig", "marital")
# socviz::gss_sm 里 attitude 维度有 polviews / partyid（如果存在）
# 实际查 gss_sm 的可用 attitude 变量
cat("可用变量：\n"); print(names(gss))

# 选择存在的态度变量
target_vars <- c("happy", "polviews", "partyid", "fefam", "racdif1",
                 "abany", "letin1", "owngun", "godchnge", "wrkstat")
target_vars <- target_vars[target_vars %in% names(gss)]
cat("\n选中的态度变量：", target_vars, "\n")

# 完整数据导出
cols_keep <- intersect(c(demo_vars, target_vars), names(gss))
gss_subset <- gss[, cols_keep]
write_csv(gss_subset, here("data", "gss_full.csv"))
cat("\ngss_full.csv：", nrow(gss_subset), "行 ×", ncol(gss_subset), "列\n")

# 2. 抽 100 个 persona 池（按 sex × race × region × age 分层）
set.seed(2026)
gss_clean <- gss_subset |>
  filter(!is.na(age), !is.na(sex), !is.na(race), !is.na(region),
         !is.na(degree), !is.na(income16))
# 简单 stratified sample by sex × race
personas <- gss_clean |>
  group_by(sex, race) |>
  slice_sample(n = 20) |>     # 每 sex×race 组 20 个 = 6 组 × 20 = 120
  ungroup() |>
  slice_sample(n = 100)        # 再随机抽 100
cat("\npersona 池：", nrow(personas), "行\n")
table(personas$sex, personas$race) |> print()

write_csv(personas, here("data", "gss_personas.csv"))

# 3. 题目目录（中英文）
questions_df <- data.frame(
  qid = c("happy", "polviews", "partyid", "fefam", "racdif1",
          "abany", "letin1", "owngun", "wrkstat"),
  q_en = c(
    "Taken all together, how would you say things are these days?",
    "Where would you place yourself on a political scale from extremely liberal to extremely conservative?",
    "Generally speaking, do you usually think of yourself as a Republican, Democrat, Independent, or what?",
    "It is much better for everyone if the man is the achiever outside the home and the woman takes care of the home and family. Do you agree?",
    "On average, Blacks have worse jobs, income, and housing than White people. Is this because of discrimination?",
    "Do you think it should be possible for a pregnant woman to obtain a legal abortion if the woman wants it for any reason?",
    "Do you think the number of immigrants from foreign countries who are permitted to come to the United States to live should be increased a lot, increased a little, remain the same, reduced a little, or reduced a lot?",
    "Do you happen to have in your home any guns or revolvers?",
    "Last week were you working full time, part time, going to school, keeping house, or what?"
  ),
  q_zh = c(
    "整体来看，最近你的生活怎么样？",
    "你的政治立场是从极自由派到极保守派的哪一端？",
    "你通常认为自己是共和党人、民主党人、独立派，还是其他？",
    "男人在外打拼、女人在家照顾家庭，对每个人都更好。你同意吗？",
    "黑人平均比白人工作差、收入低、住房差。这是因为歧视吗？",
    "如果一名孕妇出于任何理由想要终止妊娠，你认为应该合法吗？",
    "你认为允许移民进入美国的人数应当增加还是减少？",
    "你家中是否有枪？",
    "上周你是全职工作、兼职工作、上学、料理家务，还是其他？"
  ),
  stringsAsFactors = FALSE
)
questions_df <- questions_df[questions_df$qid %in% target_vars, ]
cat("\n问卷题目：", nrow(questions_df), "题\n")
write_csv(questions_df, here("data", "gss_questions.csv"))

cat("\n=== 真实回答边际分布（前 3 题）===\n")
for(q in head(questions_df$qid, 3)) {
  cat("\n--", q, "--\n")
  tab <- table(gss_subset[[q]], useNA = "no")
  pct <- round(100 * tab / sum(tab), 1)
  print(data.frame(value = names(tab), count = as.numeric(tab), pct = pct))
}

cat("\nDONE setup_data.R\n")
