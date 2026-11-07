import { defineConfig } from '@playwright/test'

const api = process.env.TEXT_SEARCH_API_URL
if (!api || !process.env.TEXT_SEARCH_CONTROL_URL) {
  throw new Error('Run via scripts/verify_text_search_integration.py with a disposable test database.')
}
const port = process.env.TEXT_SEARCH_UI_PORT

export default defineConfig({
  testDir: './tests/semantic',
  outputDir: 'playwright-report/semantic',
  workers: 1,
  maxFailures: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'semantic-desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'semantic-mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: `npm run dev:api -- --host 127.0.0.1 --port ${port} --strictPort`,
    cwd: process.env.TEXT_SEARCH_FRONTEND_DIR,
    env: { VITE_API_BASE_URL: api },
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  },
})
