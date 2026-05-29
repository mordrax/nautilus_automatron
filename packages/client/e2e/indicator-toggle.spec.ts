import { test, expect } from '@playwright/test'
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
  const tmpPath = viewerStatePath + '.tmp'
  if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath)
}

const smaSeriesPresent = (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const series = (chart?.getOption()?.series ?? []) as any[]
    return series.some((s) => typeof s?.name === 'string' && s.name.includes('SMA(20)'))
  })

test.describe('Indicator on/off toggle', () => {
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

  test('toggle hides/shows the indicator on the chart and persists across reload', async ({ page }) => {
    // Register listener before enableIndicator so we catch the debounced PUT (300ms after addInstance)
    const putViewerStatePromise = page.waitForResponse(
      (resp) => resp.url().includes('/viewer-state') && resp.request().method() === 'PUT',
      { timeout: 15_000 },
    )

    await enableIndicator(page, 'SMA')

    const chip = page.getByTestId('indicator-chip').filter({ hasText: 'SMA(20)' })
    await expect(chip).toBeVisible()
    await expect(chip).toHaveAttribute('data-enabled', 'true')

    await expect.poll(() => smaSeriesPresent(page)).toBe(true)

    await chip.getByTestId('indicator-chip-label').click()

    await expect(chip).toHaveAttribute('data-enabled', 'false')
    await expect(chip).toBeVisible()
    await expect.poll(() => smaSeriesPresent(page)).toBe(false)

    await chip.getByTestId('indicator-chip-label').click()
    await expect(chip).toHaveAttribute('data-enabled', 'true')
    await expect.poll(() => smaSeriesPresent(page)).toBe(true)

    await chip.getByTestId('indicator-chip-label').click()
    await expect(chip).toHaveAttribute('data-enabled', 'false')

    // Wait for viewer-state PUT to complete before reloading so the instance persists
    await putViewerStatePromise
    await page.reload()
    const chipAfterReload = page.getByTestId('indicator-chip').filter({ hasText: 'SMA(20)' })
    await expect(chipAfterReload).toBeVisible()
    await expect(chipAfterReload).toHaveAttribute('data-enabled', 'false')
    await expect.poll(() => smaSeriesPresent(page)).toBe(false)
  })
})
