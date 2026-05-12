import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { enableIndicator, removeIndicator } from './helpers'

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
  const tmpPath = viewerStatePath + '.tmp'
  if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath)
}

test.describe('Indicator Colors', () => {
  test.beforeEach(async ({ page }) => {
    clearViewerState()
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test.afterEach(() => {
    clearViewerState()
  })

  test('chip swatch opens color picker popover with hex input and presets', async ({ page }) => {
    await enableIndicator(page, 'SMA')

    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await expect(swatch).toBeVisible()
    await swatch.click()

    // Use specific locator: the color picker has an input[type="text"] for hex
    const popover = page.locator('[data-radix-popper-content-wrapper]').filter({ has: page.locator('input[type="text"]') })
    await expect(popover).toBeVisible()

    const hexInput = popover.locator('input[type="text"]')
    await expect(hexInput).toBeVisible()
    const hexValue = await hexInput.inputValue()
    expect(hexValue).toMatch(/^#[0-9A-Fa-f]{6}$/)

    const presets = popover.locator('button')
    expect(await presets.count()).toBe(10)
  })

  test('selecting a preset color updates the chip swatch', async ({ page }) => {
    await enableIndicator(page, 'SMA')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await swatch.click()

    // Use a more specific locator: the color picker popover contains a text input (hex)
    const popover = page.locator('[data-radix-popper-content-wrapper]').filter({ has: page.locator('input[type="text"]') })
    await expect(popover).toBeVisible()
    const lastPreset = popover.locator('button').last()
    await lastPreset.click()

    const newColor = await swatch.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )
    expect(newColor).toBeTruthy()
  })

  test('picked color is applied to the eCharts overlay series', async ({ page }) => {
    await enableIndicator(page, 'SMA')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await swatch.click()

    const popover = page.locator('[data-radix-popper-content-wrapper]').filter({ has: page.locator('input[type="text"]') })
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
    // Register the PUT response listener before adding the indicator
    // (the 300ms debounce means it fires soon after; listening early avoids a race)
    const putViewerStatePromise = page.waitForResponse(
      resp => resp.url().includes('/viewer-state') && resp.request().method() === 'PUT',
      { timeout: 15_000 },
    )

    await enableIndicator(page, 'SMA')
    const swatch = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await swatch.click()

    const popover = page.locator('[data-radix-popper-content-wrapper]').filter({ has: page.locator('input[type="text"]') })
    await expect(popover).toBeVisible()
    const lastPreset = popover.locator('button').last()
    const targetHex = await lastPreset.getAttribute('title')
    const targetBg = await lastPreset.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )
    await lastPreset.click()

    const stored = await page.evaluate(() => localStorage.getItem('indicator-colors-v2'))
    expect(stored).toBeTruthy()
    expect(stored).toContain(targetHex!)

    // Wait for the PUT viewer-state to complete before reloading
    await putViewerStatePromise
    await page.reload()
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()

    // After reload, the chip is restored from viewer-state — color should still be the custom one
    const swatchAfterReload = page.getByRole('button', { name: 'Change color for SMA(20)' })
    await expect(swatchAfterReload).toBeVisible()
    const colorAfterReload = await swatchAfterReload.evaluate(
      (el) => (el as HTMLElement).style.backgroundColor,
    )
    expect(colorAfterReload).toBe(targetBg)
  })

  test('removing indicator chip hides the color swatch', async ({ page }) => {
    await enableIndicator(page, 'SMA')
    await expect(page.getByRole('button', { name: 'Change color for SMA(20)' })).toBeVisible()

    await removeIndicator(page, 'SMA(20)')
    await expect(page.getByRole('button', { name: 'Change color for SMA(20)' })).toHaveCount(0)
  })
})
