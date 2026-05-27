#!/usr/bin/env node
/**
 * Lab feed extractor.
 *
 * Reads content/feed-sources.yml and produces src/data/generated/feed-raw.json.
 * Three fetcher types are supported on the "list page" entry:
 *
 *   rss      — RSS / Atom feed, parsed by fast-xml-parser
 *   html     — SSR HTML page, parsed by JSDOM-free regex against
 *              `selector.item` anchors. Robust enough for Anthropic.
 *   browser  — Playwright chromium headless; needed for sites that
 *              block UA-based curl (Cloudflare) or render on the client.
 *
 * Each source can ALSO declare an `archive:` block that walks the lab's
 * full history beyond what the list page surfaces. Supported modes:
 *
 *   sitemap         — fetch one or more sitemap.xml documents, filter
 *                     URLs against `url_pattern`, optionally keyword-filter
 *                     for blogs that mix AI with unrelated content
 *   pagination      — html or browser pagination via `template` with {n}
 *                     placeholder; either parse anchor_pattern from HTML
 *                     or use playwright on each page
 *   browser-scroll  — single playwright session, scroll the list page until
 *                     no new items appear for `idle_scrolls` rounds or
 *                     `max_scrolls` total
 *
 * Archive items only carry url + a list-page title (from the sitemap is
 * rarely informative — usually just the slug). The score-and-tag pass and
 * enrich-feed-dates / fetch-og-images steps fill in real titles, dates,
 * and summaries.
 *
 * Each source's output is appended to the same flat list, normalized to
 *
 *   {
 *     source: "openai",                // matches feed-sources.yml id
 *     sourceName: "OpenAI",
 *     id: <stable hash of url>,
 *     title: "...",
 *     url: "https://openai.com/...",
 *     summary: "..." | "",
 *     category: "Product" | "" | null, // optional, source-supplied tag
 *     publishedAt: ISO8601 | null,
 *     discoveredAt: ISO8601,
 *   }
 *
 * Stable IDs let downstream scoring skip already-scored items.
 *
 * Env:
 *   - SKIP_BROWSER=1     skip playwright sources (CI / dev convenience)
 *   - FEED_LIMIT=N       keep at most N items per source from the LIST PAGE
 *                        (default 30; archive walks have their own cap)
 *   - SKIP_ARCHIVE=1     skip the archive walks (fast path for dev iteration)
 *   - ARCHIVE_ONLY=src1,src2  only run archive walks for matching ids
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";
import { XMLParser } from "fast-xml-parser";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..", "..");

const SOURCES_FILE = path.join(projectRoot, "content", "news", "feed-sources.yml");
const OUT_FILE = path.join(
  projectRoot,
  "src",
  "data",
  "generated",
  "feed-raw.json",
);
const FEED_LIMIT = parseInt(process.env.FEED_LIMIT ?? "30", 10);
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";

function stableId(url) {
  return crypto.createHash("sha1").update(url).digest("hex").slice(0, 16);
}

function normalizeISO(input) {
  if (!input) return null;
  if (input instanceof Date) return input.toISOString();
  const s = String(input).trim();
  if (!s) return null;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function trim(text, max = 300) {
  if (!text) return "";
  const clean = String(text).replace(/\s+/g, " ").trim();
  return clean.length > max ? clean.slice(0, max - 1) + "…" : clean;
}

// ---------- RSS / Atom -----------------------------------------------------

const xmlParser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: "@",
  trimValues: true,
});

async function fetchWithRetry(url, init, tries = 3) {
  let lastErr;
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, init);
      if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
      return res;
    } catch (err) {
      lastErr = err;
      // node undici occasionally drops TLS on first connect; back off and retry.
      await new Promise((r) => setTimeout(r, 600 * (i + 1)));
    }
  }
  throw lastErr;
}

async function fetchRss(source) {
  const res = await fetchWithRetry(source.url, { headers: { "User-Agent": UA } });
  const xml = await res.text();
  const doc = xmlParser.parse(xml);
  // RSS 2.0: rss.channel.item[]
  // Atom:    feed.entry[]
  let entries = [];
  if (doc.rss?.channel?.item) {
    entries = Array.isArray(doc.rss.channel.item)
      ? doc.rss.channel.item
      : [doc.rss.channel.item];
    return entries.map((e) => ({
      title: trim(e.title?.["#text"] ?? e.title, 200),
      url: e.link?.["#text"] ?? e.link ?? "",
      summary: trim(
        stripHtml(e.description?.["#text"] ?? e.description ?? ""),
        300,
      ),
      category: pickCategory(e.category),
      publishedAt: normalizeISO(e.pubDate ?? e["dc:date"]),
    }));
  }
  if (doc.feed?.entry) {
    entries = Array.isArray(doc.feed.entry)
      ? doc.feed.entry
      : [doc.feed.entry];
    return entries.map((e) => {
      const link = Array.isArray(e.link)
        ? e.link.find((l) => l["@rel"] !== "self") ?? e.link[0]
        : e.link;
      const href = link?.["@href"] ?? link?.["#text"] ?? "";
      const summary =
        e.summary?.["#text"] ??
        e.summary ??
        e.content?.["#text"] ??
        e.content ??
        "";
      return {
        title: trim(e.title?.["#text"] ?? e.title, 200),
        url: href,
        summary: trim(stripHtml(summary), 300),
        category: pickCategory(e.category),
        publishedAt: normalizeISO(e.published ?? e.updated),
      };
    });
  }
  throw new Error("unrecognized feed structure");
}

function stripHtml(s) {
  if (!s) return "";
  return String(s).replace(/<[^>]+>/g, " ");
}

function pickCategory(c) {
  if (!c) return null;
  if (typeof c === "string") return trim(c, 60);
  if (Array.isArray(c)) return pickCategory(c[0]);
  return trim(c["@term"] ?? c["#text"] ?? "", 60) || null;
}

// ---------- HTML (SSR static) ----------------------------------------------
//
// We do not pull in jsdom for one site. Anthropic's news index has a
// predictable shape:
//
//   <a href="/news/..." class="...content"><h2>title</h2>
//     <div><span class="caption bold">Product</span>
//          <time class="...date...">Apr 16, 2026</time></div>
//     <p class="body-3 serif ...body">summary</p>
//   </a>
//
// Regex on the anchor block is enough and keeps the dependency surface tiny.

async function fetchHtml(source) {
  const res = await fetchWithRetry(source.url, { headers: { "User-Agent": UA } });
  const html = await res.text();
  // Find <a href="<pathPrefix>..."> ... </a> blocks. pathPrefix comes from
  // selector.item like `a[href^="/news/"]` → `/news/`. Defaults to `/news/`
  // for backward compatibility with the original Anthropic-only design.
  // Layout variants observed on anthropic.com:
  //   - FeaturedGrid: title in <h2>, summary in <p>, category in
  //     <span class="caption bold">
  //   - PublicationList: title in <span class="...title body-3">, category
  //     in <span class="...subject body-3">, no summary
  // Both have <time class="...date...">.
  const selItem = source.selector?.item || 'a[href^="/news/"]';
  const prefixMatch = selItem.match(/href\^="([^"]+)"/);
  const pathPrefix = prefixMatch ? prefixMatch[1] : "/news/";
  const escapedPrefix = pathPrefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const anchorRe = new RegExp(
    `<a[^>]+href="(${escapedPrefix}[^"#?]+)"[^>]*>([\\s\\S]*?)</a>`,
    "g",
  );
  const seen = new Set();
  const out = [];
  let m;
  while ((m = anchorRe.exec(html))) {
    const slug = m[1];
    if (seen.has(slug)) continue;
    seen.add(slug);
    const inner = m[2];
    let title = trim(
      stripHtml((inner.match(/<h[1-3][^>]*>([\s\S]*?)<\/h[1-3]>/) ?? [, ""])[1]),
      200,
    );
    if (!title) {
      title = trim(
        stripHtml(
          (inner.match(/<span[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)<\/span>/) ?? [, ""])[1],
        ),
        200,
      );
    }
    const summary = trim(
      stripHtml((inner.match(/<p[^>]*>([\s\S]*?)<\/p>/) ?? [, ""])[1]),
      300,
    );
    const timeMatch = inner.match(/<time[^>]*>([\s\S]*?)<\/time>/);
    const dateText = timeMatch ? stripHtml(timeMatch[1]).trim() : "";
    let category = trim(
      stripHtml(
        (inner.match(/<span[^>]*class="[^"]*caption[^"]*"[^>]*>([\s\S]*?)<\/span>/) ?? [, ""])[1],
      ),
      60,
    );
    if (!category) {
      category = trim(
        stripHtml(
          (inner.match(/<span[^>]*class="[^"]*subject[^"]*"[^>]*>([\s\S]*?)<\/span>/) ?? [, ""])[1],
        ),
        60,
      );
    }
    if (!title) continue;
    out.push({
      title,
      url: source.detailBase + slug,
      summary,
      category: category || null,
      publishedAt: normalizeISO(dateText),
    });
  }
  return out;
}

// ---------- Browser (Playwright chromium) ----------------------------------

let _browser = null;
async function getBrowser() {
  if (_browser) return _browser;
  const { chromium } = await import("playwright");
  _browser = await chromium.launch({ headless: true });
  return _browser;
}

async function fetchBrowser(source) {
  const browser = await getBrowser();
  const ctx = await browser.newContext({ userAgent: UA });
  const page = await ctx.newPage();
  try {
    // networkidle is too strict for SPA sites that keep long-poll
    // connections open. domcontentloaded + small settle window is enough
    // once selectors are present.
    await page.goto(source.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    try {
      await page.waitForSelector(source.selector.item, { timeout: 15000 });
    } catch {
      // proceed even if selector doesn't appear — eval will return [].
    }
    await page.waitForTimeout(2000);
    const items = await page.$$eval(
      source.selector.item,
      (els, sel) => {
        // Group anchors by href first — grid layouts produce multiple
        // anchors per article (image, badge, title). Pick the one with
        // the most informative text per href.
        const byHref = new Map();
        for (const el of els) {
          const href = el.getAttribute("href");
          if (!href) continue;
          const key = href.replace(/[?#].*$/, "");
          if (!byHref.has(key)) byHref.set(key, []);
          byHref.get(key).push(el);
        }
        const BADGE_RE = /^(FEATURED|NEW|Featured|New|Read more|Learn more)\.?\s*$/i;
        const out = [];
        for (const [key, group] of byHref) {
          // Title resolution prefers structured selector hits across the
          // whole group (h-tags), and only falls back to anchor text when
          // none of them landed. This keeps mistral's <h1> tidy while
          // letting xai (text-only anchors) still resolve.
          let title = "";
          let bestEl = group[0];
          for (const el of group) {
            const t = (el.querySelector(sel.title)?.textContent ?? "")
              .replace(/\s+/g, " ").trim();
            if (!t || BADGE_RE.test(t)) continue;
            const clean = t.replace(/^(FEATURED|NEW|Featured|New)\s+/, "");
            if (clean.length > title.length) {
              title = clean;
              bestEl = el;
            }
          }
          if (!title) {
            for (const el of group) {
              const t = (el.textContent ?? "").replace(/\s+/g, " ").trim();
              if (!t || BADGE_RE.test(t)) continue;
              const clean = t.replace(/^(FEATURED|NEW|Featured|New)\s+/, "").slice(0, 220);
              if (clean.length > title.length) {
                title = clean;
                bestEl = el;
              }
            }
          }
          if (!title || title.length < 4) continue;
          // Date / summary / category pull from whichever anchor in the group
          // has them — try bestEl first, then any other.
          const text = (el, q) =>
            (el.querySelector(q)?.textContent ?? "").replace(/\s+/g, " ").trim();
          let dateText = "";
          let summary = "";
          let category = "";
          for (const el of [bestEl, ...group]) {
            if (!dateText) dateText = text(el, "time");
            if (!dateText && sel.timeText) {
              for (const c of el.querySelectorAll(sel.timeText)) {
                const t = (c.textContent ?? "").trim();
                if (/[A-Z][a-z]{2}\.?\s+\d{1,2},?\s+20\d{2}/.test(t)) {
                  dateText = t;
                  break;
                }
              }
            }
            if (!summary) summary = text(el, sel.summary || "p");
            if (!category && sel.category) category = text(el, sel.category);
            if (dateText && summary && category) break;
          }
          out.push({ href: key, title: title.slice(0, 220), summary, dateText, category });
        }
        return out;
      },
      source.selector,
    );
    return items.map((it) => ({
      title: trim(it.title, 200),
      url: it.href.startsWith("http") ? it.href : source.detailBase + it.href,
      summary: trim(it.summary, 300),
      category: it.category ? trim(it.category, 60) : null,
      publishedAt: normalizeISO(it.dateText),
    }));
  } finally {
    await ctx.close();
  }
}

// ---------- Archive walks --------------------------------------------------
//
// Each lab gets one of three strategies depending on what their site
// exposes. All three return the same shape — a flat array of minimal item
// records — that the orchestrator merges into the per-source results.
//
// Archive items typically only have `url`. The title field is a slug-
// derived placeholder; the score-and-tag pass rewrites it from the
// detail page metadata anyway. publishedAt comes from sitemap <lastmod>
// when available (it tracks first-publish on most blogs), and from
// enrich-feed-dates.mjs otherwise.

function slugToTitle(url) {
  // Last path segment, kebab-case → space-separated, capitalised. Good
  // enough placeholder; score-and-tag rewrites titles anyway.
  try {
    const u = new URL(url);
    const last =
      u.pathname.split("/").filter(Boolean).pop() || u.hostname;
    const words = last
      .replace(/\.html?$/, "")
      .split("-")
      .filter((w) => w.length > 0);
    if (words.length === 0) return last;
    return words
      .map((w) => (w.length > 0 ? w[0].toUpperCase() + w.slice(1) : w))
      .join(" ");
  } catch {
    return url;
  }
}

async function fetchTextWithRetry(url, init, tries = 3) {
  const res = await fetchWithRetry(url, init, tries);
  return res.text();
}

async function expandSitemap(url, depth = 0) {
  // Returns an array of { loc, lastmod } from a sitemap. If the file is a
  // sitemap-index pointing at other sitemaps, recursively expand (one level
  // deep is enough for the labs we hit).
  const xml = await fetchTextWithRetry(url, { headers: { "User-Agent": UA } });
  const doc = xmlParser.parse(xml);
  // Sitemap index → recurse
  if (doc.sitemapindex?.sitemap) {
    const children = Array.isArray(doc.sitemapindex.sitemap)
      ? doc.sitemapindex.sitemap
      : [doc.sitemapindex.sitemap];
    if (depth >= 2) return []; // bail to avoid runaway
    const all = [];
    for (const child of children) {
      const childUrl = child.loc?.["#text"] ?? child.loc;
      if (!childUrl) continue;
      try {
        const items = await expandSitemap(childUrl, depth + 1);
        all.push(...items);
      } catch (err) {
        console.warn(`  [sitemap-child fail] ${childUrl}: ${err.message}`);
      }
    }
    return all;
  }
  // urlset → flatten
  if (doc.urlset?.url) {
    const urls = Array.isArray(doc.urlset.url) ? doc.urlset.url : [doc.urlset.url];
    return urls
      .map((u) => ({
        loc: u.loc?.["#text"] ?? u.loc,
        lastmod: u.lastmod?.["#text"] ?? u.lastmod,
      }))
      .filter((u) => u.loc);
  }
  return [];
}

async function archiveSitemap(source) {
  const cfg = source.archive;
  const sitemaps = cfg.sitemaps || (cfg.sitemap ? [cfg.sitemap] : []);
  if (sitemaps.length === 0) return [];
  const pattern = new RegExp(cfg.url_pattern);
  const kwFilter = cfg.keyword_filter ? new RegExp(cfg.keyword_filter, "i") : null;
  const max = cfg.max_items ?? 500;

  const seen = new Map();
  for (const sm of sitemaps) {
    let entries = [];
    try {
      entries = await expandSitemap(sm);
    } catch (err) {
      console.warn(`  [sitemap fail] ${sm}: ${err.message}`);
      continue;
    }
    for (const e of entries) {
      if (!e.loc || !pattern.test(e.loc)) continue;
      if (kwFilter && !kwFilter.test(e.loc)) continue;
      if (seen.has(e.loc)) continue;
      seen.set(e.loc, {
        url: e.loc,
        publishedAt: normalizeISO(e.lastmod),
      });
    }
  }
  // Sort by publishedAt desc so the most recent items get kept under cap.
  const all = [...seen.values()].sort((a, b) => {
    const ad = a.publishedAt ? Date.parse(a.publishedAt) : 0;
    const bd = b.publishedAt ? Date.parse(b.publishedAt) : 0;
    return bd - ad;
  });
  return all.slice(0, max).map((it) => ({
    title: slugToTitle(it.url),
    url: it.url,
    summary: "",
    category: null,
    publishedAt: it.publishedAt,
  }));
}

async function archiveHtmlPagination(source) {
  const cfg = source.archive;
  const template = cfg.template;
  const start = cfg.start ?? 1;
  const maxPages = cfg.max_pages ?? 50;
  const max = cfg.max_items ?? 500;
  const anchorPattern = new RegExp(cfg.anchor_pattern, "g");

  const seen = new Set();
  const out = [];
  let consecutiveEmpty = 0;
  for (let n = start; n < start + maxPages; n++) {
    const pageUrl = template.replace("{n}", String(n));
    let html;
    try {
      html = await fetchTextWithRetry(
        pageUrl,
        { headers: { "User-Agent": UA } },
        2,
      );
    } catch (err) {
      console.warn(`  [pagination ${n} fail] ${err.message}`);
      consecutiveEmpty++;
      if (consecutiveEmpty >= 3) break;
      continue;
    }
    anchorPattern.lastIndex = 0;
    let pageHits = 0;
    let m;
    while ((m = anchorPattern.exec(html))) {
      const url = m[1].replace(/[?#].*$/, "");
      if (seen.has(url)) continue;
      seen.add(url);
      out.push({
        title: slugToTitle(url),
        url,
        summary: "",
        category: null,
        publishedAt: null,
      });
      pageHits++;
      if (out.length >= max) break;
    }
    if (out.length >= max) break;
    if (pageHits === 0) {
      consecutiveEmpty++;
      if (consecutiveEmpty >= 3) break;
    } else {
      consecutiveEmpty = 0;
    }
    // Pace requests
    await new Promise((r) => setTimeout(r, 250));
  }
  return out.slice(0, max);
}

async function archiveBrowserPagination(source) {
  // Like archiveHtmlPagination but driven by playwright so sites that
  // reject node fetch (Meta AI returns 400 to node's TLS fingerprint)
  // still get crawled. Some sites (ai.meta.com) hydrate the same SPA
  // grid regardless of ?page=N, so pagination only works when JS is
  // disabled and a fresh context is used per request — that's the
  // default here.
  const cfg = source.archive;
  const template = cfg.template;
  const start = cfg.start ?? 1;
  const maxPages = cfg.max_pages ?? 50;
  const max = cfg.max_items ?? 500;
  const anchorSel = cfg.anchor_selector ?? source.selector?.item;
  if (!anchorSel) {
    throw new Error("browser-pagination requires anchor_selector or selector.item");
  }
  // Default JS=disabled for this strategy. Sites that paginate via query
  // string usually have full SSR; enabling JS lets the SPA hydrate over
  // the SSR HTML and clobber the per-page content (Meta AI does this).
  const jsEnabled = cfg.js === true;
  // Default new-context-per-page=true. Reusing a single context can leak
  // SPA state across navigations on aggressive client-side routers.
  const newContextPerPage = cfg.new_context_per_page !== false;

  const browser = await getBrowser();
  const seen = new Set();
  const out = [];
  let consecutiveEmpty = 0;
  let ctx = null;
  let page = null;
  if (!newContextPerPage) {
    ctx = await browser.newContext({ userAgent: UA, javaScriptEnabled: jsEnabled });
    page = await ctx.newPage();
  }
  try {
    for (let n = start; n < start + maxPages && out.length < max; n++) {
      const pageUrl = template.replace("{n}", String(n));
      let localCtx = null;
      let activePage = page;
      try {
        if (newContextPerPage) {
          localCtx = await browser.newContext({
            userAgent: UA,
            javaScriptEnabled: jsEnabled,
          });
          activePage = await localCtx.newPage();
        }
        await activePage.goto(pageUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
        if (jsEnabled) {
          try {
            await activePage.waitForSelector(anchorSel, { timeout: 8000 });
          } catch {
            /* selector may not appear on empty pages */
          }
          await activePage.waitForTimeout(800);
        }
        const hrefs = await activePage.$$eval(anchorSel, (els) =>
          els.map((el) => el.getAttribute("href")).filter(Boolean),
        );
        if (process.env.DEBUG_FEED === "1") {
          console.log(
            `    [browser-pagination ${source.id} p${n}] ${hrefs.length} hrefs (js=${jsEnabled})`,
          );
        }
        let pageHits = 0;
        const urlFilter = cfg.url_pattern ? new RegExp(cfg.url_pattern) : null;
        for (const h of hrefs) {
          const cleaned = h.replace(/[?#].*$/, "");
          if (!cleaned) continue;
          const abs = cleaned.startsWith("http")
            ? cleaned
            : (source.detailBase ?? "") + cleaned;
          if (urlFilter && !urlFilter.test(abs)) continue;
          if (seen.has(abs)) continue;
          seen.add(abs);
          out.push({
            title: slugToTitle(abs),
            url: abs,
            summary: "",
            category: null,
            publishedAt: null,
          });
          pageHits++;
          if (out.length >= max) break;
        }
        if (pageHits === 0) {
          consecutiveEmpty++;
          if (consecutiveEmpty >= 3) break;
        } else {
          consecutiveEmpty = 0;
        }
      } catch (err) {
        console.warn(`  [browser-pagination ${n} fail] ${err.message}`);
        consecutiveEmpty++;
        if (consecutiveEmpty >= 3) break;
      } finally {
        if (localCtx) await localCtx.close();
      }
    }
  } finally {
    if (ctx) await ctx.close();
  }
  return out.slice(0, max);
}

