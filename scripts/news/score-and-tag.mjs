#!/usr/bin/env node
/**
 * Score, tag, and write Chinese 导读 for items in feed-raw.json.
 *
 * One prompt per item returns a JSON object:
 *
 *   { "score": 1..5, "category": "<one of 18>", "cn": "<80–180 chars>" }
 *
 * Items with score >= MIN_SCORE (default 3) are kept. Output is written to
 * src/data/generated/feed-scored.json. Already-scored items are skipped on
 * subsequent runs (keyed by stable id), so cron can run incrementally.
 *
 * Auth: OPENROUTER_API_KEY env. Model: $OR_MODEL or deepseek/deepseek-v4-flash.
 *
 * Modes (CLI flags):
 *   --overwrite      regenerate all items (ignore existing scored cache)
 *   --limit N        process at most N items this run
 *   --concurrency N  parallel requests (default 8)
 *   --min-score N    minimum score to keep (default 3)
 *   --dry-run        log each result, do not write file
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..", "..");

// All raw input feeds. Each gets merged into one scored output keyed by
// stable item id. New inputs only need to drop a *-raw.json file here.
const RAW_FILES = [
  path.join(projectRoot, "src/data/generated/feed-raw.json"),
  path.join(projectRoot, "src/data/generated/feed-aigclink-raw.json"),
  path.join(projectRoot, "src/data/generated/feed-extras-raw.json"),
];
const OUT_FILE = path.join(projectRoot, "src/data/generated/feed-scored.json");
const OVERRIDES_FILE = path.join(
  projectRoot,
  "content/news/feed-score-overrides.yml",
);

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY;
const ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";

// OR_MODEL 指定单一付费模型（如 deepseek/deepseek-v4-flash），跳过免费轮询，
// 速度快、稳定，不再受免费模型限流拖累。未设则回落到免费模型轮询。
const FORCED_MODEL = process.env.OR_MODEL || "";

// 免费模型轮询：每次启动时去 OpenRouter 拉当前所有免费模型列表，
// 按对中文任务的能力倾向排序，调用时按序尝试；遇到 429 / 402 / quota
// 错误就把那个模型记到当日 exhausted cache，后续 call 跳过它。
// 一日内所有免费模型都跑完，剩余条目留着，下次 cron 再试。
const PREFERRED_MODEL_KEYWORDS = [
  "deepseek",      // DeepSeek 中文强、推理稳
  "qwen",          // Qwen 原生中文
  "glm",           // 智谱
  "google/gemini", // Gemini 中文好且快
  "meta-llama/llama", // Llama 兜底
  "nvidia/",       // Nemotron 兜底
  "mistralai/",    // Mistral 兜底
];
const EXHAUSTED_CACHE = path.join(
  projectRoot,
  ".cache",
  `openrouter-exhausted-${new Date().toISOString().slice(0, 10)}.json`,
);
let exhausted = new Set();
try {
  exhausted = new Set(
    JSON.parse(await fs.readFile(EXHAUSTED_CACHE, "utf8")),
  );
} catch {
  // 文件不存在或第一次跑，照常
}
let availableModels = null; // 懒加载

async function fetchFreeModels() {
  const res = await fetch("https://openrouter.ai/api/v1/models");
  if (!res.ok) {
    throw new Error(`无法拉取 OpenRouter 模型列表：HTTP ${res.status}`);
  }
  const json = await res.json();
  const all = json.data || [];
  const free = all
    .filter(
      (m) =>
        m.id?.endsWith(":free") ||
        (m.pricing && m.pricing.prompt === "0" && m.pricing.completion === "0"),
    )
    .map((m) => m.id);
  // 按偏好排序
  free.sort((a, b) => {
    const ai = PREFERRED_MODEL_KEYWORDS.findIndex((k) => a.toLowerCase().includes(k));
    const bi = PREFERRED_MODEL_KEYWORDS.findIndex((k) => b.toLowerCase().includes(k));
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
  return free;
}

async function ensureModelList() {
  if (FORCED_MODEL) return [FORCED_MODEL];
  if (availableModels) return availableModels;
  const all = await fetchFreeModels();
  availableModels = all.filter((m) => !exhausted.has(m));
  console.log(`[openrouter] 发现 ${all.length} 个免费模型，可用 ${availableModels.length}（${exhausted.size} 已耗尽）`);
  console.log(`[openrouter] 优先序：`);
  availableModels.slice(0, 8).forEach((m, i) => console.log(`  ${i + 1}. ${m}`));
  if (availableModels.length === 0) {
    throw new Error("今日所有免费模型都已耗尽，明天再跑。");
  }
  return availableModels;
}

async function markExhausted(model) {
  if (FORCED_MODEL) return; // 付费模型不进每日耗尽名单
  exhausted.add(model);
  availableModels = availableModels?.filter((m) => m !== model) || null;
  try {
    await fs.mkdir(path.dirname(EXHAUSTED_CACHE), { recursive: true });
    await fs.writeFile(EXHAUSTED_CACHE, JSON.stringify([...exhausted], null, 2));
  } catch (e) {
    console.warn(`[exhausted] 写缓存失败：${e.message}`);
  }
}

const CATEGORIES = [
  "大模型",
  "图像模型",
  "视频生成模型",
  "3D",
  "世界模型",
  "Agent",
  "编程工具",
  "浏览器自动化",
  "TTS",
  "ASR",
  "UI生成",
  "设计",
  "知识库",
  "skill",
  "安全",
  "训练",
  "评测",
  "其他",
];

// ─────────────────────────────────────────────────────────────────────────
// System prompt — JSON output, scoring rubric, category list, plus the cn
// red lines (verbatim from book-writing-default, adapted to a one-paragraph
// 80–180 char summary).
// ─────────────────────────────────────────────────────────────────────────
const SYSTEM_PROMPT = `你是一个 AI 资讯目录站的编辑，正在给厂商一手公告或独立项目打分、归类、清洗标题、并写 80–180 字中文导读。

# 输出格式（严格 JSON，不要 markdown 代码块）

{
  "score": 1-5 的整数,
  "category": "下方列表里的一项中文标签",
  "cleanedTitle": "清洗后的中文标题，15–55 字，客观陈述",
  "cn": "80-180 字中文导读，一段散文"
}

# cleanedTitle 规则

输入的标题可能是英文（来自厂商 RSS），也可能是中文编辑写的口语化版本。无论哪种，统一产出**简洁客观的中文标题**：

- 主语用项目名 / 厂商名（如 "Anthropic"、"Qwen"、"Kimi"、"NVIDIA"、"Horizon"）
- 动词用 "发布"、"开源"、"推出"、"更新"、"上线"，不用"放出来了"、"放出"、"丢出"、"扔出"
- 严禁口语化前缀："溜儿"、"酷"、"妥妥的"、"刚刚把"、"昨晚"、"深夜炸弹"、"杀疯了"、"绝了"、"AI 圈炸了"
- 严禁戏剧动词："炸弹"、"重磅"、"突袭"、"开撕"、"暴击"、"屠榜"、"震撼"、"血洗"
- 严禁口语副词："太牛了"、"超强"、"贼快"、"巨"、"爆款"、"逆天"
- 保留专名与版本号：GPT-5.5、Claude Opus 4.7、Kimi K2.6、Gemma 4、Qwen3.6-35B-A3B 保持原样
- 不加副标题、不带括号注释、不带 emoji
- 例：
  - "溜儿，Anthropic刚刚把Claude Opus 4.7放出来了" → "Anthropic 发布 Claude Opus 4.7"
  - "OpenAI深夜炸弹放出了：GPT-5.5，超Claude Opus 4.7" → "OpenAI 发布 GPT-5.5"
  - "酷，browser use刚出的一个仅592行代码的极简自愈式浏览器自动化框架：Browser Harness" → "browser-use 开源 Browser Harness 浏览器自动化框架"
  - "Databricks brings GPT-5.5 to enterprise agent workflows" → "Databricks 将 GPT-5.5 接入企业 agent 工作流"

# 评分规则 (score)

5 = 新模型发布、重大产品发布、关键基础设施发布、决定性研究突破
4 = 重要功能/能力更新、有显著技术含量的研究、影响面广的工具发布
3 = 有信息量的工具/SDK/API 更新、可落地的应用案例、生态合作
2 = 一般产品更新、企业合作、地区扩展、运营动态
1 = 公关、品牌活动、招聘、HR、政策表态、无技术含量

# 分类标签 (category)，必须从下面 18 项里选一个

${CATEGORIES.join(" / ")}

判断要点：模型新版本/能力突破 → 大模型；文生图/编辑模型 → 图像模型；文生视频 → 视频生成模型；
NeRF/3DGS/三维重建 → 3D；可交互的虚拟环境/物理世界生成 → 世界模型；
agent 框架/多智能体 → Agent；编程 copilot/CLI/IDE → 编程工具；browser-use 这类 → 浏览器自动化；
语音合成 → TTS；语音识别 → ASR；HTML/UI 生成 → UI生成；设计工具 → 设计；
向量库/RAG → 知识库；Claude Code skill 类 → skill；安全/对齐 → 安全；
训练框架/数据集 → 训练；benchmark/榜单 → 评测；以上都对不上 → 其他。

# 中文导读规则（cn 字段）

每写完一段都要逐条 grep 自检；命中任何一条立即重写。

## 严禁的句式与词

- 严禁"不是 A 而是 B"句式（含变体："不是 A，是 B"、"并非 A，而是 B"、"这不是 X"）
- 严禁"至少三类/两件事/三件事"等数字量词引导段落
- 严禁 itemize / 列表（一段散文，不分行不列点）
- 严禁"值得注意的是 / 综上所述 / 用一句话说 / 不难发现 / 显然 / 由此可见 / 我们可以看到"
- 严禁"这不是 X / 这并非 X"否定前置
- 一段最多 1 个破折号
- 严禁渲染词："活生生 / 翻车 / 玄学 / 惊人的 / 伟大的"
- 严禁戏剧形容："戏剧性 / 命运 / 奇迹 / 灵魂 / 核心本质 / 入场券 / 第一刀"
- 严禁隐喻动词："押注 / 保险绳 / 工具箱 / 账本 / 地图 / 导航 / 救命"
- 严禁"通过 X 实现 Y / 借助 X 完成 Y / 利用 X 进行 Y"动宾倒装
- 严禁"特别适合 / 尤其适合 / 特别针对 / 特别擅长"——"特别 +" 是 AI 写中文最高发的口癖
- 严禁"全方位 / 全场景 / 全流程 / 一站式 / 开箱即用 / 完整工作流 / 成熟的 / 主流的 / 专业的 / 高效"
- 严禁"强大的 / 颠覆性 / 革命性 / 完美 / 灵魂 / 核心本质"
- 严禁"带你 / 教你 / 讲清 / 玩转 / 速览 / 一文读懂"
- 严禁中文夹全角括号注释（"前 X，简称 Y" 这样自然融入）
- 严禁"涵盖 / 覆盖 / 集成 / 整合 / 支持"开头接 5+ 个并列名词的"报菜名"句

## 必须做

- 直接陈述：项目名做主语，第三人称
- 英文专名保留：Claude / GPT / Anthropic / MCP / RAG / LLM / agent / skill / API / SDK
- 80–180 个中文字符（少于 60 太敷衍，多于 220 太长）
- 一段散文，不分行不列点
- 抓最重要的一两个事实，不复读英文摘要

# 注意

只输出一个 JSON 对象。不要解释、不要 markdown 围栏、不要前缀。`;

// ─────────────────────────────────────────────────────────────────────────
// Red-line validators — applied to cn field only, matching fill-cn.mjs rules.
// ─────────────────────────────────────────────────────────────────────────
const RED_LINES = [
  { name: "不是A而是B", re: /不是[^。，；]{1,40}(?:而是|，是)/ },
  { name: "并非而是", re: /并非[^。，；]{1,40}而是/ },
  { name: "这不是/这并非开头", re: /(?:^|[。；])\s*这不是|(?:^|[。；])\s*这并非/ },
  { name: "数字量词清单", re: /(?:至少|有)[一二三四五六七八九十两][类件个种点项条种]/ },
  { name: "X阶段X步式", re: /[一二三四五六七八九十两][阶层段步]/ },
  { name: "数字+功能/能力/场景", re: /[一二三四五六七八九十两](?:大|个|种|类)(?:核心)?(?:功能|能力|场景|模块|特性|优势|步骤|流程)/ },
  { name: "AI套话", re: /值得注意的是|不容忽视|不难发现|综上所述|由此可见|易得|一言以蔽之|用一句话说|我们可以看到/ },
  { name: "营销词", re: /强大的|颠覆性|革命性|全方位|全场景|全流程|一站式|开箱即用|易用|易于使用|核心本质|灵魂|完美|完整工作流|高效/ },
  { name: "成熟/主流形容", re: /成熟(?:的|工具链|库)|主流(?:的|工具|方案)|专业(?:的|工具|方案|级)/ },
  { name: "特别+", re: /特别(?:适合|强调|针对|擅长|适用|关注)|尤其(?:适合|擅长|适用)/ },
  { name: "动宾倒装AI句", re: /通过[^。，；]{1,30}(?:实现|完成|提供|支持)|借助[^。，；]{1,30}(?:实现|完成)|利用[^。，；]{1,30}(?:进行|完成|实现)/ },
  { name: "渲染词", re: /活生生|翻车|玄学|惊人的|伟大的|乍一看/ },
  { name: "戏剧形容", re: /戏剧性|命运|奇迹|脆弱处|入场券|第一刀|桥梁/ },
  { name: "隐喻动词", re: /押注|押对|押错|保险绳|工具箱|账本|地图|导航|救命/ },
  { name: "口语动词", re: /带你|教你|讲完|讲清|搞懂|玩转|手把手|轻松搞定/ },
  { name: "速通词", re: /速览|一文读懂|极简指南|三分钟看懂/ },
  { name: "AI 营销开头", re: /^本(?:项目|工具|产品|模型|框架|skill)(?:提供|实现|支持|帮助你|让你)|^该(?:项目|工具|产品|模型|框架|skill)(?:提供|实现|支持)/ },
  { name: "全角括号注释", re: /[一-鿿]\s*[（(][A-Za-z][^()）]{0,30}[)）]/ },
];

export function validateCn(text) {
  const hits = [];
  for (const { name, re } of RED_LINES) if (re.test(text)) hits.push(name);
  const charCount = [...text.replace(/\s+/g, "")].length;
  if (charCount < 60) hits.push(`too-short(${charCount})`);
  if (charCount > 240) hits.push(`too-long(${charCount})`);
  if ((text.match(/——/g) || []).length > 1) hits.push("too-many-dashes");
  return hits;
}

// Title-specific validators: catches AIGCLINK / influencer-style colloquial
// phrasing that the editor uses but the site style forbids.
const TITLE_BANNED = [
  { name: "口语前缀", re: /^(溜儿|酷|妥妥的|这家伙|哥们|绝了|杀疯了|牛了|炸了|爆了)/ },
  { name: "戏剧词", re: /炸弹|重磅|突袭|开撕|暴击|屠榜|震撼|血洗|王炸|逆天|爆款|杀疯/ },
  { name: "夸张副词", re: /太牛|超强|贼快|巨能|巨好|碾压|秒杀|吊打/ },
  { name: "口语动词", re: /放出来|丢出|扔出|甩出|掏出|甩出来|刷屏|出圈/ },
  { name: "时间口语", re: /昨晚|深夜|凌晨|半夜|今早|刚刚刚/ },
  { name: "标题营销词", re: /强势|王者|领跑|霸榜|登顶|屠榜/ },
];

export function validateTitle(text) {
  if (!text) return ["empty"];
  const hits = [];
  for (const { name, re } of TITLE_BANNED) if (re.test(text)) hits.push(name);
  const charCount = [...text.replace(/\s+/g, "")].length;
  if (charCount < 6) hits.push(`too-short(${charCount})`);
  if (charCount > 80) hits.push(`too-long(${charCount})`);
  return hits;
}

// ─────────────────────────────────────────────────────────────────────────
// Argv
// ─────────────────────────────────────────────────────────────────────────
const argv = new Map();
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith("--")) {
    const k = a.slice(2);
    const next = process.argv[i + 1];
    if (!next || next.startsWith("--")) argv.set(k, true);
    else {
      argv.set(k, next);
      i++;
    }
  }
}
const OVERWRITE = !!argv.get("overwrite");
const LIMIT = argv.get("limit") ? parseInt(argv.get("limit"), 10) : Infinity;
const CONCURRENCY = argv.get("concurrency")
  ? parseInt(argv.get("concurrency"), 10)
  : 8;
const MIN_SCORE = argv.get("min-score")
  ? parseInt(argv.get("min-score"), 10)
  : 3;
const DRY_RUN = !!argv.get("dry-run");

// ─────────────────────────────────────────────────────────────────────────
// LLM call
// ─────────────────────────────────────────────────────────────────────────
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function stripFences(text) {
  return text
    .replace(/^\s*```(?:json)?\s*\n?/i, "")
    .replace(/\n?```\s*$/, "")
    .trim();
}

function buildPrompt(item) {
  const parts = [
    `[来源]: ${item.sourceName} (${item.source})`,
    `[标题]: ${item.title}`,
  ];
  if (item.category) parts.push(`[原分类标签]: ${item.category}`);
  if (item.publishedAt) parts.push(`[发布时间]: ${item.publishedAt.slice(0, 10)}`);
  if (item.summary) parts.push(`[原英文摘要]: ${item.summary}`);
  parts.push(`[URL]: ${item.url}`);
  parts.push("");
  parts.push("按系统提示的 JSON schema 输出。");
  return parts.join("\n");
}

async function callModel(messages) {
  if (!OPENROUTER_KEY) throw new Error("OPENROUTER_API_KEY env not set");
  const models = await ensureModelList();
  let lastErr;
  for (const model of [...models]) {
    if (exhausted.has(model)) continue;
    let res;
    try {
      res = await fetch(ENDPOINT, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${OPENROUTER_KEY}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://chanw.org",
          "X-Title": "Chanw news scorer",
        },
        body: JSON.stringify({
          model,
          messages,
          temperature: 0.3,
          max_tokens: 600,
          response_format: { type: "json_object" },
        }),
      });
    } catch (e) {
      // 网络层错误，跳到下一个模型但不标 exhausted
      console.warn(`[network] ${model}: ${e.message}`);
      lastErr = e;
      continue;
    }
    if (res.status === 200) {
      const json = await res.json();
      return json.choices?.[0]?.message?.content?.trim() ?? "";
    }
    if (res.status === 429 || res.status === 402) {
      const body = await res.text().catch(() => "");
      console.log(`[exhausted] ${model} (HTTP ${res.status}): ${body.slice(0, 100)}`);
      await markExhausted(model);
      continue;
    }
    if (res.status === 503 || res.status >= 500) {
      // 服务端临时错误，等一会儿再试同一模型
      await sleep(5000);
      try {
        res = await fetch(ENDPOINT, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${OPENROUTER_KEY}`,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chanw.org",
            "X-Title": "Chanw news scorer",
          },
          body: JSON.stringify({
            model,
            messages,
            temperature: 0.3,
            max_tokens: 600,
            response_format: { type: "json_object" },
          }),
        });
        if (res.status === 200) {
          const json = await res.json();
          return json.choices?.[0]?.message?.content?.trim() ?? "";
        }
      } catch (e) {
        lastErr = e;
      }
      // 仍失败 → 跳到下一个模型，不标 exhausted
      continue;
    }
    // 其他 4xx 错误（请求格式问题、模型不支持 JSON mode 等），跳到下一个
    const body = await res.text();
    console.warn(`[skip] ${model}: HTTP ${res.status} ${body.slice(0, 150)}`);
    lastErr = new Error(`HTTP ${res.status}: ${body.slice(0, 120)}`);
  }
  throw new Error(
    `所有可用免费模型都失败了。最后一个错误：${lastErr?.message || "未知"}`,
  );
}

function parseJson(raw) {
  const cleaned = stripFences(raw);
  // tolerate trailing commas / stray text outside the object
  const m = cleaned.match(/\{[\s\S]*\}/);
  if (!m) throw new Error("no JSON object in response");
  return JSON.parse(m[0]);
}

async function scoreOne(item) {
  const messages = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: buildPrompt(item) },
  ];
  let raw = await callModel(messages);
  let parsed;
  try {
    parsed = parseJson(raw);
  } catch (e) {
    throw new Error(`JSON parse failed: ${e.message} | raw: ${raw.slice(0, 200)}`);
  }
  const score = Math.max(1, Math.min(5, parseInt(parsed.score, 10) || 1));
  const category = CATEGORIES.includes(parsed.category) ? parsed.category : "其他";
  let cleanedTitle = String(parsed.cleanedTitle || "").trim();
  let cn = String(parsed.cn || "").trim();

  // Validate both fields against red-line patterns. cleanedTitle uses
  // the same banned-phrase set as cn — colloquial / dramatic words leak
  // into titles just as easily.
  let cnHits = validateCn(cn);
  let titleHits = validateTitle(cleanedTitle);
  if (cnHits.length > 0 || titleHits.length > 0) {
    const issues = [];
    if (cnHits.length) issues.push(`cn: ${cnHits.join("、")}`);
    if (titleHits.length) issues.push(`cleanedTitle: ${titleHits.join("、")}`);
    const retryMsg = `上次输出违反规则 — ${issues.join("；")}。重写违规字段，严格遵守系统提示中的规则，其它字段保持。再次输出完整 JSON。`;
    const raw2 = await callModel([
      ...messages,
      { role: "assistant", content: raw },
      { role: "user", content: retryMsg },
    ]);
    try {
      const parsed2 = parseJson(raw2);
      if (parsed2.cn) cn = String(parsed2.cn).trim();
      if (parsed2.cleanedTitle) cleanedTitle = String(parsed2.cleanedTitle).trim();
      cnHits = validateCn(cn);
      titleHits = validateTitle(cleanedTitle);
    } catch {
      /* keep first values, residue will be logged */
    }
  }
  return { score, category, cleanedTitle, cn, cnHits, titleHits };
}

