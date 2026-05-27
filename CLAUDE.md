# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo Origin & Project Intent

This repo is a fork of [maggieappleton-com-v3](https://github.com/MaggieAppleton/maggie-appleton-v3) (Maggie Appleton's personal digital garden, Astro 5 + MDX). The owner is rebranding it into **their own personal site**.

The cardinal rule for all edits:

> **Content changes. Style, structure, and visual aesthetic do not.**

When adding features, refactoring, or replacing content, you MUST first look at how existing pages, components, and content collections are built and follow that pattern. Do NOT invent new layout primitives, design tokens, font families, color variables, card styles, or page archetypes. Reuse what exists; if something genuinely new is needed, extend the existing system rather than create a parallel one.

## Common Commands

```bash
npm run dev           # Dev server (regenerates links + topics first, then astro dev)
npm run build         # Production build (links + topics + webmentions + astro build)
npm run build:local   # Production build WITHOUT fetching webmentions (offline-safe)
npm run preview       # Preview the production build
./deploy.sh           # git push → npm run build → vercel --prod

npm run generate-links     # Rebuild src/links.json from MDX frontmatter + [[wiki links]]
npm run fetch-webmentions  # Refresh webmention cache (needs WEBMENTION_IO_TOKEN env)
npm run smidgeon          # Interactive scaffolder for a new smidgeon post
npm run date              # Print current date in "Month DD, YYYY" form
```

There is no test suite, no linter command, and no typecheck command. Astro's content collections and `tsconfig` (strict) provide the only static checking, surfaced at dev/build time.

## Architecture

### Rendering Model

Astro static site generator. Pages are `.astro` files under `src/pages/`. The site uses Astro's `ClientRouter` (View Transitions) — be aware that client-side scripts inside MDX can break across navigations if they assume a full page load. See `src/utils/viewTransitionLifecycle.ts` for the helper that handles this.

React is loaded via `@astrojs/react` but used sparingly; the default for any new component is a `.astro` file. Add React only when you need state/effects that don't fit Astro's island model.

### Content System

All long-form content lives in `src/content/` and is registered as typed Astro collections in `src/content/config.ts`:

| Collection   | Format    | Notes                                                          |
| ------------ | --------- | -------------------------------------------------------------- |
| `essays`     | MDX       | Longform, has `cover` image, `featured` flag for homepage      |
| `notes`      | MDX       | Loose notes, no cover                                          |
| `patterns`   | MDX       | Design pattern catalogue                                       |
| `talks`      | MDX       | Has `conferences[]` array                                      |
| `smidgeons`  | MDX       | Stream of links; uses its own `SmidgeonLayout`                 |
| `now`        | MDX       | Status updates                                                 |
| `podcasts`   | JSON      | `src/content/podcasts.json`                                    |
| `books`      | JSON      | `src/content/books.json`                                       |
| `antibooks`  | JSON      | `src/content/antibooks.json`                                   |
| `pages`      | MDX       | Static pages (e.g. `colophon-content.mdx`)                     |

All MDX collections share `growthStage` (`seedling` / `budding` / `evergreen`) and `topics[]`. To add a new field, update both `config.ts` (Zod schema) and any consumer (cards, layouts). To add a new collection, follow the same shape and register it in the `collections` export at the bottom of `config.ts`.

### Routing

Routes are file-based plus one dynamic catch-all:

- `src/pages/[...slug].astro` — single entry point for **every** essay, note, pattern, talk, and smidgeon. It branches on `entry.type` (smidgeon vs. everything else) to pick between `SmidgeonLayout` and `PostLayout`.
- `src/pages/topics/[topic].astro` — per-topic landing pages.
- `src/pages/og/[...slug].png.ts` — Satori + Sharp render dynamic OG images per content ID. `Layout.astro` constructs the OG URL from the canonical pathname.
- `src/pages/og.png.ts` — Default OG image for non-content pages, with query-param overrides.
- `src/pages/rss.xml.js`, `src/pages/smidgeons.xml.js` — RSS feeds.

When you add a new content type, prefer extending `[...slug].astro` over creating a parallel dynamic route.

### Layout Chain

`Layout.astro` (global head/nav/footer/SEO/OG) → `PostLayout.astro` or `SmidgeonLayout.astro` (post chrome — title, dates, growth indicator, backlinks, webmentions, TOC) → `ProseWrapper.astro` (typographic container for MDX). MDX components are mapped in `[...slug].astro`'s `components` object — adding a new MDX component means registering it there.

### Wiki Links and Backlinks

`[[Internal Link]]` syntax in MDX is resolved at build time by `src/plugins/remark-wiki-link.js`, which looks up `src/links.json`. `links.json` is regenerated by `src/scripts/generate-links.js` from MDX frontmatter (titles + `aliases[]`) and from the bracket references inside each file. This script MUST run before `astro dev` / `astro build` — both scripts in `package.json` already chain it.

Backlinks for a post are computed in `src/components/layouts/Backlinks.astro` using the same `links.json`.

A wiki link that doesn't resolve becomes plain text — there's no build-time error. If a `[[link]]` renders literally instead of as a link, the target slug or alias isn't in `links.json` (or hasn't been regenerated).

