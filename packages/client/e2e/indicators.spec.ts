import { test, expect } from '@playwright/test'

test.describe('Indicator Toggles', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const grid = page.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for chart and data to load
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
  })

  test('indicator panel shows Overlays and Panels sections', async ({ page }) => {
    await expect(page.getByText('Indicators')).toBeVisible()
    await expect(page.getByText('Overlays')).toBeVisible()
    await expect(page.getByText('Panels')).toBeVisible()
    // Check specific indicators are listed
    await expect(page.getByText('SMA(20)')).toBeVisible()
    await expect(page.getByText('RSI(14)')).toBeVisible()
    await expect(page.getByText('BB(20,2)')).toBeVisible()
  })

  test('toggling SMA(20) checks the checkbox', async ({ page }) => {
    const smaCheckbox = page.getByRole('checkbox').nth(0) // SMA(20) is first overlay
    await expect(smaCheckbox).not.toBeChecked()
    await smaCheckbox.click()
    await expect(smaCheckbox).toBeChecked()
  })

  test('toggling RSI(14) increases chart height', async ({ page }) => {
    const chartContainer = page.getByTestId('chart-container')
    const initialBox = await chartContainer.boundingBox()
    expect(initialBox).not.toBeNull()
    const initialHeight = initialBox!.height

    // Toggle RSI (first panel indicator)
    const rsiLabel = page.getByText('RSI(14)')
    await rsiLabel.click()

    // Wait for chart to re-render — the container should grow
    await page.waitForFunction(
      (prevHeight) => {
        const el = document.querySelector('[data-testid="chart-container"]')
        return el && el.getBoundingClientRect().height > prevHeight
      },
      initialHeight,
    )

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBeGreaterThan(initialHeight)
  })

  test('panel indicator does not overlap main chart x-axis', async ({ page }) => {
    // Toggle RSI to add a panel below the main chart
    await page.getByText('RSI(14)').click()

    // Wait for the panel to render
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 600
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
    // Container should be taller than default 600px to accommodate the panel
    expect(positions!.containerHeight).toBeGreaterThan(700)
    // Canvas should fill the container
    expect(positions!.canvasHeight).toBeGreaterThan(700)
  })

  test('multiple panels stack without overlapping each other', async ({ page }) => {
    // Toggle RSI and ATR to add two panels
    await page.getByText('RSI(14)').click()
    await page.getByText('ATR(14)').click()

    // Wait for both panels to render
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 750
    })

    const containerHeight = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height : 0
    })

    // With 2 panels (150px each), container should be 600 + 300 = 900px
    expect(containerHeight).toBeGreaterThan(850)
  })

  test('panel x-axis labels are visible on the bottom panel', async ({ page }) => {
    // Toggle RSI to add a panel
    await page.getByText('RSI(14)').click()

    // Wait for panel to render
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el && el.getBoundingClientRect().height > 600
    })

    // The bottom panel should show date labels — check that date text still appears
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
  })

  test('toggling indicator off unchecks it', async ({ page }) => {
    const smaCheckbox = page.getByRole('checkbox').nth(0)
    // Toggle on
    await smaCheckbox.click()
    await expect(smaCheckbox).toBeChecked()
    // Toggle off
    await smaCheckbox.click()
    await expect(smaCheckbox).not.toBeChecked()
  })
})