// ─────────────────────────────────────────────────────────────────────────
// Orchestration
// ─────────────────────────────────────────────────────────────────────────

async function runPool(items, worker, concurrency) {
  const results = new Array(items.length);
  let i = 0;
  async function next() {
    while (true) {
      const idx = i++;
      if (idx >= items.length) return;
      try {
        results[idx] = await worker(items[idx], idx);
      } catch (err) {
        results[idx] = { error: err.message };
      }
    }
  }
  await Promise.all(Array.from({ length: concurrency }, next));
  return results;
}

async function main() {
  // Merge every available raw feed file into a single list; later
  // duplicates by id are dropped so the order of RAW_FILES wins on ties.
  const rawItems = [];
  const seenRawIds = new Set();
  for (const file of RAW_FILES) {
    try {
      const data = JSON.parse(await fs.readFile(file, "utf8"));
      for (const it of data.items ?? []) {
        if (seenRawIds.has(it.id)) continue;
        seenRawIds.add(it.id);
        rawItems.push(it);
      }
    } catch {
      /* file may not exist for sources that aren't wired yet */
    }
  }

  let existing = { fetchedAt: null, items: [] };
  try {
    existing = JSON.parse(await fs.readFile(OUT_FILE, "utf8"));
  } catch {
    /* first run */
  }
  const existingById = new Map(existing.items.map((it) => [it.id, it]));

  const toProcess = rawItems.filter(
    (it) => OVERWRITE || !existingById.has(it.id),
  );
  const targets = toProcess.slice(0, LIMIT);
  console.log(
    `score-and-tag: ${targets.length} to process (raw=${rawItems.length}, cached=${existingById.size}, overwrite=${OVERWRITE})`,
  );

  let done = 0;
  let kept = 0;
  let dropped = 0;
  let errored = 0;
  const failedHits = [];

  const newScored = await runPool(
    targets,
    async (item, idx) => {
      const out = await scoreOne(item);
      done++;
      const allHits = [
        ...out.cnHits.map((h) => `cn:${h}`),
        ...out.titleHits.map((h) => `title:${h}`),
      ];
      if (allHits.length > 0) failedHits.push({ id: item.id, hits: allHits });
      if (out.score >= MIN_SCORE) kept++;
      else dropped++;
      const tag = out.score >= MIN_SCORE ? "KEEP" : "drop";
      process.stdout.write(
        `  [${String(done).padStart(3)}/${targets.length}] ${tag} ${String(out.score)}|${out.category.padEnd(8)} ${out.cleanedTitle.slice(0, 60)}\n`,
      );
      if (DRY_RUN) {
        process.stdout.write(`        title was: ${item.title.slice(0, 80)}\n`);
        process.stdout.write(`        cn: ${out.cn}\n`);
      }
      return {
        ...item,
        // Replace the raw title with the cleaned Chinese title so the
        // site renders consistently; keep upstream URL and source intact.
        title: out.cleanedTitle || item.title,
        originalTitle: item.title,
        score: out.score,
        category: out.category,
        cn: out.cn,
      };
    },
    CONCURRENCY,
  );

  for (const r of newScored) {
    if (r?.error) {
      errored++;
      console.warn(`  ERROR: ${r.error}`);
    }
  }

  // Merge: keep existing, add new (drop those below MIN_SCORE).
  const merged = new Map(existingById);
  for (const it of newScored) {
    if (!it || it.error) continue;
    if (it.score < MIN_SCORE) {
      merged.delete(it.id); // drop if previously kept but re-scored below threshold
      continue;
    }
    merged.set(it.id, it);
  }

  // Refresh raw-side metadata on cached entries. Source-side fields
  // (source id, sourceName, publishedAt) can change between runs — e.g.
  // when a feed source gets renamed or split — and we don't want the
  // cached score to lock us into stale labels. The LLM-derived fields
  // (cleanedTitle / score / category / cn) stay untouched.
  const rawByIdForRefresh = new Map(rawItems.map((it) => [it.id, it]));
  for (const [id, scored] of merged) {
    const raw = rawByIdForRefresh.get(id);
    if (!raw) continue;
    if (
      scored.source !== raw.source ||
      scored.sourceName !== raw.sourceName ||
      (raw.publishedAt && scored.publishedAt !== raw.publishedAt)
    ) {
      merged.set(id, {
        ...scored,
        source: raw.source,
        sourceName: raw.sourceName,
        url: raw.url,
        publishedAt: raw.publishedAt ?? scored.publishedAt,
      });
    }
  }

  // Prune entries whose source item no longer exists in any raw input.
  const rawIds = new Set(rawItems.map((i) => i.id));
  for (const id of [...merged.keys()]) {
    if (!rawIds.has(id)) merged.delete(id);
  }

  // Apply editor overrides last. They can rescue items the LLM dropped
  // (by writing in score >= MIN_SCORE) and can correct cleanedTitle /
  // category / cn on items that already passed.
  let overrides = {};
  try {
    overrides = yaml.load(await fs.readFile(OVERRIDES_FILE, "utf8")) || {};
  } catch {
    /* fine — file is optional */
  }
  const rawById = new Map(rawItems.map((it) => [it.id, it]));
  let rescuedByOverride = 0;
  let patchedByOverride = 0;
  for (const [id, patch] of Object.entries(overrides)) {
    if (!patch || typeof patch !== "object") continue;
    const raw = rawById.get(id);
    if (!raw) continue; // override points at an id that no longer exists in raw
    const base = merged.get(id);
    if (base) {
      // patch in place — apply only the fields present
      const next = { ...base };
      if (typeof patch.score === "number") next.score = patch.score;
      if (typeof patch.category === "string") next.category = patch.category;
      if (typeof patch.cleanedTitle === "string") {
        next.title = patch.cleanedTitle;
      }
      if (typeof patch.cn === "string") next.cn = patch.cn.trim();
      next.editorOverride = true;
      merged.set(id, next);
      patchedByOverride++;
    } else {
      // rescue: build a record from raw + override fields
      const score = typeof patch.score === "number" ? patch.score : 3;
      if (score < MIN_SCORE) continue;
      merged.set(id, {
        ...raw,
        title: typeof patch.cleanedTitle === "string" ? patch.cleanedTitle : raw.title,
        originalTitle: raw.title,
        score,
        category: typeof patch.category === "string" ? patch.category : "其他",
        cn: typeof patch.cn === "string" ? patch.cn.trim() : "",
        editorOverride: true,
      });
      rescuedByOverride++;
    }
  }

  const items = [...merged.values()].sort((a, b) => {
    const ad = a.publishedAt ? Date.parse(a.publishedAt) : 0;
    const bd = b.publishedAt ? Date.parse(b.publishedAt) : 0;
    if (bd !== ad) return bd - ad;
    return b.score - a.score;
  });

  if (!DRY_RUN) {
    await fs.writeFile(
      OUT_FILE,
      JSON.stringify({ fetchedAt: new Date().toISOString(), items }, null, 2),
    );
  }
  console.log(
    `\nsummary: kept=${kept} dropped=${dropped} errored=${errored} | total in file=${items.length}` +
      (rescuedByOverride || patchedByOverride
        ? ` | overrides rescued=${rescuedByOverride} patched=${patchedByOverride}`
        : "") +
      (failedHits.length ? ` | red-line residue on ${failedHits.length} items` : "") +
      (DRY_RUN ? " (dry-run, no file write)" : ` -> ${path.relative(projectRoot, OUT_FILE)}`),
  );
  if (failedHits.length) {
    console.log("red-line residue details:");
    for (const f of failedHits) console.log(`  ${f.id}: ${f.hits.join(", ")}`);
  }
}

// Only auto-run when executed directly (not when imported by tests).
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error("score-and-tag failed:", err);
    process.exit(1);
  });
}
