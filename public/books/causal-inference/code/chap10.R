# Chapter 10: 全书汇总——十种方法的终极对比
# 森林图汇总所有方法的 ATE 估计

library(ggplot2)
set.seed(2026)

# ── 从第 3--9 章收集的真实估计值 ─────────────────────────
methods <- c(
  "G Computation (Ch.4)", "PSM (Ch.5)", "IPW (Ch.5)",
  "Overlap Weights (Ch.5)", "AIPW (Ch.6)", "DML (Ch.7)",
  "TMLE (Ch.7)", "Causal Forest (Ch.9)")
est   <- c(0.052, 0.076, 0.055, 0.061, 0.044, 0.040, 0.088, 0.044)
ci_lo <- c(0.027, 0.041, 0.025, 0.033, 0.017, 0.014, 0.074, 0.020)
ci_hi <- c(0.082, 0.109, 0.085, 0.089, 0.072, 0.065, 0.103, 0.068)

df <- data.frame(method = factor(methods, levels = rev(methods)),
                 est = est, lo = ci_lo, hi = ci_hi)

# ── 森林图 ───────────────────────────────────────────────
ggplot(df, aes(x = est, y = method)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey50") +
  geom_point(size = 3, color = "#EF6548") +
  geom_errorbar(aes(xmin = lo, xmax = hi), width = 0.25,
                color = "#4292C6", linewidth = 0.7, orientation = "y") +
  labs(x = "Risk Difference (RD)", y = NULL,
       title = "ATE Estimates Across Eight Methods") +
  scale_x_continuous(breaks = seq(-0.02, 0.12, 0.02)) +
  theme_minimal(base_size = 14, base_family = "serif") +
  theme(panel.grid.minor = element_blank(),
        panel.grid.major.y = element_blank(),
        plot.title = element_text(hjust = 0.5))
