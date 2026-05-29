#!/usr/bin/env node
/**
 * news-date-overrides.json 维护器 (cron 常驻步骤)。
 *
 * 病根: OpenAI / Google AI / DeepMind 页面纯 JS 渲染, sitemap archive 抓取
 * 拿不到真实发布日期, publishedAt 是批量假戳. 本脚本对这三家的条目逐个开
 * 网页抓真实 published_time, 抓到的写进 news-date-overrides.json (url→真日期).
 * convert-feed-to-news.mjs 消费它: JS 源只有在 overrides 里(有真日期)才放行.
 *
 * 增量 + 限流 (跟 enrich-feed-dates 同模式):
 *   - 跳过已在 overrides 或已尝试过(news-date-attempted.json)的 url
 *   - 每次最多抓 MAX_NEW 条 (CI 限流避免单次 cron 超时), 本地默认 Infinity
 *   - 历史 archive (~900 条) 分多次 cron 慢慢消化; 之后只抓 RSS 新增
 *
 * 不改 news.json (那是 convert 的职责). 只维护 overrides + attempted 两个文件.
 *
 * env: CONCURRENCY (默认 8), MAX_NEW (CI 传 80, 本地 Infinity)
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");
const FEED_RAW = path.join(projectRoot, "src/data/generated/feed-raw.json");
const OVERRIDES = path.join(projectRoot, "src/data/news-date-overrides.json");
const ATTEMPTED = path.join(projectRoot, "src/data/news-date-attempted.json");

const CONCURRENCY = parseInt(process.env.CONCURRENCY ?? "8", 10);
const MAX_NEW = process.env.MAX_NEW ? parseInt(process.env.MAX_NEW, 10) : Infinity;
const TIMEOUT_MS = 18_000;
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";

const JS_RENDERED = new Set(["OpenAI", "Google AI", "DeepMind"]);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const readJson = async (f, fallback) => {
  try { return JSON.parse(await fs.readFile(f, "utf8")); } catch { return fallback; }
};

let _browser = null;
async function getBrowser() {
  if (_browser) return _browser;
  const { chromium } = await import("playwright");
  _browser = await chromium.launch({ headless: true });
  return _browser;
}

async function extractDate(page) {
  return page.evaluate(() => {
    const og = document.querySelector('meta[property="article:published_time"]')?.getAttribute("content");
    if (og && !Number.isNaN(Date.parse(og))) return og;
    for (const ld of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const data = JSON.parse(ld.textContent || "null");
        for (const c of (Array.isArray(data) ? data : [data])) {
          if (c?.datePublished && !Number.isNaN(Date.parse(c.datePublished))) return c.datePublished;
          if (c?.["@graph"]) for (const g of c["@graph"])
            if (g?.datePublished && !Number.isNaN(Date.parse(g.datePublished))) return g.datePublished;
        }
      } catch {}
    }
    const t = document.querySelector("time[datetime]")?.getAttribute("datetime");
    if (t && !Number.isNaN(Date.parse(t))) return t;
    const m = document.querySelector('meta[name="publishdate"], meta[name="pubdate"], meta[name="date"]')?.getAttribute("content");
    if (m && !Number.isNaN(Date.parse(m))) return m;
    return null;
  });
}

async function fetchReal(item) {
  const browser = await getBrowser();
  const ctx = await browser.newContext({ userAgent: UA });
  const page = await ctx.newPage();
  try {
    await page.goto(item.url, { waitUntil: "domcontentloaded", timeout: TIMEOUT_MS });
    return await Promise.race([extractDate(page), sleep(6000).then(() => null)]);
  } catch { return null; }
  finally { await ctx.close().catch(() => {}); }
}

async function pool(items, n, work) {
  const queue = items.slice();
  let done = 0;
  const out = new Map();
  async function worker() {
    for (;;) {
      const job = queue.shift();
      if (!job) return;
      out.set(job.url, await work(job).catch(() => null));
      if (++done % 50 === 0 || done === items.length)
        process.stderr.write(`  抓取: ${done}/${items.length}\n`);
    }
  }
  await Promise.all(Array.from({ length: n }, worker));
  return out;
}

async function main() {
  const raw = await readJson(FEED_RAW, { items: [] });
  const items = Array.isArray(raw) ? raw : raw.items ?? [];
  const overrides = await readJson(OVERRIDES, {});
  const attempted = new Set(await readJson(ATTEMPTED, []));

  // 增量候选: JS 源 + 不在 overrides + 没尝试过
  const candidates = items.filter(
    (x) => JS_RENDERED.has(x.sourceName || x.source) && !overrides[x.url] && !attempted.has(x.url),
  );
  const batch = candidates.slice(0, MAX_NEW);
  console.error(
    `JS 源待抓 ${candidates.length} 条, 本次抓 ${batch.length} (MAX_NEW=${MAX_NEW === Infinity ? "∞" : MAX_NEW})`,
  );
  if (batch.length === 0) { console.error("无新候选, 跳过"); return; }

  const results = await pool(batch, CONCURRENCY, fetchReal);

  let fixed = 0;
  for (const x of batch) {
    attempted.add(x.url); // 不论成败都标记, 避免重抓
    const real = results.get(x.url);
    if (real && !Number.isNaN(Date.parse(real))) {
      overrides[x.url] = new Date(real).toISOString();
      fixed++;
    }
  }

  await fs.writeFile(OVERRIDES, JSON.stringify(overrides, null, "\t"));
  await fs.writeFile(ATTEMPTED, JSON.stringify([...attempted], null, "\t"));
  console.error(`✓ 抓到真日期 ${fixed}/${batch.length}`);
  console.error(`✓ overrides 累计 ${Object.keys(overrides).length}, attempted 累计 ${attempted.size}`);

  if (_browser) await _browser.close().catch(() => {});
}

main().catch((e) => { console.error("fatal:", e); process.exit(1); });
