# 04_permutation.R —— Abadie 推断：按 pre-RMSPE 过滤后的 placebo 推断
# Abadie 2010 标准: 删 pre-MSPE > k × CA 的州（k = 2, 5, 20）
# 实践补丁: 同时删 pre-MSPE < 0.5 的 degenerate fits

suppressPackageStartupMessages({
  library(tidyverse); library(tidysynth); library(here); library(ragg); library(showtext)
})
source(here::here("code", "_theme.R"))
set.seed(2026)

sc_out <- readRDS(here::here("data", "sc_out_classic.rds"))
sig_tab <- sc_out |> grab_significance(time_window = 1989:2000)
ca_pre <- sig_tab |> filter(unit_name == "California") |> pull(pre_mspe)
ca_post <- sig_tab |> filter(unit_name == "California") |> pull(post_mspe)
ca_ratio <- sig_tab |> filter(unit_name == "California") |> pull(mspe_ratio)
cat("California pre-MSPE   =", round(ca_pre, 4), "\n")
cat("California post-MSPE  =", round(ca_post, 4), "\n")
cat("California RMSPE 比值 =", round(ca_ratio, 3), "\n\n")

# 删 degenerate fit (pre_mspe < 0.5) + Abadie filter
do_rank <- function(k, min_pre = 0.5) {
  keep <- sig_tab |> filter(pre_mspe <= k * ca_pre, pre_mspe >= min_pre)
  ca_rk <- which(keep$unit_name[order(-keep$mspe_ratio)] == "California")
  p_val <- ca_rk / nrow(keep)
  data.frame(k = k, n_kept = nrow(keep), ca_rank = ca_rk, p_value = round(p_val, 4))
}

cat("=== p 值随过滤阈值 k 变化（min pre-MSPE = 0.5） ===\n")
ranks <- bind_rows(lapply(c(2, 5, 20, 1000), do_rank))
print(ranks)

# 同时报告: 不删 degenerate
do_rank_raw <- function(k) {
  keep <- sig_tab |> filter(pre_mspe <= k * ca_pre)
  ca_rk <- which(keep$unit_name[order(-keep$mspe_ratio)] == "California")
  p_val <- ca_rk / nrow(keep)
  data.frame(k = k, n_kept = nrow(keep), ca_rank = ca_rk, p_value = round(p_val, 4))
}
cat("\n=== p 值（不过滤 degenerate） ===\n")
ranks_raw <- bind_rows(lapply(c(2, 5, 20, 1000), do_rank_raw))
print(ranks_raw)

# 用 k=20, min_pre=0.5 做主图
k_use <- 20
keep_units <- sig_tab |> filter(pre_mspe <= k_use * ca_pre, pre_mspe >= 0.5) |> pull(unit_name)
cat("\n=== 主图过滤参数 k =", k_use, " min_pre = 0.5 ===\n")
cat("保留 placebo + CA = ", length(keep_units), " 州\n")

all_gaps <- sc_out |> grab_synthetic_control(placebo = TRUE) |>
  mutate(gap = real_y - synth_y,
         is_ca = .placebo == 0)

# === 图 1：过滤后 placebo gap ===
p1 <- ggplot() +
  geom_hline(yintercept = 0, color = "gray60", linewidth = 0.3) +
  geom_vline(xintercept = 1989, color = "gray60", linetype = "dashed", linewidth = 0.4) +
  geom_line(data = all_gaps |> filter(!is_ca, .id %in% keep_units),
            aes(x = time_unit, y = gap, group = .id),
            color = "gray70", alpha = 0.7, linewidth = 0.4) +
  geom_line(data = all_gaps |> filter(is_ca),
            aes(x = time_unit, y = gap),
            color = COLOR_TREAT, linewidth = 1.05) +
  annotate("text", x = 1998, y = -48, label = "California 真实",
           color = COLOR_TREAT, family = "Heiti TC", size = 3.3, hjust = 1) +
  annotate("text", x = 1972, y = -48,
           label = paste0("过滤后 ", length(keep_units) - 1, " 个 placebo 州"),
           color = "gray45", family = "Heiti TC", size = 3.3, hjust = 0) +
  scale_x_continuous(breaks = seq(1970, 2000, 5)) +
  scale_y_continuous(limits = c(-50, 50)) +
  labs(x = "年份", y = "Gap（实际 − 合成）") +
  theme_book()
ggsave(here::here("figure", "chap04_filtered_placebo.png"),
       p1, width = 7, height = 4.2, dpi = 300, device = ragg::agg_png)

# === 图 2：过滤后 RMSPE 比值排序 ===
keep_sig <- sig_tab |> filter(unit_name %in% keep_units) |>
  arrange(desc(mspe_ratio)) |>
  mutate(rk = row_number(),
         is_ca = unit_name == "California",
         label = ifelse(is_ca,
                        paste0("California 排名 ", rk, " / ", n()),
                        NA))

p2 <- keep_sig |>
  ggplot(aes(x = reorder(unit_name, mspe_ratio), y = mspe_ratio, fill = is_ca)) +
  geom_col(width = 0.7, alpha = 0.92) +
  geom_text(aes(label = label),
            hjust = -0.1, family = "Heiti TC", size = 3.3, color = COLOR_TREAT,
            na.rm = TRUE) +
  scale_fill_manual(values = c("FALSE" = COLOR_DONOR, "TRUE" = COLOR_TREAT),
                    guide = "none") +
  coord_flip() +
  labs(x = NULL, y = "post / pre RMSPE 比值") +
  theme_book(base_size = 9)
ggsave(here::here("figure", "chap04_rmspe_ratio_filtered.png"),
       p2, width = 6.5, height = 6.5, dpi = 300, device = ragg::agg_png)

write.csv(ranks, here::here("data", "chap04_ranks.csv"), row.names = FALSE)
write.csv(ranks_raw, here::here("data", "chap04_ranks_raw.csv"), row.names = FALSE)

cat("\nDONE chap04.\n")
