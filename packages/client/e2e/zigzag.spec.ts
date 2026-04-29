import { test, expect, Page } from '@playwright/test'

const waitForIndicatorData = async (page: Page) => {
  // Wait for the indicator API response
  await page.waitForResponse(
    (resp) => resp.url().includes('/indicators?ids=') && resp.status() === 200,
    { timeout: 15_000 },
  )
  // Wait for chart to merge the new series
  await page.waitForFunction(() => {
    const chart = (window as any).__ECHARTS_INSTANCE__
    return chart?.getOption()?.series?.some((s: any) => s.name?.includes('ZigZag'))
  }, { timeout: 10_000 })
}

const getSeriesNames = (page: Page) =>
  page.evaluate(() => {
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart?.getOption) return []
    return chart.getOption().series?.map((s: any) => s.name) ?? []
  })

test.describe('ZigZag Indicator', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('ZigZag indicators appear in the Overlays section', async ({ page }) => {
    await expect(page.getByText('ZigZag(0.1%)')).toBeVisible()
    await expect(page.getByText('ZigZag(3%)')).toBeVisible()
  })

  test('toggling ZigZag(0.1%) renders a sparse overlay line', async ({ page }) => {
    await page.getByText('ZigZag(0.1%)').click()
    await waitForIndicatorData(page)

    const seriesInfo = await page.evaluate(() => {
      const chart = (window as any).__ECHARTS_INSTANCE__
      if (!chart?.getOption) return null
      const option = chart.getOption()
      // Find zigzag series — label is "ZigZag(0.1%)"
      const series = option.series ?? []
      const zigzag = series.find((s: any) =>
        s.name && (s.name.includes('ZigZag') || s.name.includes('zigzag')),
      )
      if (!zigzag) {
        // Return all series names for debugging
        return { found: false, allNames: series.map((s: any) => s.name) }
      }
      const data = zigzag.data ?? []
      return {
        found: true,
        name: zigzag.name,
        type: zigzag.type,
        connectNulls: zigzag.connectNulls,
        totalPoints: data.length,
        nonNullCount: data.filter((d: any) => d !== null && d !== undefined).length,
      }
    })

    expect(seriesInfo).not.toBeNull()
    if (!seriesInfo!.found) {
      // Fail with helpful debug info
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

    await page.getByText('ZigZag(0.1%)').click()
    await waitForIndicatorData(page)

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBe(initialBox!.height)
  })

  test('toggling ZigZag off removes the overlay', async ({ page }) => {
    // Toggle on
    await page.getByText('ZigZag(0.1%)').click()
    await waitForIndicatorData(page)

    // Toggle off
    await page.getByText('ZigZag(0.1%)').click()
    // Wait for chart to remove the series
    await page.waitForFunction(() => {
      const chart = (window as any).__ECHARTS_INSTANCE__
      return !chart?.getOption()?.series?.some((s: any) => s.name?.includes('ZigZag'))
    }, { timeout: 10_000 })

    const names = await getSeriesNames(page)
    const hasZigZag = names.some((n: string) => n?.includes('ZigZag') || n?.includes('zigzag'))
    expect(hasZigZag).toBe(false)
  })
})