### Content Versioning

Versioned posts live in a folder named after the base slug, with each version as `base-slug-v1.mdx`, `base-slug-v2.mdx`, etc. The version number comes from `version:` in frontmatter. `src/utils/versionUtils.ts` owns all the logic:

- The latest version is served at `/base-slug` (canonical).
- Older versions are served at `/v1/base-slug`, `/v2/base-slug`, etc.
- `startDate` is the earliest across versions; `updated` is the latest.
- Smidgeons do NOT support versioning.

`[...slug].astro` calls `generateVersionedPaths()` to produce both canonical and versioned routes. Don't manually compute slugs — always use the helpers in `versionUtils.ts`.

### Design System

All design tokens are CSS custom properties in `src/global.css`:

- Colors: `--color-*` plus opacity variants via `color-mix`.
- Fonts:
  - Latin: `Canela Deck` (serif display), `Canela Text` (serif body), `Lato` (sans). WOFF2/WOFF files are in `public/fonts/`.
  - **CJK: `LXGW WenKai` Light (weight 300) — loaded via jsdelivr `lxgw-wenkai-webfont/lxgwwenkai-light.css` and appended to every `--font-*` fallback stack.** `body { font-synthesis: weight none; }` ensures bold/heavy weight requests still render CJK at Light (no faux-bold). **This is a hard rule: all Chinese text on this site must render as LXGW WenKai Light. Do NOT introduce another CJK font, do NOT raise the weight, do NOT remove `font-synthesis: weight none`.** Any new font stack added later must keep `"LXGW WenKai"` before the generic `serif` / `sans-serif` fallback. If you ever load a different LXGW variant (Bold, Mono, etc.) it must be a deliberate, scoped exception — never global.
- Spacing: fluid t-shirt sizes (`--space-3xs` … `--space-3xl`) plus "one-up pairs" (`--space-s-m`, etc.). All derived from a `--fluid-bp` interpolation between 320px and 1200px.
- Type scale: same fluid system.
- Radii, shadows, leading: `--border-radius-*`, `--box-shadow-*`, `--leading-*`.

When styling: **use these tokens. Do not hardcode hex, px, rem, or new font stacks.** If a needed value doesn't exist, add it to `:root` in `global.css` next to its peers, then use it.

The component vocabulary for content layout is in `src/components/layouts/` (page-level chrome) and `src/components/mdx/` (in-content primitives — `Alert`, `Footnote`, `IntroParagraph`, typography titles, etc.). Cards for each content type live in `src/components/cards/`. **Reuse before you build new.** One-off illustrative components for specific posts go in `src/components/unique/`.

### Pre-build Scripts

`src/scripts/`:

- `generate-links.js` — Builds `src/links.json` (frontmatter + alias index for wiki links). Runs before dev and build.
- `generate-topics.ts` — Scans MDX frontmatter and prints a topic count (the schema generation is implicit via Astro content collections). Runs before dev and build.
- `get-webmentions.js` — Fetches from webmention.io into a local cache. Only runs in `npm run build`, not in `npm run dev` or `npm run build:local`. Requires `WEBMENTION_IO_TOKEN`.
- `create-smidgeon.js` (in repo root `scripts/`) — Interactive prompt to scaffold a new smidgeon MDX file.

If editing any of these, remember they're invoked from the `npm` script chain in `package.json` — don't change their CLI surface without updating that.

