import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/integration",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:4175", trace: "retain-on-failure" },
  webServer: [
    {
      command: "../.venv/bin/python ../tools/prepare_integration_db.py && cd ../cloudflare/worker && ./node_modules/.bin/wrangler dev --local --config test/wrangler.integration.toml --persist-to .wrangler/integration --port 8789",
      url: "http://127.0.0.1:8789/health", timeout: 120_000, reuseExistingServer: false,
    },
    {
      command: "yarn build && yarn preview --port 4175 --strictPort",
      env: { API_PROXY_TARGET: "http://127.0.0.1:8789" },
      url: "http://127.0.0.1:4175", timeout: 120_000, reuseExistingServer: false,
    },
  ],
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 5"] } },
  ],
});
