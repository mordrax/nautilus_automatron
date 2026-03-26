import { defineConfig } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const testDataPath = path.resolve(__dirname, 'e2e/test-data/backtest_catalog')
const vitePort = Number(process.env.TEST_VITE_PORT ?? 5173)
const apiPort = Number(process.env.TEST_API_PORT ?? 8000)

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  reporter: [['html', { open: 'never' }]],

  use: {
    baseURL: `http://localhost:${vitePort}`,
    trace: 'retain-on-failure',
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
      command: `cd ${path.resolve(__dirname, '../server')} && NAUTILUS_STORE_PATH=${testDataPath} .venv/bin/python -m uvicorn server.main:app --port ${apiPort}`,
      port: apiPort,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: `VITE_PORT=${vitePort} VITE_API_URL=http://localhost:${apiPort} bun run dev`,
      port: vitePort,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
})
