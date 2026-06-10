import { defineConfig } from "vitepress";
import { fileURLToPath } from "node:url";

const docsSiteRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  title: "Vocaloid Title Search Docs",
  description: "Development and operations documentation",
  srcDir: "../docs",
  cleanUrls: true,
  ignoreDeadLinks: false,
  metaChunk: true,
  head: [
    ["meta", { name: "robots", content: "noindex,nofollow,noarchive" }],
  ],
  vite: {
    resolve: {
      alias: {
        vue: `${docsSiteRoot}/node_modules/vue`,
        "vue/server-renderer": `${docsSiteRoot}/node_modules/vue/server-renderer/index.mjs`,
        "@vue/server-renderer": `${docsSiteRoot}/node_modules/@vue/server-renderer/dist/server-renderer.esm-bundler.js`,
      },
    },
  },
  themeConfig: {
    nav: [
      { text: "Guide", link: "/" },
      { text: "Quality", link: "/quality-gates" },
      { text: "Operations", link: "/operations" },
    ],
    sidebar: [
      {
        text: "Start Here",
        items: [
          { text: "Home", link: "/" },
          { text: "Documentation Guide", link: "/README" },
          { text: "Concepts", link: "/concepts" },
          { text: "Usage", link: "/usage" },
        ],
      },
      {
        text: "Development",
        items: [
          { text: "Project Structure", link: "/project-structure" },
          { text: "Testing", link: "/testing" },
          { text: "Frontend UI", link: "/frontend-ui" },
          { text: "Web API", link: "/web-api" },
          { text: "CLI Reference", link: "/cli-reference" },
        ],
      },
      {
        text: "Data",
        items: [
          { text: "Data Model", link: "/data-model" },
          { text: "Detail Extraction", link: "/detail-extraction" },
          { text: "Extraction Algorithm", link: "/detail-extraction-algorithm" },
        ],
      },
      {
        text: "Operations",
        items: [
          { text: "Operations Runbook", link: "/operations" },
          { text: "Production Design", link: "/production" },
          { text: "Quality Gates", link: "/quality-gates" },
        ],
      },
      {
        text: "Cloudflare",
        items: [
          { text: "Serverless Architecture", link: "/cloudflare-serverless" },
          { text: "Infrastructure", link: "/infrastructure" },
          { text: "Cloudflare DNS", link: "/cloudflare-dns" },
        ],
      },
      {
        text: "Maintenance",
        items: [
          { text: "Repository Privacy", link: "/repository-privacy" },
          { text: "Documentation Quality", link: "/documentation-quality" },
          { text: "Development Backlog", link: "/development-backlog" },
          { text: "Documentation Backlog", link: "/documentation-improvement-backlog" },
        ],
      },
    ],
    search: {
      provider: "local",
    },
  },
});
