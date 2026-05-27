// @ts-check
import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import react from "@astrojs/react";
import icon from "astro-icon";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { remarkWikiLink } from "./src/plugins/remark-wiki-link";

// https://astro.build/config
export default defineConfig({
  site: "https://chanw.org",
  image: {
    domains: ["res.cloudinary.com"],
  },
  integrations: [
    mdx({
      remarkPlugins: [remarkWikiLink, remarkMath],
      rehypePlugins: [rehypeKatex],
      shikiConfig: {
        // vitesse-light：低饱和度浅色主题，与 cream 正文背景协调。
        // 章节里的短代码块（5-15 行 R/Python 教学片段）从"夺目黑块"
        // 降级为"学术论文 listing"，不破坏阅读流。
        theme: "vitesse-light",
        wrap: true,
      },
    }),
react(),
    icon(),
  ],
});
