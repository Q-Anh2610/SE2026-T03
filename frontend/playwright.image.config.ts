import { defineConfig } from '@playwright/test'

const live = !!process.env.IMAGE_SMOKE_API_URL
export default defineConfig({
  testDir: './tests/e2e', testMatch: 'image-live.spec.ts', workers: 1,
  reporter: [['list'], ['json', { outputFile: 'test-results/image-live.json' }]],
  use: { channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome', baseURL: 'http://127.0.0.1:5294', trace: 'retain-on-failure' },
  projects: [
    { name: 'image-desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'image-mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: { command: 'npm run dev:api -- --host 127.0.0.1 --port 5294 --strictPort', url: 'http://127.0.0.1:5294', reuseExistingServer: false,
    env: live ? { VITE_API_BASE_URL: process.env.IMAGE_SMOKE_API_URL! } : {} },
})
