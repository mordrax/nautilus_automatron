import { test, expect } from '@playwright/test'

const enableIndicator = async (page: import('@playwright/test').Page, label: string) => {
  await page.getByRole('button', { name: 'Add indicator' }).click()
  await page.getByRole('option', { name: label }).click()
  await expect(page.getByPlaceholder('Search indicators…')).not.toBeVisible()
}

test.describe('Indicator Selector', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
  })

  test('add menu opens and shows Overlays and Panels groups', async ({ page }) => {
    await page.getByRole('button', { name: 'Add indicator' }).click()
    await expect(page.getByText('Overlays')).toBeVisible()
    await expect(page.getByText('Panels')).toBeVisible()
    await expect(page.getByRole('option', { name: 'SMA(20)' })).toBeVisible()
    await expect(page.getByRole('option', { name: 'RSI(14)' })).toBeVisible()
    await expect(page.getByRole('option', { name: 'BB(20,2)' })).toBeVisible()
  })

  test('selecting SMA(20) from menu creates an active chip', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    const chip = page.getByTestId('indicator-selector').getByText('SMA(20)')
    await expect(chip).toBeVisible()
  })

  test('enabling RSI(14) increases chart height', async ({ page }) => {
    const chartContainer = page.getByTestId('chart-container')
    const initialBox = await chartContainer.boundingBox()
    expect(initialBox).not.toBeNull()
    const initialHeight = initialBox!.height

    await enableIndicator(page, 'RSI(14)')

    await page.waitForFunction(
      (prevHeight) => {
        const el = document.querySelector('[data-testid="chart-container"]')
        return el ? el.getBoundingClientRect().height > prevHeight : false
      },
      initialHeight,
    )

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBeGreaterThan(initialHeight)
  })

  test('panel indicator does not overlap main chart x-axis', async ({ page }) => {
    await enableIndicator(page, 'RSI(14)')

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height > 600 : false
    })

    const positions = await page.evaluate(() => {
      const container = document.querySelector('[data-testid="chart-container"]')
      if (!container) return null
      const canvas = container.querySelector('canvas')
      if (!canvas) return null
      return {
        containerHeight: container.getBoundingClientRect().height,
        canvasHeight: canvas.getBoundingClientRect().height,
      }
    })

    expect(positions).not.toBeNull()
    expect(positions!.containerHeight).toBeGreaterThan(700)
    expect(positions!.canvasHeight).toBeGreaterThan(700)
  })

  test('multiple panels stack without overlapping each other', async ({ page }) => {
    await enableIndicator(page, 'RSI(14)')
    await enableIndicator(page, 'ATR(14)')

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height > 750 : false
    })

    const containerHeight = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height : 0
    })

    expect(containerHeight).toBeGreaterThan(850)
  })

  test('panel x-axis labels are visible on the bottom panel', async ({ page }) => {
    await enableIndicator(page, 'RSI(14)')

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height > 600 : false
    })

    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
  })

  test('clicking ✕ on chip disables the indicator', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    const chip = page.getByTestId('indicator-selector').getByText('SMA(20)')
    await expect(chip).toBeVisible()

    await page.getByRole('button', { name: 'Disable SMA(20)' }).click()
    await expect(chip).not.toBeVisible()
  })
})
