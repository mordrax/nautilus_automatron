import { test, expect } from '@playwright/test'

/** Read dataZoom start/end from the echarts instance exposed on window. */
const getZoom = (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart) return null
    const opt = chart.getOption()
    const zoom = opt?.dataZoom?.[0]
    return zoom ? { start: zoom.start as number, end: zoom.end as number } : null
  })

/** Poll until zoom width is less than the given threshold. */
const waitForZoomIn = async (page: import('@playwright/test').Page, maxWidth = 99) => {
  await page.waitForFunction(
    (mw) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      if (!chart) return false
      const opt = chart.getOption()
      const zoom = opt?.dataZoom?.[0]
      return zoom && (zoom.end - zoom.start) < mw
    },
    maxWidth,
    { timeout: 10_000 },
  )
}

test.describe('Trade Zoom', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.locator('canvas').first()).toBeVisible()
  })

  test('selecting a trade zooms the chart on first click', async ({ page }) => {
    // Click Next to select trade #2
    await page.getByRole('button', { name: /Next/ }).click()
    await expect(page.getByText(/Trade #2/).first()).toBeVisible()

    // Wait for chart to zoom in
    await waitForZoomIn(page)
    const zoom = await getZoom(page)

    expect(zoom).not.toBeNull()
    expect(zoom!.end - zoom!.start).toBeLessThan(100)
  })

  test('selecting a different trade re-centers the chart', async ({ page }) => {
    // Select trade #2
    await page.getByRole('button', { name: /Next/ }).click()
    await expect(page.getByText(/Trade #2/).first()).toBeVisible()
    await waitForZoomIn(page)
    const zoom2 = await getZoom(page)

    // Jump to a distant trade via the table (trade #20)
    const tradesTable = page.locator('table')
    const distantRow = tradesTable.locator('tbody tr').nth(19)
    await expect(distantRow).toBeVisible()
    await distantRow.click()
    await expect(page.getByText(/Trade #20/).first()).toBeVisible()

    // Wait for zoom center to shift
    await page.waitForFunction(
      (prevStart) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const chart = (window as any).__ECHARTS_INSTANCE__
        if (!chart) return false
        const opt = chart.getOption()
        const zoom = opt?.dataZoom?.[0]
        return zoom && Math.abs(zoom.start - prevStart) > 1
      },
      zoom2!.start,
      { timeout: 10_000 },
    )
    const zoom20 = await getZoom(page)

    // Both should be zoomed in
    expect(zoom2!.end - zoom2!.start).toBeLessThan(100)
    expect(zoom20!.end - zoom20!.start).toBeLessThan(100)

    // Center should have shifted significantly
    const mid2 = (zoom2!.start + zoom2!.end) / 2
    const mid20 = (zoom20!.start + zoom20!.end) / 2
    expect(Math.abs(mid20 - mid2)).toBeGreaterThan(5)
  })

  test('clicking a trade in the table zooms the chart', async ({ page }) => {
    // Click 5th trade row
    const tradesTable = page.locator('table')
    const fifthRow = tradesTable.locator('tbody tr').nth(4)
    await expect(fifthRow).toBeVisible()
    await fifthRow.click()

    await expect(page.getByText(/Trade #5/).first()).toBeVisible()
    await waitForZoomIn(page)
    const zoom = await getZoom(page)

    expect(zoom).not.toBeNull()
    expect(zoom!.end - zoom!.start).toBeLessThan(100)
  })
})
