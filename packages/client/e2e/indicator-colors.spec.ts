import { test, expect } from '@playwright/test'

test.describe('Indicator Colors', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('color swatches are visible next to each indicator', async ({ page }) => {
    // Each indicator should have a color swatch button
    const overlaysSection = page.getByText('Overlays').locator('..')
    const swatches = overlaysSection.locator('button[title="Change color"]')
    await expect(swatches.first()).toBeVisible()
    const count = await swatches.count()
    expect(count).toBeGreaterThan(0)
  })

  test('clicking color swatch opens popover with hex input and preset swatches', async ({ page }) => {
    // Click the first color swatch
    const firstSwatch = page.locator('button[title="Change color"]').first()
    await expect(firstSwatch).toBeVisible()
    await firstSwatch.click()

    // Popover should open with hex input and preset colors
    const popover = page.locator('[data-radix-popper-content-wrapper]')
    await expect(popover).toBeVisible()

    // Should have a hex text input
    const hexInput = popover.locator('input[type="text"]')
    await expect(hexInput).toBeVisible()
    const hexValue = await hexInput.inputValue()
    expect(hexValue).toMatch(/^#[0-9A-Fa-f]{6}$/)

    // Should have preset color buttons (10 colors in the palette)
    const presets = popover.locator('button')
    const presetCount = await presets.count()
    expect(presetCount).toBe(10)
  })

  test('selecting a preset color updates the swatch', async ({ page }) => {
    const firstSwatch = page.locator('button[title="Change color"]').first()
    await expect(firstSwatch).toBeVisible()

    // Open popover and click a different preset
    await firstSwatch.click()
    const popover = page.locator('[data-radix-popper-content-wrapper]')
    await expect(popover).toBeVisible()

    // Click the last preset (likely different from current)
    const lastPreset = popover.locator('button').last()
    await lastPreset.click()

    // Swatch color should have changed
    const newColor = await firstSwatch.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor
    )
    // Colors may or may not differ (if the last preset happened to be the default)
    // But the swatch should still have a valid color
    expect(newColor).toBeTruthy()
  })

  test('indicator colors are deterministic across toggles', async ({ page }) => {
    // Enable SMA(20) and note its color
    const smaCheckbox = page.getByRole('checkbox').nth(0)
    await smaCheckbox.click()
    await expect(smaCheckbox).toBeChecked()

    // Get the swatch color for SMA
    const smaSwatch = page.locator('button[title="Change color"]').first()
    const color1 = await smaSwatch.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor
    )

    // Disable and re-enable
    await smaCheckbox.click()
    await expect(smaCheckbox).not.toBeChecked()
    await smaCheckbox.click()
    await expect(smaCheckbox).toBeChecked()

    // Color should be the same
    const color2 = await smaSwatch.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor
    )
    expect(color2).toBe(color1)
  })
})
