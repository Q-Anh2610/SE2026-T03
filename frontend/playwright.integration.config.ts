import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'

// Uses the repository's merged backend/ by default; override only for local debugging.
const backend = resolve(process.env.BACKEND_CONTRACT_DIR || '../backend')
const python = process.env.BACKEND_PYTHON || 'python3'

export default defineConfig({
  testDir: './tests/integration',
  outputDir: 'playwright-report/integration',
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5197', browserName: 'chromium', channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome', trace: 'retain-on-failure' },
  projects: [
    { name: 'backend-desktop', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'backend-mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    { command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 5196`, cwd: backend,
      env: { APP_ENV: 'test', APP_DEBUG: 'false', APP_MOCK_API_ENABLED: 'true', APP_ASSET_LIST_SOURCE: 'fixture', APP_CORS_ORIGINS: '["http://127.0.0.1:5197"]' },
      url: 'http://127.0.0.1:5196/healthz', reuseExistingServer: false },
    { command: 'npm run dev:api -- --host 127.0.0.1 --port 5197 --strictPort',
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:5196' }, url: 'http://127.0.0.1:5197', reuseExistingServer: false },
  ],
})
