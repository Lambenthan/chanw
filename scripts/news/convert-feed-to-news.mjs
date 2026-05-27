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

// source id → group
const PAPER_SOURCES = new Set(["arxiv", "hf-papers"]);
const GH_SOURCES = new Set(["github"]);

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

  // 映射成 news.json schema。
  // 关键决策：date 只取 publishedAt，绝不 fallback 到 discoveredAt
  // —— 后者是脚本第一次见到 URL 的时间，与"实际发布时间"无关，
  // 用它会显示假日期（例如 Meta AI 这类 Playwright 源全 632 条本来
  // 都掉进这个坑）。没真日期的条目 date=""，News card 上不显示
  // 时间戳；enrich-feed-dates.mjs 后续 cron 会逐批补真日期。
  const news = deduped
    .map((item) => ({
      title: item.title || item.originalTitle || "（无标题）",
      url: item.url,
      source: item.sourceName || item.source || "未知",
      date: item.publishedAt || "",
      group: groupFor(item.source),
    }))
    .filter((n) => n.url && n.title);

  // 按时间倒序
  news.sort((a, b) => {
    const ad = a.date ? new Date(a.date).getTime() : 0;
    const bd = b.date ? new Date(b.date).getTime() : 0;
    return bd - ad;
  });

  await fs.writeFile(OUT, JSON.stringify(news, null, "\t"), "utf8");

  const groupCount = news.reduce((m, n) => {
    m[n.group] = (m[n.group] ?? 0) + 1;
    return m;
  }, {});
  console.log(`[convert] ✓ 写入 ${OUT}：${news.length} 条`);
  console.log(`[convert]   分组：${JSON.stringify(groupCount)}`);
  if (news[0]) console.log(`[convert]   最新：${news[0].title} | ${news[0].date}`);
}

main().catch((e) => {
  console.error(`[convert] 失败：${e.message}`);
  process.exit(1);
});
