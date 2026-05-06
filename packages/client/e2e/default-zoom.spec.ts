import { test, expect } from '@playwright/test'

const DEFAULT_VISIBLE_BARS = 500

const getZoom = (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart) return null
    const opt = chart.getOption()
    const zoom = opt?.dataZoom?.[0]
    const xAxis = opt?.xAxis?.[0]
    const total = Array.isArray(xAxis?.data) ? xAxis.data.length : 0
    return zoom
      ? { start: zoom.start as number, end: zoom.end as number, total }
      : null
  })

test.describe('Default chart zoom', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.locator('canvas').first()).toBeVisible()
    await page.waitForFunction(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      const opt = chart?.getOption()
      return Array.isArray(opt?.xAxis?.[0]?.data) && opt.xAxis[0].data.length > 0
    })
  })

  test('initial zoom shows the last 500 bars when dataset is larger', async ({ page }) => {
    const zoom = await getZoom(page)
    expect(zoom).not.toBeNull()
    expect(zoom!.total).toBeGreaterThan(DEFAULT_VISIBLE_BARS)

    expect(zoom!.end).toBe(100)

    const expectedStart = ((zoom!.total - DEFAULT_VISIBLE_BARS) / zoom!.total) * 100
    expect(zoom!.start).toBeCloseTo(expectedStart, 1)

    const visibleBars = ((zoom!.end - zoom!.start) / 100) * zoom!.total
    expect(Math.round(visibleBars)).toBe(DEFAULT_VISIBLE_BARS)
  })
})
