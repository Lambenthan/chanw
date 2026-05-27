# Maggie 设计语言参照 + 学术章节映射

本文档分两部分：
- **Part A**：Maggie 22 篇 essays 实证统计出来的设计语言规则 —— 每个组件她用在什么语义场景、用多频
- **Part B**：把这套规则映射到本项目的学术章节内容 —— 哪些能直接套用、哪些要新建组件

写这份文档的原因：上一轮我犯了"看到组件名就机械套用"的错（譬如把 `Alert` 当成万能盒子套在 Definition/Theorem/章节导言上）。Alert 是**警示**组件，Maggie 在 essays 里 **0 次**用过它。要正确使用她的设计语言，必须先理解每个组件的**语义触发条件**。

---

## Part A · Maggie 设计语言实证规则

数据来源：`src/content/essays/*.mdx`（22 篇）+ `src/content/notes/*.mdx`（92 篇）的 grep 统计 + 全文阅读 `ai-dark-forest.mdx`。

### A.1 文章顶层结构（开篇三件套）

**模板**（86% essays 沿用）：

```mdx
import AssumedAudience from "../../components/mdx/AssumedAudience.astro";
import IntroParagraph from "../../components/mdx/IntroParagraph.astro";
... (其他用到的组件)

<AssumedAudience>
[本文为谁写。1-3 句，描述读者画像。]
</AssumedAudience>

<Spacer size="small" />

<IntroParagraph>第一段正文，首字下沉。可以含 [[wiki link]] 和 <Footnote idName={1}>...</Footnote>。</IntroParagraph>

[后续是普通段落 + 各种组件]
```

**关键**：AssumedAudience **不是装饰盒子**，是"读者契约" —— 告诉读者"你是这类人才适合读，否则别浪费时间"。每篇只有 1 个。

### A.2 组件使用频率（按 22 篇 essays import 统计）

| 组件 | 出现频次 | 占比 | 语义角色 |
|---|---:|---:|---|
| `IntroParagraph` | 19 / 22 | **86%** | 第一段正文 dropcap，每篇 1 次 |
| `Footnote` | 17 / 22 | **77%** | Tufte 边注，行内补注，浮在右栏 |
| `AssumedAudience` | 10 / 22 | 45% | 文章开篇定义读者，仅长 essay 用 |
| `GridColumns` | 10 / 22 | 45% | 多张图并排成网格 |
| `YearsAgo` | 9 / 22 | 41% | 行内 "X years ago"（动态算） |
| `TweetEmbed` | 6 / 22 | 27% | 引用推文 |
| `References` + `ReferencesLink` | 6 / 22 | 27% | 文末参考文献区 |
| `Video` | 5 / 22 | 23% | 嵌入视频 |
| `SimpleCard` / `Center` | 4 / 22 | 18% | |
| `FullWidthBackground` / `ComingSoon` / `AcademicReference` | 3 / 22 | 14% | |
| `BlockquoteCitation` | **2 / 22** | **9%** | 仅用于"外部作者真名实姓引用" |
| `Alert` | **0 / 22** | **0%** | **essays 不用**，仅在 notes 里偶尔出现 |
| `h2.micro` | 5 / 22 | 23% | 红色 sans 大写 caption，用得克制 |

**核心警示**：

1. **Alert 在 essays 里 0 次出现**。它只在 3 篇 notes 出现（`css-position`、`metatour`、`react-vdom`），且都是"过时信息 / 技术免责声明"语境（"这套写法在 X 情况会失效"、"这视频是旧版站点的"、"React 团队不再用 VDOM 这个心智模型"）。**Alert = 警示读者注意「我接下来要纠正一个常见误解 / 提醒一个失效场景」**。不是定义、不是定理、不是导言。

2. **BlockquoteCitation 只 9% essays 在用，且每篇只 1-2 次**。语义严格 —— 必须是引用其他作者（有名有姓）的原话。Maggie 自己的强调、章节导言、内部对话**绝不**包进 BlockquoteCitation。

3. **plain `> blockquote` 是主力**（51 次实例）。Maggie 的 prose 风格自动给它配 centered + max-30ch + 上下细横线的"格言匣"视觉。她用它来：放强调句、放需要慢读的核心命题、放反问式自言自语。

### A.3 引用的两套写法（重要区分）

**外部作者引用 → `BlockquoteCitation`**：

