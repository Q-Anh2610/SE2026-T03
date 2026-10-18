import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  workers: 2,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/e2e.json' }]],
  use: {
    browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'mock-desktop', testMatch: 'mock.spec.ts', use: { baseURL: 'http://127.0.0.1:5193', viewport: { width: 1280, height: 900 } } },
    { name: 'mock-mobile', testMatch: 'mock.spec.ts', use: { baseURL: 'http://127.0.0.1:5193', viewport: { width: 390, height: 844 } } },
    { name: 'api-desktop', testMatch: 'api.spec.ts', use: { baseURL: 'http://127.0.0.1:5194', viewport: { width: 1280, height: 900 } } },
    { name: 'production-mobile', testMatch: 'api.spec.ts', use: { baseURL: 'http://127.0.0.1:5195', viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    { command: 'npm run dev -- --host 127.0.0.1 --port 5193 --strictPort', url: 'http://127.0.0.1:5193', reuseExistingServer: false },
    { command: 'npm run dev:api -- --host 127.0.0.1 --port 5194 --strictPort', url: 'http://127.0.0.1:5194', reuseExistingServer: false },
    { command: 'npm run preview -- --host 127.0.0.1 --port 5195 --strictPort', url: 'http://127.0.0.1:5195', reuseExistingServer: false },
  ],
})
