#!/usr/bin/env node
/**
 * C 方案第 3 步：LLM 滤通稿。
 *
 * 对 news.json 里 AI lab 源 (OpenAI/NVIDIA/Google/DeepMind/Anthropic 等) 的
 * 条目, 批量让免费 OpenRouter 模型判断: 是"实质技术/产品/模型/研究发布"还是
 * "纯公关通告 (参加峰会/获奖/区域扩展/企业合作签约/行业调查报告/活动预告)".
 * 后者剔除. GitHub Trending / Hugging Face Blog 是开源项目本身, 非通稿, 直接保留.
 *
 * 持久化: 被判为通稿的 url 写入 src/data/news-exclude.json (黑名单),
 * convert-feed-to-news.mjs 读它排除, 保证下次 cron 不把通稿拉回来.
 *
 * env: OPENROUTER_API_KEY
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..", "..");
const NEWS = path.join(projectRoot, "src/data/news.json");
const EXCLUDE = path.join(projectRoot, "src/data/news-exclude.json");

const KEY = process.env.OPENROUTER_API_KEY;
const ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";
const BATCH = 20;

// 这些源是项目/技术内容本身, 不是通稿, 直接保留
const KEEP_SOURCES = new Set(["GitHub Trending", "Hugging Face Blog"]);

const PREFERRED = ["deepseek", "qwen", "glm", "google/gemini", "meta-llama/llama"];

async function freeModels() {
  // OR_MODEL 指定单一付费模型时直接用它，跳过免费模型轮询
  if (process.env.OR_MODEL) return [process.env.OR_MODEL];
  const res = await fetch("https://openrouter.ai/api/v1/models");
  const all = (await res.json()).data || [];
  return all
    .filter((m) => m.id?.endsWith(":free") || (m.pricing?.prompt === "0" && m.pricing?.completion === "0"))
    .map((m) => m.id)
    .sort((a, b) => {
      const ai = PREFERRED.findIndex((k) => a.toLowerCase().includes(k));
      const bi = PREFERRED.findIndex((k) => b.toLowerCase().includes(k));
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
}

const SYS = `你是 AI 行业新闻编辑。判断每条标题是"实质内容"还是"公关噪声"。
实质内容(keep=true): 新模型/产品/功能发布、技术方法、研究成果、开源项目、benchmark、重要能力更新。
公关噪声(keep=false): 参加/举办峰会展会、获奖、区域扩展(扩展到X国/上线X地区)、企业合作签约通告、行业调查报告、活动预告、招聘、纯政策声明。
只按 JSON 输出: {"results":[{"i":序号,"keep":true/false}, ...]}`;

async function judgeBatch(models, batch) {
  const list = batch.map((x, i) => `${i}. ${x.title}`).join("\n");
  const messages = [
    { role: "system", content: SYS },
    { role: "user", content: `判断这 ${batch.length} 条:\n${list}` },
  ];
  for (const model of models) {
    try {
      const res = await fetch(ENDPOINT, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${KEY}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://chanw.org",
          "X-Title": "Chanw press filter",
        },
        body: JSON.stringify({
          model,
          messages,
          temperature: 0.1,
          max_tokens: 1500,
          response_format: { type: "json_object" },
        }),
      });
      if (res.status === 429 || res.status === 402) continue;
      if (res.status !== 200) continue;
      const json = await res.json();
      const raw = json.choices?.[0]?.message?.content ?? "";
      const m = raw.match(/\{[\s\S]*\}/);
      if (!m) continue;
      const parsed = JSON.parse(m[0]);
      if (Array.isArray(parsed.results)) return parsed.results;
    } catch {
      continue;
    }
  }
  // 全失败 → 保守保留整批
  return batch.map((_, i) => ({ i, keep: true }));
}

async function main() {
  if (!KEY) throw new Error("OPENROUTER_API_KEY not set");
  // 增量: 优先判 feed-scored (cron 上游产物, 含所有候选), 本地手跑可读 news.json
  const SCORED = path.join(projectRoot, "src/data/generated/feed-scored.json");
  let pool;
  const scored = await readJsonSafe(SCORED);
  if (scored?.items) {
    pool = scored.items.map((x) => ({
      title: x.title || x.originalTitle || "",
      url: x.url,
      source: x.sourceName || x.source || "",
    }));
    console.error(`从 feed-scored 读 ${pool.length} 条候选`);
  } else {
    pool = JSON.parse(await fs.readFile(NEWS, "utf8"));
    console.error(`从 news.json 读 ${pool.length} 条候选`);
  }

  const models = await freeModels();
  // 已有黑名单 → 这些已判过为通稿, 跳过不重判
  let prevExclude = (await readJsonSafe(EXCLUDE)) ?? [];
  const excludeSet = new Set(prevExclude);

  // 增量待判: 非项目源 + 不在已有黑名单 (项目源天然保留, 已判通稿不重判)
  const toJudge = pool.filter(
    (x) => x.url && x.title && !KEEP_SOURCES.has(x.source) && !excludeSet.has(x.url),
  );
  console.error(
    `${models.length} 免费模型, 待判断(lab源 - 已判通稿): ${toJudge.length}`,
  );

  let newExcluded = 0;
  for (let b = 0; b < toJudge.length; b += BATCH) {
    const batch = toJudge.slice(b, b + BATCH);
    const verdicts = await judgeBatch(models, batch);
    const vmap = new Map(verdicts.map((v) => [v.i, v.keep]));
    batch.forEach((x, i) => {
      if (vmap.get(i) === false) { excludeSet.add(x.url); newExcluded++; }
    });
    if ((b / BATCH) % 5 === 0)
      console.error(`  批 ${b / BATCH + 1}/${Math.ceil(toJudge.length / BATCH)}, 新增剔除 ${newExcluded}`);
  }

  await fs.writeFile(EXCLUDE, JSON.stringify([...excludeSet], null, "\t"));
  console.error(`\n✓ 本次新增通稿 ${newExcluded} 条 → 黑名单累计 ${excludeSet.size} url`);
  console.error(`  (实际从 news.json 移除由 convert 消费黑名单完成)`);
}

async function readJsonSafe(f) {
  try { return JSON.parse(await fs.readFile(f, "utf8")); } catch { return null; }
}

main().catch((e) => { console.error("fatal:", e); process.exit(1); });