```mdx
<BlockquoteCitation
  author="Murray Shanahan"
  title="Talking About Large Language Models"
  url="http://arxiv.org/abs/2212.03551"
>
Humans are members of a community of language-users inhabiting a shared world,
and this primal fact makes them essentially different to large language models...
</BlockquoteCitation>
```

视觉：底部居中显示 `Murray Shanahan – Talking About Large Language Models`。

**内部强调 / 反问 / 命题 → plain `>`**：

```mdx
> *如果这个事件没发生，阳明的人格演化轨迹会是什么样？*
```

视觉：自动居中、最宽 30ch、上下细灰线、字号 `--font-size-lg`。

**误用警告**：上一轮我把"如果事件没发生"这类内部 voice 包成 BlockquoteCitation 是错的。它没有外部作者。该用 `>`。

### A.4 边注（Footnote）的 Tufte 风格

Maggie 的 Footnote 不是页脚跳转，是**右栏浮动边注**（Tufte sidenotes）：

```mdx
The dark forest theory of the web...<Footnote idName={1}>[Dark Forest Theory of the Internet](https://...) by Yancey Strickler</Footnote> Most open spaces...
```

行内显示 `1` 上标，右栏同步显示 `1 Dark Forest Theory... by Yancey Strickler` 小字。

**何时用 Footnote**（基于她 17 篇 essays 的实证）：
- 提到一个值得标明出处的外部链接，但不想打断主句
- 补充一个有趣的题外话（带玩笑色彩 — 譬如 `<Footnote>This feels like a hostage holding up yesterday's newspaper</Footnote>`）
- 给一个术语加学术性的来源说明
- 提供时间敏感的状态说明（"目前 GPT-3 的训练截止是 <YearsAgo>2021</YearsAgo>"）

**何时 NOT 用 Footnote**：
- 整段独立段落 → 用主流叙述
- 学术参考文献 → 走 `<References>` + `<ReferencesLink>` 在文末
- 重要警告 → 用 plain blockquote 或独立段落
- 数学公式补充 → 用 `$$` display math 块

### A.5 图片三种模式

| 用法 | 组件 | 触发场景 |
|---|---|---|
| 单张图，嵌在 prose 流里 | `<BasicImage>` | 一个普通配图、示意图 |
| 多张图并列展示 | `<GridColumns>` 包多个 `<BasicImage>` | 6 张 Midjourney 生成图、一组 UI 截图 |
| 大图打破 72ch 限制 | `<BasicImage width="1300px">` 或 `<FullWidthSection>` 包 | 关键大数据图、宽尺寸示意 |

**图说**：`<Subtext>` 跟在图后面提供小灰字注释（譬如 `Images I generated with Midjourney's V4 model`）。

### A.6 章节分隔

**水平横线** `---`：
- 在主题大跨度切换时用（譬如从"问题陈述"切到"解决方案"）
- 视觉是 salmon 短杠（20% 宽，居中）
- 用得克制 —— ai-dark-forest 全文 200 行只用了 1 次

**`h2.micro` 红色 caption**：
- 用作小节的"副标题"或"主题点睛"
- 视觉是 sans 全大写 红色 加字距，比 `<h2>` 小一档
- 偶尔出现在 essay 段落开头当"小标语"

### A.7 文末参考文献

```mdx
<References>
  <ReferencesLink
    title="Talking About Large Language Models"
    href="http://arxiv.org/abs/2212.03551"
    author="Murray Shanahan"
  />
  <ReferencesLink ... />
</References>
```

**何时用**：essay 引用了多个外部学术资源，文末统一列出。**与 Footnote 区分**：Footnote 是行内边注（一般 1 句话），References 是文末正式书目（每条 title + author + url）。

### A.8 行内链接

- `[[wiki link]]` —— 内链到本站其他笔记，自动 hover 预览（remark plugin 处理）
- `[文本](url)` —— 外链，自动用 `TooltipLink` 包 hover 显示 favicon + 标题
- `<AcademicReference authors year title href>` 包行内文本 —— 学术引用样式，hover 弹出完整 abstract

---

## Part B · 学术章节 → Maggie 设计映射

下面给出我的学术章节里**每种语义元素**对应该用 Maggie 哪个组件 / 是否需要新建组件。

### B.1 直接套用 Maggie 组件（语义对得上）

