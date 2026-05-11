import { test, expect } from '@playwright/test'

const getZoom = (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart) return null
    const opt = chart.getOption()
    const zoom = opt?.dataZoom?.[0]
    return zoom ? { start: zoom.start as number, end: zoom.end as number } : null
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

  test('chart opens with a default window applied (not full range)', async ({ page }) => {
    const zoom = await getZoom(page)
    expect(zoom).not.toBeNull()
    expect(zoom!.end).toBe(100)
    expect(zoom!.start).toBeGreaterThan(0)
  })
})
