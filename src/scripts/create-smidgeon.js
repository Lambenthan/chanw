#!/usr/bin/env node

import inquirer from "inquirer";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function createSmidgeon() {
  // Get title from user
  const { title } = await inquirer.prompt([
    {
      type: "input",
      name: "title",
      message: "What is the title of your smidgeon?",
      validate: (input) => {
        if (input.trim() === "") {
          return "Title cannot be empty";
        }
        return true;
      },
    },
  ]);

  // Create filename
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-") // Replace non-alphanumeric chars with hyphens
    .replace(/^-+|-+$/g, ""); // Remove leading/trailing hyphens

  const filename = `${year}-${month}-${slug}.mdx`;

  // Create frontmatter
  const frontmatter = `---
title: "${title}"
startDate: ${date.toISOString()}
type: "smidgeon"
---

`;

  // Ensure year directory exists
  const yearDir = path.join(
    __dirname,
    "..",
    "src",
    "content",
    "smidgeons",
    year.toString(),
  );
  await fs.mkdir(yearDir, { recursive: true });

  // Write file
  const filePath = path.join(yearDir, filename);
  await fs.writeFile(filePath, frontmatter);

  console.log(`Created new smidgeon at: ${filePath}`);
}

createSmidgeon().catch(console.error);
