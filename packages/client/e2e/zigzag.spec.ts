import { test, expect, Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { removeIndicator } from './helpers'

// Enable ZigZag via the new Add popover and wait for the indicator data to load
// and the chart series to render. The waitForResponse listener must be
// registered BEFORE the click — the indicator fetch can resolve before the
// listener is set up otherwise (race condition observed in CI).
const toggleZigZagAndWait = async (page: Page) => {
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/indicators') && resp.request().method() === 'POST' && resp.status() === 200,
    { timeout: 15_000 },
  )
  await page.getByTestId('add-indicator-button').click()
  await page.locator('[data-testid="indicator-type-option"]', { hasText: 'ZigZag' }).click()
  // Use a small threshold (0.001 = 0.1%) to ensure zigzag produces data on tick bars
  await page.getByTestId('param-input-threshold').fill('0.001')
  await page.getByTestId('param-form-submit').click()
  await expect(page.getByTestId('param-form-submit')).not.toBeVisible()
  await responsePromise
  // Wait until ZigZag series has non-null data points (response fetched + chart updated)
  await page.waitForFunction(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart?.getOption) return false
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const series = chart.getOption().series ?? []
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const zigzag = series.find((s: any) => s.name?.includes('ZigZag'))
    if (!zigzag) return false
    const data = zigzag.data ?? []
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return data.some((d: any) => d !== null && d !== undefined)
  }, { timeout: 10_000 })
}

const getSeriesNames = (page: Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart?.getOption) return []
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return chart.getOption().series?.map((s: any) => s.name) ?? []
  })

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

test.describe('ZigZag Indicator', () => {
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

  test('ZigZag indicator appears in the Add type list', async ({ page }) => {
    await page.getByTestId('add-indicator-button').click()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'ZigZag' })).toBeVisible()
    // Dismiss by clicking outside the popover
    await page.mouse.click(10, 10)
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'ZigZag' })).not.toBeVisible()
  })

  test('toggling ZigZag renders a sparse overlay line', async ({ page }) => {
    await toggleZigZagAndWait(page)

    const seriesInfo = await page.evaluate(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      if (!chart?.getOption) return null
      const option = chart.getOption()
      const series = option.series ?? []
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const zigzag = series.find((s: any) =>
        s.name && (s.name.includes('ZigZag') || s.name.includes('zigzag')),
      )
      if (!zigzag) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return { found: false as const, allNames: series.map((s: any) => s.name) }
      }
      const data = zigzag.data ?? []
      return {
        found: true as const,
        name: zigzag.name,
        type: zigzag.type,
        connectNulls: zigzag.connectNulls,
        totalPoints: data.length,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        nonNullCount: data.filter((d: any) => d !== null && d !== undefined).length,
      }
    })

    expect(seriesInfo).not.toBeNull()
    if (!seriesInfo!.found) {
      throw new Error(`ZigZag series not found. Available series: ${JSON.stringify(seriesInfo!.allNames)}`)
    }
    expect(seriesInfo!.type).toBe('line')
    expect(seriesInfo!.connectNulls).toBe(true)
    expect(seriesInfo!.nonNullCount).toBeGreaterThan(0)
    expect(seriesInfo!.nonNullCount).toBeLessThan(seriesInfo!.totalPoints)
  })

  test('ZigZag is an overlay and does not change chart height', async ({ page }) => {
    const chartContainer = page.getByTestId('chart-container')
    const initialBox = await chartContainer.boundingBox()
    expect(initialBox).not.toBeNull()

    await toggleZigZagAndWait(page)

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBe(initialBox!.height)
  })

  test('toggling ZigZag off removes the overlay', async ({ page }) => {
    // Toggle on
    await toggleZigZagAndWait(page)

    // Remove via the chip
    // Get the ZigZag chip label from the selector
    const selector = page.getByTestId('indicator-instance-selector')
    const zigzagChip = selector.locator('[data-testid="indicator-chip"]').filter({
      has: page.locator('[data-testid="indicator-chip-label"]').filter({ hasText: /ZigZag/ }),
    })
    await zigzagChip.getByTestId('indicator-chip-remove').click()

    await page.waitForFunction(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return !chart?.getOption()?.series?.some((s: any) => s.name?.includes('ZigZag'))
    }, { timeout: 10_000 })

    const names = await getSeriesNames(page)
    const hasZigZag = names.some((n: string) => n?.includes('ZigZag') || n?.includes('zigzag'))
    expect(hasZigZag).toBe(false)
  })
})