### External Services

- **Vercel** — Hosting + headers/CSP defined in `vercel.json`. Watch the CSP if you add a new embed source (Twitter, YouTube, Vimeo, Figma, Transistor are already allowlisted).
- **webmention.io + brid.gy** — Social interactions. Domain is currently hardcoded to `maggieappleton.com` in `src/scripts/get-webmentions.js` and `src/components/layouts/WebMentions.astro` — **this is one of the identity strings you must change** (see checklist below).
- **Cloudinary** — Many images in existing essays reference `res.cloudinary.com`. Allowed via `astro.config.mjs` `image.domains`.
- **Cloudflare R2** — Video hosting at `media.maggieappleton.com`. See README for upload commands. If you rebrand to your own R2 bucket, update `<link rel="preconnect">` in `Layout.astro` and the host wherever it's referenced.

## Rebrand / Identity Replacement Checklist

When customizing the fork for the new owner, these are the places where Maggie's identity is hardcoded outside of `src/content/`. Search-replace alone is risky (the strings appear in MDX content too); do these by hand:

1. **`src/layouts/Layout.astro`** — site title, default description, RSS title, webmention/pingback URLs, `rel="me"` link, Twitter creator handle, OG image alt, `preconnect` host, Google site verification meta.
2. **`astro.config.mjs`** — `site:` URL and `image.domains` if you stop using Cloudinary.
3. **`src/components/layouts/Footer.astro`** — social links, copyright name.
4. **`src/components/layouts/navbar/`** — site name in the navbar.
5. **`src/pages/index.astro`** — homepage hero copy ("Maggie makes visual essays…", current employer line).
6. **`src/pages/about.astro`, `hire-me.astro`, `colophon/`** — biographical pages.
7. **`src/pages/rss.xml.js`, `smidgeons.xml.js`** — feed titles / author.
8. **`src/pages/patterns.astro`, `podcasts.astro`, `now.astro`, `hire-me.astro`** — `<Layout title="… Maggie Appleton">` strings.
9. **`src/scripts/get-webmentions.js`** — `domain=maggieappleton.com` query string.
10. **`src/components/layouts/WebMentions.astro`** — hardcoded `maggieappleton.com` baseUrl and content sanitization regex.
11. **`vercel.json`** — `media-src` host in the CSP if you change media host.
12. **`public/manifest.json`, favicon set in `public/images/favicon/`** — PWA name, app icons.

Identity strings inside `src/content/` (essays, notes, etc.) and `src/components/unique/` (per-essay illustrations) belong to legacy posts — leave them as-is or delete the post; do not rewrite Maggie's voice as someone else's.

## Repo Conventions

- **Prettier** is configured (`.prettierrc`): trailing commas everywhere, `printWidth: 100`. MDX embedded code is left unformatted.
- **TypeScript** uses `astro/tsconfigs/strict`. Most files are `.astro` or `.js`; `.ts` exists for utilities, type-heavy logic, and content config. Don't migrate JS files to TS just because — match the file's neighbors.
- **Dates** in commits/plans/docs: run `npm run date` to get the canonical "Month DD, YYYY" string. Don't guess.
- **Astro upgrade prompt** ("New version of Astro available") appears in dev output; ignore unless explicitly asked to upgrade — version bumps can break the MDX/View Transitions setup.

## Cursor Rules Carried Forward

`.cursor/rules/` contains rules originally written for Cursor that also apply here:

- **No long-running commands.** Don't run `npm run build`, `npm run dev`, or any other dev server / build commands as part of "verification." Ask the user to run them. Reading files, grepping, package installs, and git operations are fine.
- **Delegate visual/interactive testing to the user.** You can't see hover states, animations, view transitions, or responsive breakpoints. After making UI changes, tell the user what to navigate to and what to look for, and wait for their feedback.
- **Date handling.** Always use `npm run date` for current date strings in docs/plans.
- **Substantial changes** (new page archetype, new collection, new design primitive): pause and clarify before implementing. Ask one focused question at a time about the intended UX.

## Planning Documents

`planning/` holds long-form design docs for past features (`content-versioning-system.md`, `now-posts-garden-integration.md`). When proposing a non-trivial new feature, write a similar doc in `planning/` first and align with the user before touching `src/`.
