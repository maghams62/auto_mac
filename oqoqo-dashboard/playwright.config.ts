import { defineConfig } from "@playwright/test";

const port = process.env.PLAYWRIGHT_PORT ?? "3100";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./playwright",
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  use: {
    baseURL,
    video: "off",
    screenshot: "off",
    trace: "off",
  },
  webServer: {
    command: "npm run dev",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      ...process.env,
      GRAPH_MODE: "synthetic",
      ISSUE_MODE: "synthetic",
      OQOQO_MODE: "synthetic",
      NEXT_PUBLIC_OQOQO_MODE: "synthetic",
    },
  },
});


