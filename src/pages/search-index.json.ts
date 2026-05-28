/**
 * Build-time endpoint: /search-index.json
 *
 * 输出一个 merged search index 供客户端 SearchBox fetch + 全客户端过滤。
 * 索引 3 类内容：Skills (130) + Library books (15) + News (1745) ≈ 1900 项。
 *
 * 每项结构统一为：{type, title, description?, url, meta?}
 * 客户端按 title + description 子串匹配（lowercased）。
 */
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import skillsData from "../data/skills.json";
import newsItems from "../data/news.json";

type IndexItem = {
	type: "skill" | "book" | "news";
	title: string;
	description?: string;
	url: string;
	meta?: string;
};

export const GET: APIRoute = async () => {
	const items: IndexItem[] = [];

	// Skills: dedupe by slug since /skills 显示重复（pdf/docx 在多个分类）
	const seenSkills = new Set<string>();
	for (const s of skillsData as Array<{
		slug: string;
		repo: string;
		path?: string;
		ref?: string;
		descriptionZh?: string | null;
		categoryLabel?: string;
	}>) {
		if (seenSkills.has(s.slug)) continue;
		seenSkills.add(s.slug);
		const branch = s.ref || "main";
		const resolvedPath = s.path || `skills/${s.slug}`;
		items.push({
			type: "skill",
			title: s.slug,
			description: s.descriptionZh ?? undefined,
			url: `https://github.com/${s.repo}/tree/${branch}/${resolvedPath}`,
			meta: s.categoryLabel,
		});
	}

	// Books: from collection
	const books = await getCollection("books");
	for (const b of books) {
		items.push({
			type: "book",
			title: b.data.title,
			description: b.data.subtitle,
			url: b.data.link ?? `/books/${b.data.slug ?? ""}`,
			meta: b.data.series,
		});
	}

	// News
	for (const n of newsItems as Array<{
		title: string;
		url: string;
		source?: string;
		date?: string;
	}>) {
		items.push({
			type: "news",
			title: n.title,
			url: n.url,
			meta: n.source,
		});
	}

	return new Response(JSON.stringify(items), {
		headers: { "Content-Type": "application/json; charset=utf-8" },
	});
};
