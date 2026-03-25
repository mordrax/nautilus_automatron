import { defineConfig } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const testDataPath = path.resolve(__dirname, 'e2e/test-data/backtest_catalog')

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'headless',
      use: {
        headless: true,
        channel: 'chromium',
      },
    },
    {
      name: 'headed',
      use: {
        headless: false,
        channel: 'chromium',
        launchOptions: { slowMo: 1000 },
        viewport: { width: 1400, height: 900 },
      },
    },
  ],

  webServer: [
    {
      command: `NAUTILUS_STORE_PATH=${testDataPath} cd ${path.resolve(__dirname, '../server')} && .venv/bin/python -m uvicorn server.main:app --port 8000`,
      port: 8000,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'bun run dev',
      port: 5173,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
})
