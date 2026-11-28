import { defineConfig } from '@playwright/test'

const origin = process.env.E2E_STACK_URL
if (!origin || !process.env.E2E_STACK_INPUT) {
  throw new Error('Cần E2E_STACK_URL và E2E_STACK_INPUT; xem docs/guides/e2e-search-w7.md.')
}
const url = new URL(origin)
if (!['127.0.0.1', 'localhost'].includes(url.hostname) || url.username || url.password || url.search || url.hash) {
  throw new Error('Chỉ chạy trên stack local riêng, URL không chứa credentials.')
}

export default defineConfig({
  testDir: './tests/stack',
  outputDir: 'test-results/stack',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/stack-report.json' }]],
  use: {
    baseURL: origin,
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'stack-desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'stack-mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
})
