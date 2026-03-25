import { test, expect } from '@playwright/test'

test.describe('Indicator Toggles', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await table.locator('tbody tr').first().click()
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
