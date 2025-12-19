import { defineConfig, devices } from "@playwright/test";
import path from "path";

const FRONTEND_PORT = Number(process.env.PLAYWRIGHT_APP_PORT || 3300);
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${FRONTEND_PORT}`;
const reuseServer = process.env.CI ? false : true;
const reuseBackendServer = Boolean(process.env.REUSE_EXISTING_BACKEND);

export default defineConfig({
  testDir: "./playwright/tests",
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    extraHTTPHeaders: {
      "x-test-suite": "brain-universe",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `bash -lc "cd '${path.resolve("..")}' && ENABLE_TEST_FIXTURE_ENDPOINTS=1 BRAIN_GRAPH_FIXTURE=deterministic python api_server.py"`,
      url: `${BACKEND_ORIGIN}/health`,
      timeout: 120_000,
      reuseExistingServer: reuseBackendServer,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `PORT=${FRONTEND_PORT} NEXT_PUBLIC_API_URL=${BACKEND_ORIGIN} NEXT_PUBLIC_GRAPH_TEST_HOOKS=1 npm run dev`,
      url: `${baseURL}/brain/universe`,
      timeout: 120_000,
      reuseExistingServer: reuseServer,
    },
  ],
});

