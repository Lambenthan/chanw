#!/usr/bin/env node
/**
 * 转接层：把 src/data/generated/feed-{scored,raw}.json 映射成
 * src/data/news.json（当前站点 news 页直接 import 的文件）。
 *
 * 优先级：
 *   feed-scored.json（含 LLM 评分、分类、中文摘要）—— 如果存在
 *   feed-raw.json（仅抓取层，无 cn）—— 备用
 *
 * 输出 schema 匹配 src/pages/news.astro 期望：
 *   { title, url, source, date, group }
 *
 * group 由 source id 映射到 labs / papers / gh / hn。
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");

const SCORED = path.join(projectRoot, "src/data/generated/feed-scored.json");
const RAW = path.join(projectRoot, "src/data/generated/feed-raw.json");
const EXTRAS_RAW = path.join(projectRoot, "src/data/generated/feed-extras-raw.json");
const AIGCLINK_RAW = path.join(projectRoot, "src/data/generated/feed-aigclink-raw.json");
const OUT = path.join(projectRoot, "src/data/news.json");

// === news 质量理念（每次 cron 常驻执行，不是一次性清洗）===
// 1. 真日期 overrides: OpenAI/Google/DeepMind 等 JS 渲染源 sitemap 抓取拿不到
//    真发布日期, prune-news.mjs 抓到的真日期存这里, convert 用它覆盖假戳
const DATE_OVERRIDES = path.join(projectRoot, "src/data/news-date-overrides.json");
// 2. 通稿黑名单: filter-press-releases.mjs 判定为公关通告的 url, 永久排除
const EXCLUDE = path.join(projectRoot, "src/data/news-exclude.json");
// 3. 时间窗: news 是"最新动态"不是档案馆, 只保留最近 N 天有真日期的
const WINDOW_DAYS = parseInt(process.env.NEWS_WINDOW_DAYS ?? "90", 10);
// 4. JS 渲染源: 这三家页面纯 JS 渲染, sitemap archive 抓取的 publishedAt 是
//    批量假戳不可信. 只信 overrides 里抓到的真日期; 不在 overrides 的一律排除.
//    (enrich/prune 抓到真日期会进 overrides, 那时它们自然重新进来)
const JS_RENDERED_SOURCES = new Set(["OpenAI", "Google AI", "DeepMind"]);

// source id → group
const PAPER_SOURCES = new Set(["arxiv", "hf-papers"]);
const GH_SOURCES = new Set(["github-trending", "github"]);

function groupFor(srcId) {
  if (PAPER_SOURCES.has(srcId)) return "papers";
  if (GH_SOURCES.has(srcId)) return "gh";
  return "labs"; // 默认所有厂商发布、AIGCLINK 都归 labs
}

async function readJsonSafe(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

async function main() {
  // 输入优先 scored，没有就读 raw
  const scored = await readJsonSafe(SCORED);
  const raw = await readJsonSafe(RAW);
  const extras = await readJsonSafe(EXTRAS_RAW);
  const aigclink = await readJsonSafe(AIGCLINK_RAW);

  // 合并源：scored 是 union(raw + extras + aigclink) 经评分后的子集
  // 若 scored 存在则用 scored.items；否则用 raw + extras + aigclink 合集
  let items;
  if (scored && Array.isArray(scored.items)) {
    items = scored.items;
    console.log(`[convert] 用 feed-scored.json：${items.length} 条`);
  } else {
    items = [];
    for (const file of [raw, extras, aigclink]) {
      if (file && Array.isArray(file.items)) items.push(...file.items);
    }
    console.log(`[convert] feed-scored.json 不存在，合并 raw + extras + aigclink：${items.length} 条`);
  }

  // 去重（按 id 或 url）
  const seen = new Set();
  const deduped = [];
  for (const item of items) {
    const key = item.id || item.url;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }

  // 加载三套质量理念的数据
  const overrides = (await readJsonSafe(DATE_OVERRIDES)) ?? {};
  const excludeList = (await readJsonSafe(EXCLUDE)) ?? [];
  const excludeSet = new Set(Array.isArray(excludeList) ? excludeList : []);
  const cutoff = Date.now() - WINDOW_DAYS * 86400_000;

  // 映射成 news.json schema。
  // 关键决策：date 只取 publishedAt（或真日期 override），绝不 fallback 到
  // discoveredAt —— 后者是脚本第一次见到 URL 的时间，与"实际发布时间"无关。
  const mapped = deduped
    .map((item) => ({
      title: item.title || item.originalTitle || "（无标题）",
      url: item.url,
      source: item.sourceName || item.source || "未知",
      // 真日期 override 优先于抓取层 publishedAt（修 JS 渲染源的假戳）
      date: overrides[item.url] || item.publishedAt || "",
      group: groupFor(item.source),
    }))
    .filter((n) => n.url && n.title);

  // 四道常驻过滤（理念固化）：
  const news = mapped.filter((n) => {
    if (excludeSet.has(n.url)) return false; // ① 通稿黑名单
    // ② JS 渲染源不在真日期 overrides 里 → 假戳不可信，排除
    if (JS_RENDERED_SOURCES.has(n.source) && !overrides[n.url]) return false;
    if (!n.date) return false; // ③ 删无真日期
    if (new Date(n.date).getTime() < cutoff) return false; // ④ 砍时间窗
    return true;
  });

  // 按时间倒序
  news.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  await fs.writeFile(OUT, JSON.stringify(news, null, "\t"), "utf8");

  const groupCount = news.reduce((m, n) => {
    m[n.group] = (m[n.group] ?? 0) + 1;
    return m;
  }, {});
  console.log(
    `[convert] 理念过滤：${mapped.length} → ${news.length} ` +
      `(黑名单 ${excludeSet.size} url, 窗 ${WINDOW_DAYS}d, overrides ${Object.keys(overrides).length})`,
  );
  console.log(`[convert] ✓ 写入 ${OUT}：${news.length} 条`);
  console.log(`[convert]   分组：${JSON.stringify(groupCount)}`);
  if (news[0]) console.log(`[convert]   最新：${news[0].title} | ${news[0].date}`);
}

main().catch((e) => {
  console.error(`[convert] 失败：${e.message}`);
  process.exit(1);
});
