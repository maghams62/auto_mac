/**
 * Playwright configuration for UI regression tests
 *
 * Configures browser settings, test execution, and reporting for
 * end-to-end UI testing of the conversational interface.
 */

import { defineConfig, devices } from '@playwright/test';

/**
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './tests/ui',

  /* Run tests in files in parallel */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,

  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,

  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,

  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: process.env.CI
    ? [['html'], ['junit', { outputFile: 'results.xml' }]]
    : [['html'], ['list']],

  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.UI_BASE_URL || 'http://localhost:3000',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Take screenshot only when test fails */
    screenshot: 'only-on-failure',

    /* Record video only when test fails */
    video: 'retain-on-failure',

    /* Timeout for individual actions */
    actionTimeout: 10000,

    /* Timeout for individual tests */
    testTimeout: 60000, // 60 seconds for e2e tests
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        /* Custom settings for e2e tests */
        viewport: { width: 1280, height: 720 },
        ignoreHTTPSErrors: true,
      },
    },

    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        /* Custom settings for e2e tests */
        viewport: { width: 1280, height: 720 },
        ignoreHTTPSErrors: true,
      },
    },

    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        /* Custom settings for e2e tests */
        viewport: { width: 1280, height: 720 },
        ignoreHTTPSErrors: true,
      },
    },

    /* Test against mobile viewports. */
    {
      name: 'Mobile Chrome',
      use: {
        ...devices['Pixel 5'],
        /* Custom settings for mobile e2e tests */
        ignoreHTTPSErrors: true,
      },
    },

    {
      name: 'Mobile Safari',
      use: {
        ...devices['iPhone 12'],
        /* Custom settings for mobile e2e tests */
        ignoreHTTPSErrors: true,
      },
    },
  ],

  /* Run your local dev server before starting the tests */
  webServer: process.env.CI ? undefined : [
    {
      command: 'cd ../.. && python api_server.py',
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 120000, // 2 minutes
    },
    {
      command: 'cd ../../frontend && npm run dev',
      port: 3000,
      reuseExistingServer: !process.env.CI,
      timeout: 120000, // 2 minutes
    },
  ],

  /* Global setup and teardown */
  globalSetup: require.resolve('./global-setup'),
  globalTeardown: require.resolve('./global-teardown'),

  /* Test results and artifacts */
  outputDir: './test-results',
  snapshotDir: './snapshots',

  /* Configure expect timeouts */
  expect: {
    timeout: 10000,
  },
});