| 学术章节里的元素 | 对应 Maggie 组件 | 用法说明 |
|---|---|---|
| 章节开篇"本章你将学到 / 本章读者画像" | `<AssumedAudience>` | 把"本章要回答的"4 条改写为 1 段散文 |
| 章节首段（提出研究问题） | `<IntroParagraph>` | 首字下沉，注意中文首字（"王"等）的 dropcap 视觉 |
| 引用阳明 / 朱熹原文等古典文献 | `<BlockquoteCitation author title url>` | author = "王阳明"，title = "《传习录》" 等。**只对真实历史人物原文用** |
| 反问 / 内部强调 / 假设场景（"如果事件没发生..."） | plain `> blockquote` | **不要**包 BlockquoteCitation |
| 行内补注 / 题外话 / 数据来源说明 | `<Footnote idName={N}>` | 譬如"括号里的 t 值是 Welch t 检验"这类补充 |
| 学术参考文献（章末） | `<References>` + `<ReferencesLink>` | 每条 author + title + url |
| 数据图（单张） | `<BasicImage>` 或 `<FullWidthSection><BasicImage></FullWidthSection>` | 大数据图必须 full-width |
| 多图组（譬如 4 个子图） | `<GridColumns>` 包多个 `<BasicImage>` | 譬如"4 个事件 ITS 效应图" |
| 图下注释 | `<Subtext>` | 一句话灰字 |
| 章节主题大切换 | `---` (salmon HR) | **克制使用**，最多 2-3 次 / 章 |
| 章末"未解决问题"小节 | 普通 `## H2` + 段落 | 不需要特殊组件 |
| 行内"X 年前" | `<YearsAgo>1508</YearsAgo>` | 想用就用，但学术语境通常直接写 1508 即可 |

### B.2 学术专属元素（Maggie 没有对应组件，必须新建）

这些是学术书的核心组成部分，Maggie 的 prose-essay 设计语言**根本没覆盖** —— 强行硬塞她的组件就是上一轮的错误。需要新建专属组件，但**外观必须沿用 Maggie 的设计语言**（cream 配色 / serif 字体 / sea-blue 强调 / 圆角细边框）。

| 学术元素 | 推荐新组件 | 视觉提案（仿 ElegantBook 学术书风格） |
|---|---|---|
| **定义**（数学定义、概念定义） | `<Definition title="...">` | 左侧 4px sea-blue 竖条 + 浅 cream 底 + 顶上"定义"sans 小标 + 公式 / 文字内容。无 icon。 |
| **定理**（命题、推论） | `<Theorem title="...">` | 左侧 4px crimson 竖条 + 顶上"定理"sans 小标 + 内容。无 icon。 |
| **误区**（方法误用 / 概念误解警告） | 新建 `<Pitfall>` 组件，**不复用** Maggie 的 Alert | Alert 的 salmon 三角太"网络警告"风，跟学术书气质不合。Pitfall 沿用 Definition / Theorem 的左色条 + 顶部 sans 小标族类视觉，色用 dark-salmon |
| **方法卡**（方法摘要） | `<MethodCard title="...">` | 4 项结构化（数学形式 / 核心假设 / 实现 / 失效场景），用 4 个 sea-blue 小标的 dl 列表 |
| **数据表格** | 沿用 markdown pipe table | 但 prose CSS 需要加 `.prose-wrapper table` 样式：cream 表头 / 行交替底色 / 全宽 / 数字 tabular-nums |
| **知识地图**（章末核心概念对比表） | 复用上面的表格样式 | 不需要新组件 |
| **代码块** | 沿用 markdown ` ``` ` fence | shiki 主题已配 `night-owl`，足够好 |

### B.3 学术章节专用页面 chrome（不在组件层面，而在路由层面）

**对比 Maggie essay 的 PostLayout header**：
- 上：back link + growthStage icon + 阶段字
- 中：H1 标题 + description
- 底：topics 标签 + 日期

**我章节页 `[chapter].astro` 应该补的**：
- 上：back link "← 王阳明轨迹" + "第 1 章" 红色 chapter 标签 ✓（已做）
- 中：H1 标题 + description ✓（已做）
- 底：**目前没有 topics / 日期** —— 应该补上 chapter 的 `topics` 和 `updated` 字段渲染，跟 essay 视觉一致
- **新增**：右侧 sticky TOC（小节目录），让长章节也能快速跳

### B.4 上一轮我做错的具体清单

下面是上一轮 chap01 里的具体错误，要在新版本里逐一改：

| 位置 | 上一轮做的 | 该改成 |
|---|---|---|
| "本章要回答的" 4 条 → 包 `<Alert>` | ❌ Alert 是警示，不是导言 | ✅ `<AssumedAudience>` 1 段描述读者画像 |
| 数学定义 → 包 `<Alert title="人格分定义">` | ❌ Alert 警示三角 | ✅ 新建 `<Definition>` 组件，左 sea-blue 竖条 |
| ITS 定义 → 包 `<Alert title="定义 · 中断时间序列因果效应">` | ❌ 同上 | ✅ `<Definition>` |
| 体裁混淆误区 → 用 `<Pitfall title="体裁混淆">` | ✅ 学术警告语义 | 标签自动显示"误区" |
| 内生 treatment 误区 → 用 `<Pitfall title="内生 treatment">` | ✅ | 同上 |
| 方法卡 → 包 `<Alert title="方法卡 ...">` | ❌ 不是警示 | ✅ 新建 `<MethodCard>` 组件 |
| "如果事件没发生..." 反问 → 包成 `<BlockquoteCitation>` | ❌ 不是外部作者引用 | ✅ plain `>` blockquote |
| 5 个人格维度的 `>` 缩进列表 | ✅ 这个是对的 | 保留 |
| 每个 `##` 后加 `<h2 class="micro">小节副标</h2>` | ❌ Maggie 用得克制（1-2 次/篇），我每个 `##` 都塞 | ✅ 全删，只在最关键 2-3 处保留 |
| 章节末没有 `<References>` | ❌ 缺学术参考文献 | ✅ 把章节里 cited 的来源（《传习录》、Welch 检验论文等）汇成 `<References>` |
| 章节里没有 `<Footnote>` | ❌ 没用 Tufte 边注 | ✅ 把"括号补注"性质的内容（譬如"完整代码见 ..."）改为 Footnote |

