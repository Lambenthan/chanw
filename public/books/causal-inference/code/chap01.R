## ============================================================
## Chapter 01: 问题与数据——RHC 争议的起点
## 完整脚本：数据探索 + Table 1 + 图 + 粗死亡率
## ============================================================

library(tidyverse)
library(tableone)
set.seed(2026)

# --- 读入数据 ---
d <- read_csv(here::here("data", "rhc.csv"), show_col_types = FALSE) |>
  mutate(
    death180_bin = ifelse(death180 == "Yes", 1, 0),
    rhc_label = factor(ifelse(rhc == 1, "RHC", "No RHC"),
                       levels = c("No RHC", "RHC"))
  )

cat("Dimensions:", dim(d), "\n")

# --- 数据预览 ---
key_vars <- c("rhc", "death180", "age", "sex", "apache_score",
              "blood_pressure", "creatinine", "albumin",
              "heart_rate", "respiratory_rate")
print(head(d[, key_vars], 6))

# --- Table 1 with SMD ---
vars <- c("age", "sex", "apache_score", "blood_pressure",
          "heart_rate", "respiratory_rate", "creatinine",
          "albumin", "hematocrit", "wbc", "temperature",
          "das_index")

tab1 <- CreateTableOne(vars = vars, strata = "rhc_label",
                       data = d, test = FALSE, smd = TRUE)
print(tab1, smd = TRUE)

# --- 粗死亡率 ---
mort <- d |>
  group_by(rhc_label) |>
  summarise(
    n         = n(),
    deaths    = sum(death180_bin),
    mortality = mean(death180_bin),
    .groups   = "drop"
  )
print(mort)
cat("Crude difference:",
    mort$mortality[mort$rhc_label == "RHC"] -
      mort$mortality[mort$rhc_label == "No RHC"], "\n")

# --- Figure 1: APACHE 分布 ---
p1 <- ggplot(d, aes(x = apache_score, fill = rhc_label)) +
  geom_histogram(aes(y = after_stat(density)),
                 bins = 40, alpha = 0.6, position = "identity") +
  scale_fill_manual(values = c("No RHC" = "#4292C6",
                               "RHC"    = "#EF6548")) +
  labs(x = "APACHE Score", y = "Density", fill = "Group") +
  theme_minimal(base_size = 14, base_family = "serif") +
  theme(legend.position = c(0.85, 0.85))

ggsave(here::here("figure", "chap01_apache_dist.pdf"),
       p1, width = 7, height = 4.5)

# --- Figure 2: SMD Love plot ---
smd_vals <- ExtractSmd(tab1)
smd_df <- tibble(
  variable = rownames(smd_vals),
  smd      = as.numeric(smd_vals[, 1])
) |> mutate(variable = fct_reorder(variable, smd))

p2 <- ggplot(smd_df, aes(x = smd, y = variable)) +
  geom_point(size = 3, color = "#EF6548") +
  geom_vline(xintercept = 0.1, linetype = "dashed",
             color = "red", linewidth = 0.5) +
  labs(x = "Standardized Mean Difference (SMD)", y = NULL) +
  theme_minimal(base_size = 14, base_family = "serif") +
  theme(panel.grid.major.y = element_line(linetype = "dotted",
                                          color = "grey80"))

ggsave(here::here("figure", "chap01_smd_loveplot.pdf"),
       p2, width = 7, height = 5)

# --- Figure 3: 粗死亡率柱状图 ---
p3 <- ggplot(mort, aes(x = rhc_label, y = mortality, fill = rhc_label)) +
  geom_col(width = 0.5, alpha = 0.85) +
  geom_text(aes(label = sprintf("%.1f%%", mortality * 100)),
            vjust = -0.5, size = 5, family = "serif") +
  scale_fill_manual(values = c("No RHC" = "#4292C6",
                               "RHC"    = "#EF6548")) +
  scale_y_continuous(labels = scales::percent_format(),
                     limits = c(0, 0.65)) +
  labs(x = NULL, y = "180-Day Mortality") +
  theme_minimal(base_size = 14, base_family = "serif") +
  theme(legend.position = "none")

ggsave(here::here("figure", "chap01_crude_mortality.pdf"),
       p3, width = 5, height = 4.5)

cat("All Chapter 1 outputs generated.\n")
