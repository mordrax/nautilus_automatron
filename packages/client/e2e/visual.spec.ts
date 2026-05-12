import { test, expect, Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { enableIndicator } from './helpers'

const __dirname = path.dirname(new URL(import.meta.url).pathname)
const RUN_ID = '41a1f019-a7fd-44cd-9c7a-bf41e5b0bf31'
const viewerStatePath = path.resolve(
  __dirname,
  'test-data/backtest_catalog/backtest',
  RUN_ID,
  'viewer_state.json',
)

const clearViewerState = () => {
  if (fs.existsSync(viewerStatePath)) fs.unlinkSync(viewerStatePath)
}

test.describe('Visual Regression', () => {
  test.beforeEach(() => {
    clearViewerState()
  })

  test.afterEach(() => {
    clearViewerState()
  })

  test('runs page', async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    await expect(runsSection.locator('.tabulator')).toBeVisible()
    // Wait for data to render
    await expect(page.getByText('EMACross-000').first()).toBeVisible()

    await expect(page).toHaveScreenshot('runs-page.png', {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with no indicators', async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    await runsSection.locator('.tabulator-row').first().locator('button', { hasText: 'View' }).click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for chart to render with data
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-no-indicators.png', {
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with SMA overlay', async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    await runsSection.locator('.tabulator-row').first().locator('button', { hasText: 'View' }).click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    // Enable SMA via the new Add popover and wait for chart re-render
    await enableIndicator(page, 'SMA')
    await page.waitForFunction(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return chart?.getOption()?.series?.some((s: any) => s.name?.includes('SMA'))
    }, { timeout: 10_000 })

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-sma-overlay.png', {
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with RSI panel', async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    await runsSection.locator('.tabulator-row').first().locator('button', { hasText: 'View' }).click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    // Enable RSI via the new Add popover and wait for chart to grow (panel added)
    await enableIndicator(page, 'RSI')
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 600
    }, { timeout: 10_000 })

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-rsi-panel.png', {
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with multiple panels', async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    await runsSection.locator('.tabulator-row').first().locator('button', { hasText: 'View' }).click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    // Enable RSI and ATR via the new Add popover
    await enableIndicator(page, 'RSI')
    await enableIndicator(page, 'ATR')
    // Wait for both panels
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 750
    }, { timeout: 10_000 })

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-multi-panel.png', {
      maxDiffPixelRatio: 0.01,
    })
  })
})
