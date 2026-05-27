# 05_gsc.R —— GSC (Xu 2017): r ∈ {0,1,2} 敏感性
# 单 treated unit + factor model 容易过拟合，本章诚实呈现不同 r 下 ATT 的差异

suppressPackageStartupMessages({
  library(tidyverse); library(gsynth); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

smoking <- read.csv(here::here("data", "smoking.csv"))
smoking$treated <- with(smoking, ifelse(state == "California" & year >= 1989, 1, 0))

fit_gsc <- function(r) {
  set.seed(2026)
  gsynth(cigsale ~ treated,
         data = smoking, index = c("state", "year"),
         force = "two-way",
         CV = FALSE, r = r,
         se = TRUE, inference = "nonparametric",
         nboots = 500, parallel = FALSE, seed = 2026)
}

cat("===== GSC 敏感性（r ∈ {0,1,2}） =====\n")
fits <- list()
sens_tbl <- data.frame()
for (r in c(0, 1, 2)) {
  cat("\n--- r =", r, "---\n")
  fit <- fit_gsc(r)
  fits[[as.character(r)]] <- fit
  row <- data.frame(
    r = r,
    ATT = round(fit$att.avg, 3),
    SE  = round(fit$est.avg[2], 3),
    CI_lower = round(fit$est.avg[3], 2),
    CI_upper = round(fit$est.avg[4], 2),
    p_value  = round(fit$est.avg[5], 4)
  )
  print(row)
  sens_tbl <- bind_rows(sens_tbl, row)
}
cat("\n=== 汇总 ===\n")
print(sens_tbl)
write.csv(sens_tbl, here::here("data", "chap05_gsc_sens.csv"), row.names = FALSE)

# 用 r=0（两路 FE，等价于带固定效应的 DiD）做主结果
gsc_main <- fits[["0"]]
saveRDS(gsc_main, here::here("data", "gsc_out.rds"))

# 取 CA 的反事实
ca_idx <- which(smoking$state == "California")
ca_dat <- smoking[ca_idx, ] |> arrange(year)
# gsc$Y.ct 是 T × Ntr 矩阵（T=31 年, Ntr=1）
if (is.matrix(gsc_main$Y.ct)) {
  ct_vec <- as.numeric(gsc_main$Y.ct[, 1])
} else {
  ct_vec <- as.numeric(gsc_main$Y.ct)
}
cat("\nlength(ca_dat) =", nrow(ca_dat), "  length(Y.ct) =", length(ct_vec), "\n")
ca_dat$synth_y <- ct_vec

# === 图 1：CA 实际 vs GSC r=0 反事实 ===
p1 <- ca_dat |>
  select(year, cigsale, synth_y) |>
  pivot_longer(c(cigsale, synth_y), names_to = "type", values_to = "y") |>
  mutate(type = ifelse(type == "cigsale", "California 实际", "GSC 反事实（r=0）")) |>
  ggplot(aes(x = year, y = y, color = type, linetype = type)) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  annotate("text", x = 1989.3, y = 35, label = "Prop 99 → 1989",
           color = "gray30", hjust = 0, family = "Heiti TC", size = 3.2) +
  geom_line(linewidth = 1.0) +
  scale_color_manual(values = c("California 实际"   = COLOR_TREAT,
                                "GSC 反事实（r=0）" = COLOR_DONOR)) +
  scale_linetype_manual(values = c("California 实际" = "solid",
                                   "GSC 反事实（r=0）" = "dashed")) +
  scale_x_continuous(breaks = seq(1970, 2000, 5)) +
  scale_y_continuous(limits = c(20, 200)) +
  labs(x = "年份", y = "人均香烟销量（packs / capita）",
       color = NULL, linetype = NULL,
       title = "GSC r=0（双向固定效应 / DiD 等价）反事实") +
  theme_book()
ggsave(here::here("figure", "chap05_gsc_counterfactual.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

# === 图 2：r ∈ {0,1,2} 三个 ATT 与 CI ===
sens_tbl$r_label <- paste0("r = ", sens_tbl$r)
p2 <- sens_tbl |>
  ggplot(aes(x = r_label, y = ATT)) +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_pointrange(aes(ymin = CI_lower, ymax = CI_upper),
                  color = COLOR_TREAT, linewidth = 0.8, size = 0.7) +
  geom_text(aes(label = sprintf("ATT = %.2f", ATT)),
            family = "Times New Roman", size = 3.2,
            hjust = -0.4, color = COLOR_TREAT) +
  coord_flip() +
  labs(x = NULL, y = "ATT 估计 与 95% bootstrap CI",
       title = "GSC ATT 对 factor 数 r 的敏感性") +
  theme_book()
ggsave(here::here("figure", "chap05_gsc_sens.png"),
       p2, width = 7, height = 3.5, dpi = 300, device = ragg::agg_png)

cat("\nDONE chap05.\n")
