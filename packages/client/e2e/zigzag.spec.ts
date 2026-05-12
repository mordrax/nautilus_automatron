import { test, expect, Page } from '@playwright/test'

// Enable ZigZag(0.1%) via the Add menu and wait for the indicator data to load
// and the chart series to render. The waitForResponse listener must be
// registered BEFORE the click — the indicator fetch can resolve before the
// listener is set up otherwise (race condition observed in CI).
const toggleZigZagAndWait = async (page: Page) => {
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/indicators?ids=') && resp.status() === 200,
    { timeout: 15_000 },
  )
  await page.getByRole('button', { name: 'Add indicator' }).click()
  await page.getByRole('option', { name: 'ZigZag(0.1%)' }).click()
  await expect(page.getByPlaceholder('Search indicators…')).not.toBeVisible()
  await responsePromise
  await page.waitForFunction(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return chart?.getOption()?.series?.some((s: any) => s.name?.includes('ZigZag'))
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

  test('ZigZag indicators appear in the Add menu Overlays group', async ({ page }) => {
    await page.getByRole('button', { name: 'Add indicator' }).click()
    await expect(page.getByRole('option', { name: 'ZigZag(0.1%)' })).toBeVisible()
    await expect(page.getByRole('option', { name: 'ZigZag(3%)' })).toBeVisible()
  })

  test('toggling ZigZag(0.1%) renders a sparse overlay line', async ({ page }) => {
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

    // Toggle off via the chip's Disable button
    await page.getByRole('button', { name: 'Disable ZigZag(0.1%)' }).click()
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
