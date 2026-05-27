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
        theme: "night-owl",
        wrap: true,
      },
    }),
react(),
    icon(),
  ],
});
