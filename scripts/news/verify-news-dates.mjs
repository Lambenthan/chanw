#!/usr/bin/env node
/**
 * 一次性脚本：去每条 news.json item 的 URL 拿真实发布日期。
 *
 * 之前 news.json 里的 date 字段可能来自 discoveredAt fallback 或 bulk
 * RSS 解析时的伪日期。本脚本用 Playwright 打开每个 URL，按以下顺序提取
 * 真实发布日期：
 *   1. <meta property="article:published_time">
 *   2. JSON-LD datePublished
 *   3. <meta name="dc.date.issued"> / dcterms.created
 *   4. <time datetime="...">
 *   5. <meta name="publishdate"> / pubdate
 *
 * 验证规则：拿到的日期若与当前记录差 > 2 天，认为是真实日期，覆盖；
 * 若差 < 2 天，认为当前可信不动；若拿不到，留原值，记一个 unknown flag。
 *
 * Concurrency 6（友好但不至于太慢）；timeout 20s/page。
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");
const NEWS = path.join(projectRoot, "src/data/news.json");
const BACKUP = path.join(projectRoot, "src/data/news.before-date-verify.json");

const CONCURRENCY = parseInt(process.env.CONCURRENCY ?? "6", 10);
const TIMEOUT_MS = 20_000;
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";

let _browser = null;
async function getBrowser() {
  if (_browser) return _browser;
  const { chromium } = await import("playwright");
  _browser = await chromium.launch({ headless: true });
  return _browser;
}

async function extractDate(page) {
  return page.evaluate(() => {
    // 1) Open Graph article:published_time
    const og = document
      .querySelector('meta[property="article:published_time"]')
      ?.getAttribute("content");
    if (og && !Number.isNaN(Date.parse(og))) return og;

    // 2) JSON-LD datePublished
    const lds = document.querySelectorAll('script[type="application/ld+json"]');
    for (const ld of lds) {
      try {
        const data = JSON.parse(ld.textContent || "null");
        const candidates = Array.isArray(data) ? data : [data];
        for (const c of candidates) {
          if (c?.datePublished && !Number.isNaN(Date.parse(c.datePublished))) {
            return c.datePublished;
          }
          if (c?.["@graph"]) {
            for (const g of c["@graph"]) {
              if (g?.datePublished && !Number.isNaN(Date.parse(g.datePublished))) {
                return g.datePublished;
              }
            }
          }
        }
      } catch {}
    }

    // 3) DC / DC Terms meta
    const dc = document
      .querySelector(
        'meta[name="dc.date.issued"], meta[name="dcterms.created"], meta[name="DC.date.issued"]',
      )
      ?.getAttribute("content");
    if (dc && !Number.isNaN(Date.parse(dc))) return dc;

    // 4) <time datetime="...">
    const t = document.querySelector("time[datetime]")?.getAttribute("datetime");
    if (t && !Number.isNaN(Date.parse(t))) return t;

    // 5) Other common metas
    const other = document
      .querySelector(
        'meta[name="publishdate"], meta[name="pubdate"], meta[property="og:updated_time"]',
      )
      ?.getAttribute("content");
    if (other && !Number.isNaN(Date.parse(other))) return other;

    return null;
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchOne(item) {
  const browser = await getBrowser();
  const ctx = await browser.newContext({ userAgent: UA });
  const page = await ctx.newPage();
  try {
    await page.goto(item.url, { waitUntil: "domcontentloaded", timeout: TIMEOUT_MS });
    const found = await Promise.race([
      extractDate(page),
      sleep(8000).then(() => null), // 给页面 8s 渲染时间，免得 JSON-LD 是 lazy 注入
    ]);
    return found;
  } catch (e) {
    return { err: String(e).slice(0, 120) };
  } finally {
    await ctx.close().catch(() => {});
  }
}

async function pool(items, n, work) {
  const queue = items.slice();
  const inflight = new Set();
  const results = new Map();
  let done = 0;
  async function next() {
    const job = queue.shift();
    if (!job) return;
    const p = (async () => {
      try {
        const r = await work(job);
        results.set(job.url, r);
      } catch (e) {
        results.set(job.url, { err: String(e).slice(0, 120) });
      } finally {
        done++;
        if (done % 50 === 0 || done === items.length) {
          process.stderr.write(`  progress: ${done}/${items.length}\n`);
        }
      }
    })();
    inflight.add(p);
    p.finally(() => inflight.delete(p));
    await p;
    return next();
  }
  await Promise.all(Array.from({ length: n }, () => next()));
  return results;
}

async function main() {
  const raw = await fs.readFile(NEWS, "utf8");
  const items = JSON.parse(raw);
  await fs.writeFile(BACKUP, raw); // 备份
  console.error(`Loaded ${items.length} items, backup written to ${path.relative(projectRoot, BACKUP)}`);

  const results = await pool(items, CONCURRENCY, fetchOne);

  let updated = 0,
    unchanged = 0,
    failed = 0,
    confirmed = 0;

  const TWO_DAYS = 2 * 24 * 3600 * 1000;
  const newItems = items.map((it) => {
    const r = results.get(it.url);
    if (!r || typeof r === "object") {
      failed++;
      return it;
    }
    const realDate = String(r);
    const curIso = it.date;
    if (!curIso) {
      updated++;
      return { ...it, date: realDate };
    }
    const curMs = new Date(curIso).getTime();
    const realMs = new Date(realDate).getTime();
    if (Math.abs(curMs - realMs) > TWO_DAYS) {
      updated++;
      return { ...it, date: realDate };
    } else {
      confirmed++;
      return it;
    }
  });

  console.error(`\n=== 完成 ===`);
  console.error(`总: ${items.length}`);
  console.error(`日期被覆盖 (差 >2d): ${updated}`);
  console.error(`日期被验证 (差 ≤2d): ${confirmed}`);
  console.error(`Failed (timeout/404/etc): ${failed}`);
  console.error(`未变 (current==null + no fetch): ${unchanged}`);

  await fs.writeFile(NEWS, JSON.stringify(newItems, null, 2));
  console.error(`✓ 写回 ${path.relative(projectRoot, NEWS)}`);

  if (_browser) await _browser.close().catch(() => {});
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
