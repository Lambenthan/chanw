#!/usr/bin/env node
/**
 * 拉 GitHub Search API 的 AI 类 trending 仓库，append 进 feed-raw.json。
 *
 * 为什么不放 feed-sources.yml: GitHub Search 不是 RSS/HTML 抓取，是 API 查询;
 * 跟现有 extract-feed.mjs 的 type 体系（rss/html/browser）不兼容，单独脚本更清晰。
 *
 * 运行顺序：extract-feed → extract-github → enrich → score → convert
 *
 * GITHUB_TOKEN env (可选): 设了 rate limit 5000/hr 否则 60/hr。GHA 自带 GITHUB_TOKEN。
 *
 * AI 主题列表：选 8 个高 signal 主题。每个主题查近 6 个月新创建 + ⭐≥200 的仓库 top 25。
 * 去重后预估 100-200 个新条目/次。
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");
const FEED_RAW = path.join(projectRoot, "src/data/generated/feed-raw.json");

const TOKEN = process.env.GITHUB_TOKEN;

// AI 相关主题，覆盖 LLM / Agent / RAG / 生成式 / Claude Code / Computer Use
const TOPICS = [
  "llm",
  "agent",
  "rag",
  "ai-agent",
  "generative-ai",
  "claude-code",
  "ai-tools",
  "computer-use",
];

// 近 6 个月创建 + ⭐ ≥ 200 才录入（过滤 vaporware 与未启动项目）
const SINCE_MONTHS = 6;
const MIN_STARS = 200;
const PER_TOPIC = 25;

const sinceDate = new Date(Date.now() - SINCE_MONTHS * 30 * 86400 * 1000)
  .toISOString()
  .slice(0, 10);

function hashId(s) {
  return createHash("sha256").update(s).digest("hex").slice(0, 16);
}

async function searchTopic(topic) {
  const q = `topic:${topic}+created:>=${sinceDate}+stars:>=${MIN_STARS}`;
  const url = `https://api.github.com/search/repositories?q=${q}&sort=stars&order=desc&per_page=${PER_TOPIC}`;
  const headers = {
    "User-Agent": "chanw-feed/1.0",
    Accept: "application/vnd.github+json",
  };
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;

  const res = await fetch(url, { headers });
  if (!res.ok) {
    console.warn(`[github] topic="${topic}" HTTP ${res.status}`);
    return [];
  }
  const data = await res.json();
  return data.items ?? [];
}

async function main() {
  const allRepos = new Map(); // dedupe by html_url

  for (const topic of TOPICS) {
    const items = await searchTopic(topic);
    let added = 0;
    for (const r of items) {
      if (allRepos.has(r.html_url)) continue;
      allRepos.set(r.html_url, {
        source: "github-trending",
        sourceName: "GitHub Trending",
        id: hashId(r.html_url),
        // title 形态：`owner/repo · 描述（限 100 字）`
        title: r.description
          ? `${r.full_name} · ${r.description.slice(0, 100)}`
          : r.full_name,
        url: r.html_url,
        summary: r.description ?? "",
        category: r.language ?? "",
        // publishedAt 用 pushed_at（最近活动）；GitHub trending 上看的就是"活跃"
        publishedAt: r.pushed_at,
        discoveredAt: new Date().toISOString(),
        // 额外 GitHub-specific 字段，UI 显示时可拿
        stars: r.stargazers_count,
        repoTopics: r.topics ?? [],
        owner: r.owner?.login,
      });
      added++;
    }
    console.log(`[github] topic="${topic}" got ${items.length}, +${added} new`);
    // 节流：每 topic 间停 2s，免得撞 rate limit
    await new Promise((r) => setTimeout(r, 2000));
  }

  // 读 feed-raw.json，追加去重写回
  const raw = JSON.parse(await fs.readFile(FEED_RAW, "utf8"));
  const existing = Array.isArray(raw) ? raw : raw.items ?? [];
  const existingUrls = new Set(existing.map((e) => e.url));
  const toAdd = [...allRepos.values()].filter((r) => !existingUrls.has(r.url));

  const out = Array.isArray(raw)
    ? [...existing, ...toAdd]
    : { ...raw, items: [...existing, ...toAdd] };

  await fs.writeFile(FEED_RAW, JSON.stringify(out, null, 2));
  console.log(
    `\n[github] queried ${TOPICS.length} topics, ${allRepos.size} unique repos, ${toAdd.length} new appended to feed-raw.json`,
  );
  console.log(
    `[github] feed-raw.json now has ${Array.isArray(out) ? out.length : out.items.length} items`,
  );
}

main().catch((e) => {
  console.error("[github] fatal:", e);
  process.exit(1);
});
