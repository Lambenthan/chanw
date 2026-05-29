#!/usr/bin/env node
/**
 * 抓 github.com/trending（GitHub 官方算法选的当日 / 本周热门），append 进 feed-raw.json。
 *
 * 设计哲学（关键）：
 *   不用 topic 白名单查询。topic 是发布者手贴的标签，要 2-3 个月才规范化，
 *   新范式来了根本查不到（确认偏差）。改成直接吃 GitHub 官方 trending 算法的
 *   结果——它综合 star velocity 选出"这两天真的在爆"的项目，零主观。
 *
 *   AI 相关性过滤交给下游 score-and-tag.mjs：它会把非 AI 项目打成"其他"分类
 *   丢掉。所以这里 trending 上的 CRM / 教程 / 英语学习等非 AI repo 抓进来也无妨，
 *   评分阶段自动滤掉。我们只负责"把 GitHub 认为在爆的都端上来"。
 *
 * 流程顺序：extract-feed → extract-github → enrich → score → convert
 *
 * GITHUB_TOKEN env (可选): 设了 API 补全走 5000/hr 否则 60/hr。GHA 自带。
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");
const FEED_RAW = path.join(projectRoot, "src/data/generated/feed-raw.json");

const TOKEN = process.env.GITHUB_TOKEN;
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";

// 抓 daily + weekly 两个窗口。daily 抓最新爆点，weekly 抓持续热度，并集去重。
const TRENDING_PAGES = [
  "https://github.com/trending?since=daily",
  "https://github.com/trending?since=weekly",
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function hashId(s) {
  return createHash("sha256").update(s).digest("hex").slice(0, 16);
}

/** 从 trending HTML 抽 owner/repo 列表（h2 锚定，避开 sponsor 链接）。 */
async function scrapeTrending(url) {
  const res = await fetch(url, { headers: { "User-Agent": UA } });
  if (!res.ok) {
    console.warn(`[github] trending ${url} HTTP ${res.status}`);
    return [];
  }
  const html = await res.text();
  const articles = html.match(/<article class="Box-row">[\s\S]*?<\/article>/g) ?? [];
  const repos = [];
  for (const a of articles) {
    const h2 = a.match(/<h2[^>]*>([\s\S]*?)<\/h2>/);
    if (!h2) continue;
    const m = h2[1].match(/href="\/([^"]+)"/);
    if (!m) continue;
    const fullName = m[1].trim().replace(/\s+/g, "");
    // 必须是 owner/repo 两段式
    if (!/^[^/]+\/[^/]+$/.test(fullName)) continue;
    repos.push(fullName);
  }
  return repos;
}

/** 用 GitHub API 补全单个 repo 的 stars / 描述 / 语言 / pushed_at。 */
async function fetchRepoMeta(fullName) {
  const headers = {
    "User-Agent": "chanw-feed/1.0",
    Accept: "application/vnd.github+json",
  };
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;
  const res = await fetch(`https://api.github.com/repos/${fullName}`, { headers });
  if (!res.ok) {
    if (res.status === 403) console.warn(`[github] API rate-limited at ${fullName}`);
    return null;
  }
  return res.json();
}

async function main() {
  // 1. 抓两个 trending 页，并集去重
  const seen = new Set();
  const order = [];
  for (const url of TRENDING_PAGES) {
    const repos = await scrapeTrending(url);
    console.log(`[github] ${url}  -> ${repos.length} repos`);
    for (const r of repos) {
      if (!seen.has(r)) {
        seen.add(r);
        order.push(r);
      }
    }
    await sleep(1500);
  }
  console.log(`[github] 并集 ${order.length} 个 unique trending repos`);

  // 2. 逐个补全 meta（节流 GitHub API）
  const items = [];
  for (const fullName of order) {
    const meta = await fetchRepoMeta(fullName);
    await sleep(TOKEN ? 300 : 1200); // 无 token 时 60/hr，慢点避免 403
    if (!meta || !meta.html_url) continue;
    const desc = meta.description ?? "";
    items.push({
      source: "github-trending",
      sourceName: "GitHub Trending",
      id: hashId(meta.html_url),
      title: desc ? `${meta.full_name} · ${desc.slice(0, 100)}` : meta.full_name,
      url: meta.html_url,
      summary: desc,
      category: meta.language ?? "",
      // trending 项目的"时间"用 pushed_at（最近活跃），符合"它正在热"的语义
      publishedAt: meta.pushed_at,
      discoveredAt: new Date().toISOString(),
      stars: meta.stargazers_count,
      repoTopics: meta.topics ?? [],
      owner: meta.owner?.login,
    });
  }
  console.log(`[github] 补全 ${items.length} 个 repo meta`);

  // 3. 追加去重写回 feed-raw.json
  const raw = JSON.parse(await fs.readFile(FEED_RAW, "utf8"));
  const existing = Array.isArray(raw) ? raw : raw.items ?? [];
  const existingUrls = new Set(existing.map((e) => e.url));
  const toAdd = items.filter((r) => !existingUrls.has(r.url));

  const out = Array.isArray(raw)
    ? [...existing, ...toAdd]
    : { ...raw, items: [...existing, ...toAdd] };

  await fs.writeFile(FEED_RAW, JSON.stringify(out, null, 2));
  console.log(
    `[github] ${toAdd.length} new appended (${items.length - toAdd.length} 已存在跳过)`,
  );
  console.log(
    `[github] feed-raw.json now has ${Array.isArray(out) ? out.length : out.items.length} items`,
  );
}

main().catch((e) => {
  console.error("[github] fatal:", e);
  process.exit(1);
});
