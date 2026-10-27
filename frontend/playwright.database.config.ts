import { defineConfig } from '@playwright/test'

const api = process.env.ASSET_API_TEST_URL
if (!api) throw new Error('Run via python -m scripts.verify_asset_api --ui with TEST_DATABASE_URL.')
const port = process.env.ASSET_API_UI_PORT || '5199'

export default defineConfig({
  testDir: './tests/database',
  outputDir: 'playwright-report/database',
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'database-desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'database-mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: `npm run dev:api -- --host 127.0.0.1 --port ${port} --strictPort`,
    env: { VITE_API_BASE_URL: api },
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  },
})
