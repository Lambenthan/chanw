#!/usr/bin/env node
/**
 * Open the detail page of every feed-raw.json item that lacks
 * publishedAt and try to extract a real publication timestamp from
 * meta tags or <time> elements. Cache results so subsequent runs
 * skip already-resolved ids.
 *
 * Affects mostly Mistral / Meta AI / xAI items whose list pages
 * don't surface dates. Without this step those items sort by
 * discoveredAt (today, every cron) and never look chronologically
 * correct.
 *
 * Output: src/data/generated/feed-dates.json (id → ISO date string).
 * extract-content.mjs merges these into the rss[] entries.
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");

const FEED_RAW = path.join(projectRoot, "src/data/generated/feed-raw.json");
const OUT = path.join(projectRoot, "src/data/generated/feed-dates.json");

const CONCURRENCY = parseInt(process.env.CONCURRENCY ?? "4", 10);
const TIMEOUT_MS = 25_000;
// Per CLAUDE.md "Operating principles (HARD)" rule 2: enrich-feed-dates
// is the codified fallback for missing publishedAt and must default to
// uncapped. CI passes MAX_NEW as a throttle to bound a single cron run;
// locally the default is Infinity so backfills happen in one go.
const MAX_NEW_PER_RUN = process.env.MAX_NEW
  ? parseInt(process.env.MAX_NEW, 10)
  : Infinity;
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
    // 1) Open Graph article:published_time (most reliable for blogs)
    const og = document
      .querySelector('meta[property="article:published_time"]')
      ?.getAttribute("content");
    if (og && !Number.isNaN(Date.parse(og))) return og;

    // 2) Twitter / Date meta
    const ld = document.querySelector('script[type="application/ld+json"]');
    if (ld) {
      try {
        const data = JSON.parse(ld.textContent || "null");
        const candidates = Array.isArray(data) ? data : [data];
        for (const d of candidates) {
          const v =
            d?.datePublished ||
            d?.uploadDate ||
            d?.dateCreated ||
            d?.publishDate;
          if (v && !Number.isNaN(Date.parse(v))) return v;
        }
      } catch {
        /* swallow malformed JSON-LD */
      }
    }

    // 3) <time datetime="..."> on the page
    const t = document.querySelector("time[datetime]");
    const dt = t?.getAttribute("datetime");
    if (dt && !Number.isNaN(Date.parse(dt))) return dt;

    // 4) <time>Mon DD, YYYY</time> visible text
    const text = t?.textContent?.trim();
    if (text) {
      const parsed = Date.parse(text);
      if (!Number.isNaN(parsed)) return new Date(parsed).toISOString();
    }

    // 5) Text date near the h1 — covers Meta AI (混淆 class)
    //    <h1>...</h1> ... <span>April 8, 2026</span>
    //    Anything else with the article-title pattern.
    const dateRe =
      /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},?\s+20\d{2}$/;
    const h1 = document.querySelector("h1");
    if (h1) {
      const scope = h1.parentElement ?? document.body;
      const cands = scope.querySelectorAll("span, p, div, time, em, i");
      for (const el of Array.from(cands)) {
        const t = el.textContent?.trim() ?? "";
        if (t.length > 30) continue; // article body, skip
        if (!dateRe.test(t)) continue;
        const parsed = Date.parse(t);
        if (!Number.isNaN(parsed)) {
          return new Date(parsed).toISOString();
        }
      }
    }

    // 6) Last resort — first standalone date string anywhere in body.
    //    Risky (could pick up an in-body example date), so only used
    //    when steps 1-5 all missed. Scope to the article container if
    //    one exists (most blog templates), otherwise body.
    const article =
      document.querySelector("article, main, [role='main']") || document.body;
    const inline = article.innerHTML?.match(
      /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},?\s+20\d{2}/,
    );
    if (inline) {
      const parsed = Date.parse(inline[0]);
      if (!Number.isNaN(parsed)) return new Date(parsed).toISOString();
    }

    return null;
  });
}

async function resolveDate(browser, item) {
  const ctx = await browser.newContext({ userAgent: UA });
  const page = await ctx.newPage();
  try {
    await page.goto(item.url, {
      waitUntil: "domcontentloaded",
      timeout: TIMEOUT_MS,
    });
    await page.waitForTimeout(700);
    return await extractDate(page);
  } catch {
    return null;
  } finally {
    await ctx.close();
  }
}

async function runPool(items, worker, concurrency) {
  const out = new Array(items.length);
  let i = 0;
  async function next() {
    while (true) {
      const idx = i++;
      if (idx >= items.length) return;
      out[idx] = await worker(items[idx], idx);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, next));
  return out;
}

async function main() {
  const raw = JSON.parse(await fs.readFile(FEED_RAW, "utf8"));
  let cache = {};
  try {
    cache = JSON.parse(await fs.readFile(OUT, "utf8"));
  } catch {
    /* first run */
  }

  const candidates = raw.items.filter(
    (it) => !it.publishedAt && !cache[it.id],
  );
  const targets = candidates.slice(0, MAX_NEW_PER_RUN);
  console.log(
    `enrich-feed-dates: ${targets.length} new candidates (cached=${Object.keys(cache).length}, raw-null=${candidates.length})`,
  );
  if (targets.length === 0) {
    console.log("nothing to do");
    return;
  }

  const browser = await getBrowser();
  let hits = 0;
  let misses = 0;
  const results = await runPool(
    targets,
    async (it, idx) => {
      const date = await resolveDate(browser, it);
      if (date) {
        hits++;
        console.log(
          `  [${String(idx + 1).padStart(2)}/${targets.length}] OK   ${date.slice(0, 10)}  ${it.sourceName.padEnd(14)} ${it.title.slice(0, 50)}`,
        );
        return [it.id, date];
      }
      misses++;
      console.log(
        `  [${String(idx + 1).padStart(2)}/${targets.length}] miss            ${it.sourceName.padEnd(14)} ${it.title.slice(0, 50)}`,
      );
      return null;
    },
    CONCURRENCY,
  );

  await browser.close();

  const out = { ...cache };
  for (const r of results) {
    if (r) out[r[0]] = r[1];
  }
  await fs.writeFile(OUT, JSON.stringify(out, null, 2));
  console.log(
    `\nsummary: ${hits} resolved, ${misses} miss | total cached: ${Object.keys(out).length}`,
  );
}

main().catch((err) => {
  console.error("enrich-feed-dates failed:", err);
  process.exit(1);
});