---

## Part C · 实施步骤建议

1. **先建 3 个学术专属组件**：
   - `src/components/mdx/Definition.astro`（左 sea-blue 竖条 + 顶部"定义"小标）
   - `src/components/mdx/Theorem.astro`（左 crimson 竖条 + 顶部"定理"小标）
   - `src/components/mdx/MethodCard.astro`（4 字段 dl 列表）
   
   视觉规则全部用 Maggie 已有的 CSS 变量（`--color-sea-blue`, `--color-cream`, `--font-serif`, `--space-*`），不引入新 token。

2. **给 prose-wrapper 加表格样式**：在 `src/components/layouts/ProseWrapper.astro` 加 `:global(table)` 规则 —— cream 表头 / 行交替底色 / tabular-nums。

3. **章节路由 [chapter].astro 补充 topics + dates 显示**，仿 PostLayout 那条 metadata 条。

4. **chap01 按 B.4 表逐项改写**，作为 proof-of-concept。

5. **批量化时**：把这套映射规则写成 conversion 脚本（pandoc 输出 → 替换 `<div class="definition">` 为 `<Definition>` 等），剩 6 章 + 12 本书一次性跑。

---

## Part D · 还需用户确认的设计决策

1. **章节开篇 AssumedAudience 的写法** —— Maggie 是"为谁写"，学术章节如果也用这个组件，文案是"本章为谁写"还是改为"本章要回答的"？前者贴合 Maggie 原意，后者贴合学术书惯例。

2. **章节末 References** —— 我章节里的引用大多是历史文献（《传习录》、《年谱》），不是现代学术论文。要不要给历史文献单独写一个 `<HistoricalReferences>` 组件区别于现代 ReferencesLink？还是统一用 ReferencesLink？

3. **Definition / Theorem 视觉走"接近 LaTeX ElegantBook 学术书"还是"接近 Maggie 极简风"？** —— 前者更有学术质感（左竖条 + caption + 内层缩进），后者更轻量（仅一行小标 + 普通段落）。这影响新组件的具体设计。

4. **章节内 micro caption 的具体数量** —— 全章建议 2-3 次。哪 2-3 处合适？我可以等改写时再具体定，但你也可以现在就指明（譬如"每章只在'本章主结论'前用 1 次"）。