async function archiveBrowserScroll(source) {
  const cfg = source.archive;
  const maxScrolls = cfg.max_scrolls ?? 80;
  const idleScrolls = cfg.idle_scrolls ?? 5;
  const max = cfg.max_items ?? 300;

  const browser = await getBrowser();
  const ctx = await browser.newContext({ userAgent: UA });
  const page = await ctx.newPage();
  const seen = new Set();
  const out = [];
  try {
    await page.goto(source.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    try {
      await page.waitForSelector(source.selector.item, { timeout: 15000 });
    } catch {
      /* proceed, maybe selector lazy */
    }
    await page.waitForTimeout(1500);

    let idle = 0;
    for (let i = 0; i < maxScrolls && out.length < max && idle < idleScrolls; i++) {
      const before = out.length;
      const items = await page.$$eval(source.selector.item, (els) =>
        els
          .map((el) => el.getAttribute("href"))
          .filter(Boolean)
          .map((h) => h.replace(/[?#].*$/, "")),
      );
      for (const href of items) {
        const abs = href.startsWith("http") ? href : source.detailBase + href;
        if (seen.has(abs)) continue;
        seen.add(abs);
        out.push({
          title: slugToTitle(abs),
          url: abs,
          summary: "",
          category: null,
          publishedAt: null,
        });
        if (out.length >= max) break;
      }
      if (out.length === before) idle++;
      else idle = 0;
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(1500);
    }
  } finally {
    await ctx.close();
  }
  return out.slice(0, max);
}

async function runArchive(source) {
  const mode = source.archive?.mode;
  if (!mode) return [];
  if (mode === "sitemap") return archiveSitemap(source);
  if (mode === "pagination") {
    const strat = source.archive.strategy ?? "html-pagination";
    if (strat === "html-pagination") return archiveHtmlPagination(source);
    if (strat === "browser-pagination") return archiveBrowserPagination(source);
    throw new Error(`unknown pagination strategy: ${strat}`);
  }
  if (mode === "browser-scroll") return archiveBrowserScroll(source);
  throw new Error(`unknown archive mode: ${mode}`);
}

// ---------- Orchestration --------------------------------------------------

async function run() {
  const cfg = yaml.load(await fs.readFile(SOURCES_FILE, "utf8"));
  const sources = (cfg.sources ?? []).filter((s) => s.enabled !== false);

  const now = new Date().toISOString();
  const results = [];
  const stats = [];

  // Archive scoping: ARCHIVE_ONLY=src1,src2 limits archive walks to those
  // sources (the list-page fetches still run for everyone). Useful when
  // iterating on a single lab.
  const archiveOnlySet = process.env.ARCHIVE_ONLY
    ? new Set(process.env.ARCHIVE_ONLY.split(",").map((s) => s.trim()))
    : null;
  const skipArchive = process.env.SKIP_ARCHIVE === "1";

  for (const source of sources) {
    if (process.env.SKIP_BROWSER === "1" && source.type === "browser") {
      stats.push(`  ${source.id.padEnd(12)} skipped (SKIP_BROWSER=1)`);
      continue;
    }
    const t0 = Date.now();
    // Track per-source unique URLs so the archive walk can't double-add an
    // item already pulled by the live list page.
    const seenUrlsForSource = new Set();
    let listCount = 0;
    let archiveAdded = 0;
    let archiveAvailable = 0;
    try {
      let raw;
      if (source.type === "rss") raw = await fetchRss(source);
      else if (source.type === "html") raw = await fetchHtml(source);
      else if (source.type === "browser") raw = await fetchBrowser(source);
      else throw new Error(`unknown type: ${source.type}`);

      raw = raw.filter((r) => r.url && r.title).slice(0, FEED_LIMIT);
      for (const r of raw) {
        if (seenUrlsForSource.has(r.url)) continue;
        seenUrlsForSource.add(r.url);
        results.push({
          source: source.id,
          sourceName: source.name,
          id: stableId(r.url),
          title: r.title,
          url: r.url,
          summary: r.summary ?? "",
          category: r.category ?? null,
          publishedAt: r.publishedAt,
          discoveredAt: now,
        });
        listCount++;
      }
    } catch (err) {
      stats.push(`  ${source.id.padEnd(12)} list FAILED  ${err.message}`);
    }

    // Archive walk — separate try block so a sitemap timeout doesn't
    // throw away the list-page items we already collected.
    if (
      !skipArchive &&
      source.archive &&
      (archiveOnlySet === null || archiveOnlySet.has(source.id))
    ) {
      // Browser-driven archives reuse the playwright session, so we only
      // honour SKIP_BROWSER for them. Sitemap/html-pagination work over
      // plain fetch and are always run.
      const isBrowserMode =
        source.archive.mode === "browser-scroll" ||
        (source.archive.mode === "pagination" &&
          source.archive.strategy === "browser-pagination");
      if (isBrowserMode && process.env.SKIP_BROWSER === "1") {
        stats.push(
          `  ${source.id.padEnd(12)} list=${listCount} archive=skipped (SKIP_BROWSER=1)`,
        );
        continue;
      }
      try {
        const archive = await runArchive(source);
        if (process.env.DEBUG_FEED === "1") {
          console.log(`    [archive ${source.id}] runArchive returned ${archive.length} items`);
        }
        archiveAvailable = archive.length;
        for (const a of archive) {
          if (seenUrlsForSource.has(a.url)) continue;
          seenUrlsForSource.add(a.url);
          results.push({
            source: source.id,
            sourceName: source.name,
            id: stableId(a.url),
            title: a.title,
            url: a.url,
            summary: a.summary ?? "",
            category: a.category ?? null,
            publishedAt: a.publishedAt,
            discoveredAt: now,
          });
          archiveAdded++;
        }
      } catch (err) {
        stats.push(
          `  ${source.id.padEnd(12)} archive FAILED  ${err.message}`,
        );
      }
    }

    const capHint =
      source.archive?.max_items &&
      archiveAvailable >= source.archive.max_items
        ? ` [cap=${source.archive.max_items}]`
        : "";
    stats.push(
      `  ${source.id.padEnd(12)} list=${String(listCount).padStart(3)} ` +
        `archive=${String(archiveAdded).padStart(4)}` +
        `${capHint} (${Date.now() - t0}ms)`,
    );
  }

  if (_browser) await _browser.close();

  // Sort by published date desc (null pubs go to bottom).
  results.sort((a, b) => {
    if (!a.publishedAt && !b.publishedAt) return 0;
    if (!a.publishedAt) return 1;
    if (!b.publishedAt) return -1;
    return Date.parse(b.publishedAt) - Date.parse(a.publishedAt);
  });

  await fs.mkdir(path.dirname(OUT_FILE), { recursive: true });
  await fs.writeFile(
    OUT_FILE,
    JSON.stringify({ fetchedAt: now, items: results }, null, 2),
  );

  console.log("feed extract:");
  for (const line of stats) console.log(line);
  console.log(`  total: ${results.length} items -> ${path.relative(projectRoot, OUT_FILE)}`);
}

run().catch((err) => {
  console.error("feed extract failed:", err);
  process.exit(1);
});
