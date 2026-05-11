import { test, expect } from '@playwright/test'

const enableIndicator = async (page: import('@playwright/test').Page, label: string) => {
  await page.getByRole('button', { name: 'Add indicator' }).click()
  await page.getByRole('option', { name: label }).click()
  await expect(page.getByPlaceholder('Search indicators…')).not.toBeVisible()
}

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

  test('chip swatch opens color picker popover with hex input and presets', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')

    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await expect(swatch).toBeVisible()
    await swatch.click()

    const popover = page.locator('[data-radix-popper-content-wrapper]')
    await expect(popover).toBeVisible()

    const hexInput = popover.locator('input[type="text"]')
    await expect(hexInput).toBeVisible()
    const hexValue = await hexInput.inputValue()
    expect(hexValue).toMatch(/^#[0-9A-Fa-f]{6}$/)

    const presets = popover.locator('button')
    expect(await presets.count()).toBe(10)
  })

  test('selecting a preset color updates the chip swatch', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await swatch.click()

    const popover = page.locator('[data-radix-popper-content-wrapper]')
    await expect(popover).toBeVisible()
    const lastPreset = popover.locator('button').last()
    await lastPreset.click()

    const newColor = await swatch.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )
    expect(newColor).toBeTruthy()
  })

  test('indicator colors are deterministic across enable/disable', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    const color1 = await swatch.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )

    await page.getByRole('button', { name: 'Disable SMA(20)' }).click()
    await expect(page.getByRole('button', { name: 'Change color for SMA(20)' })).toHaveCount(0)

    await enableIndicator(page, 'SMA(20)')
    const color2 = await page
      .getByRole('button', { name: 'Change color for SMA(20)' })
      .evaluate((el) => (el as HTMLElement).style.backgroundColor)
    expect(color2).toBe(color1)
  })

  test('picked color is applied to the eCharts overlay series', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await swatch.click()

    const popover = page.locator('[data-radix-popper-content-wrapper]')
    await expect(popover).toBeVisible()
    const lastPreset = popover.locator('button').last()
    const targetHex = await lastPreset.getAttribute('title')
    expect(targetHex).toMatch(/^#[0-9A-Fa-f]{6}$/)
    await lastPreset.click()

    await expect
      .poll(async () =>
        page.evaluate((label) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const chart = (window as any).__ECHARTS_INSTANCE__
          if (!chart) return null
          const opt = chart.getOption()
          const match = (opt.series as Array<{ name?: string; lineStyle?: { color?: string } }>)
            .find((s) => s.name === label)
          return match?.lineStyle?.color ?? null
        }, 'SMA(20)'),
      )
      .toBe(targetHex)
  })

  test('color persists across page reload via localStorage', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await swatch.click()

    const popover = page.locator('[data-radix-popper-content-wrapper]')
    await expect(popover).toBeVisible()
    const lastPreset = popover.locator('button').last()
    const targetHex = await lastPreset.getAttribute('title')
    const targetBg = await lastPreset.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )
    await lastPreset.click()

    const stored = await page.evaluate(() => localStorage.getItem('indicator-colors'))
    expect(stored).toBeTruthy()
    expect(stored).toContain(targetHex!)

    await page.reload()
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()

    // After reload the chip won't be there (enabledIds is in-memory only).
    // Re-enable and verify the persisted color is applied to the new chip.
    await enableIndicator(page, 'SMA(20)')
    const swatchAfterReload = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await expect(swatchAfterReload).toBeVisible()
    const colorAfterReload = await swatchAfterReload.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )
    expect(colorAfterReload).toBe(targetBg)
  })
})
