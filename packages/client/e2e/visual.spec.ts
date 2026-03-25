import { test, expect } from '@playwright/test'

test.describe('Visual Regression', () => {
  test('runs page', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('table')).toBeVisible()
    // Wait for data to render
    await expect(page.getByText('EMACross-000').first()).toBeVisible()

    await expect(page).toHaveScreenshot('runs-page.png', {
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with no indicators', async ({ page }) => {
    await page.goto('/')
    await page.locator('table tbody tr').first().click()
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
    await page.locator('table tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    // Toggle SMA(20) on
    await page.getByRole('checkbox').nth(0).click()
    // Wait for indicator data to load and chart to re-render
    await page.waitForFunction(() => {
      const canvas = document.querySelector('[data-testid="chart-container"] canvas')
      return canvas !== null
    })
    // Small delay for eCharts to finish rendering the overlay line
    await page.waitForFunction(() => true, null, { timeout: 1000 }).catch(() => {})

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-sma-overlay.png', {
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with RSI panel', async ({ page }) => {
    await page.goto('/')
    await page.locator('table tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    // Toggle RSI(14) on
    await page.getByText('RSI(14)').click()
    // Wait for chart to grow (panel added)
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 600
    })

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-rsi-panel.png', {
      maxDiffPixelRatio: 0.01,
    })
  })

  test('chart with multiple panels', async ({ page }) => {
    await page.goto('/')
    await page.locator('table tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()

    // Toggle RSI and ATR
    await page.getByText('RSI(14)').click()
    await page.getByText('ATR(14)').click()
    // Wait for both panels
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 750
    })

    const chart = page.getByTestId('chart-container')
    await expect(chart).toHaveScreenshot('chart-multi-panel.png', {
      maxDiffPixelRatio: 0.01,
    })
  })
})
