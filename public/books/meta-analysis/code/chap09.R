# =========================================================
# Chapter 9: 敏感性分析与影响诊断
# leave-one-out / 累积 meta / influence diagnostics
# =========================================================

library(tidyverse)
library(metafor)
library(here)
library(ragg)
source(here::here("code", "_theme.R"))
set.seed(2026)

d  <- read_csv(here::here("data", "bcg.csv"), show_col_types = FALSE)
es <- escalc(measure = "RR", ai = tpos, bi = tneg,
             ci = cpos, di = cneg, data = d, append = TRUE)

re <- rma(yi, vi, data = es, method = "REML", test = "knha")

# ---------- Leave-one-out ----------
loo <- leave1out(re, transf = exp)
cat("\n===== Leave-one-out (RR scale) =====\n")
print(loo, digits = 4)

# ---------- 累积 meta（按年份） ----------
es_sorted <- es |> arrange(year)
re_sorted <- rma(yi, vi, data = es_sorted, method = "REML", test = "knha")
cum <- cumul(re_sorted, transf = exp)
cat("\n===== 累积 meta（按发表年份） =====\n")
print(cum, digits = 4)

# ---------- 影响诊断 ----------
inf <- influence(re)
cat("\n===== 影响诊断指标 =====\n")
print(inf)

# 把影响诊断的关键统计输出出来
inf_df <- data.frame(
  trial   = es$trial,
  author  = es$author,
  rstu    = round(inf$inf$rstudent, 3),  # studentized residual
  dffits  = round(inf$inf$dffits, 3),    # DFFITS
  cookd   = round(inf$inf$cook.d, 3),    # Cook's distance
  hatval  = round(inf$inf$hat, 3),        # leverage
  weight_pct = round(inf$inf$weight, 2)
)
cat("\n===== 各研究的影响诊断 =====\n")
print(inf_df)

# 标记 influential studies
infl_flag <- inf$is.infl
cat("\n===== metafor 标记的 influential 研究 =====\n")
flagged <- which(infl_flag)
if (length(flagged) > 0) {
  cat("研究编号：", flagged, "\n")
  cat("研究作者：", es$author[flagged], "\n")
} else {
  cat("（无）\n")
}

# ---------- Forest of leave-one-out ----------
loo_df <- data.frame(
  excluded_trial  = es$trial,
  excluded_author = paste0(es$author, " (", es$year, ")"),
  RR    = loo$estimate,
  ci_lb = loo$ci.lb,
  ci_ub = loo$ci.ub
) |>
  mutate(label = factor(excluded_author, levels = excluded_author))

p1 <- ggplot(loo_df, aes(x = RR, y = label)) +
  geom_vline(xintercept = exp(re$beta), linetype = "dashed",
             color = "#EF6548", linewidth = 0.6) +
  geom_vline(xintercept = 1, color = "gray70", linewidth = 0.4) +
  geom_errorbar(aes(xmin = ci_lb, xmax = ci_ub),
                width = 0.2, color = "#4292C6") +
  geom_point(size = 2.5, color = "#EF6548") +
  scale_x_log10() +
  labs(x = "合并 RR (去掉某项后)", y = "去掉的研究",
       title = "Leave-one-out 敏感性分析",
       subtitle = "红色虚线为完整 13 项的合并 RR = 0.49") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap09_leave1out.png"),
       p1, width = 7, height = 5, dpi = 300, device = ragg::agg_png)

# ---------- 累积 meta forest ----------
cum_df <- data.frame(
  added_author = paste0(es_sorted$author, " (", es_sorted$year, ")"),
  RR    = cum$estimate,
  ci_lb = cum$ci.lb,
  ci_ub = cum$ci.ub
) |>
  mutate(label = factor(added_author, levels = added_author))

p2 <- ggplot(cum_df, aes(x = RR, y = label)) +
  geom_vline(xintercept = 1, color = "gray70", linewidth = 0.4) +
  geom_errorbar(aes(xmin = ci_lb, xmax = ci_ub),
                width = 0.2, color = "#4292C6") +
  geom_point(size = 2.5, color = "#EF6548") +
  scale_x_log10() +
  labs(x = "累积合并 RR", y = "新加入的研究",
       title = "累积 meta 分析（按发表年份）",
       subtitle = "每加入一项研究后的合并 RR；CI 收敛过程反映证据累积") +
  theme_book(base_size = 11)

ggsave(here::here("figure", "chap09_cumul.png"),
       p2, width = 7, height = 5, dpi = 300, device = ragg::agg_png)

# ---------- 影响诊断图 ----------
pdf(here::here("figure", "chap09_influence.pdf"),
    width = 8, height = 8, family = "Times")
plot(inf)
dev.off()

cat("\n===== Chapter 9 figures generated =====\n")
