import { test, expect, Page } from '@playwright/test'

const enableIndicator = async (page: Page, label: string) => {
  await page.getByRole('button', { name: 'Add indicator' }).click()
  await page.getByRole('option', { name: label }).click()
  await expect(page.getByPlaceholder('Search indicators…')).not.toBeVisible()
}

test.describe('Visual Regression', () => {
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

    // Enable SMA(20) via the Add menu and wait for chart re-render
    await enableIndicator(page, 'SMA(20)')
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

    // Enable RSI(14) via the Add menu and wait for chart to grow (panel added)
    await enableIndicator(page, 'RSI(14)')
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

    // Enable RSI and ATR via the Add menu
    await enableIndicator(page, 'RSI(14)')
    await enableIndicator(page, 'ATR(14)')
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
