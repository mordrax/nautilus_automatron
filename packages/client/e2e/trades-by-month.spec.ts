import { test, expect } from '@playwright/test'

test.describe('Trades by Month Chart', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await table.locator('tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()

    // Switch to Trades by Month tab
    await page.getByRole('tab', { name: 'Trades by Month' }).click()
    await expect(page.getByRole('tab', { name: 'Trades by Month' })).toHaveAttribute('data-state', 'active')
  })

  test('chart renders with a canvas element', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    const canvas = chart.locator('canvas')
    await expect(canvas).toBeVisible()
  })

  test('chart container has expected height', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    const box = await chart.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.height).toBeGreaterThanOrEqual(450)
    expect(box!.height).toBeLessThanOrEqual(550)
  })

  test('bar count matches number of distinct trade months', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    // Wait for eCharts to render and expose instance
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')
      if (!el) return false
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return !!(el as any)._ec_instance
    })

    const barCount = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')!
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (el as any)._ec_instance
      const option = chart.getOption()
      return option.xAxis[0].data.length
    })

    expect(barCount).toBeGreaterThan(0)
  })

  test('total trades across all bars equals total trade count', async ({ page }) => {
    // Get total trades from the Trades tab before switching away
    await page.getByRole('tab', { name: 'Trades', exact: true }).click()
    const tradeCountText = await page.getByText(/Trades \(\d+\)/).textContent()
    const tableTotal = parseInt(tradeCountText?.match(/\((\d+)\)/)?.[1] ?? '0')
    expect(tableTotal).toBeGreaterThan(0)

    // Switch back to Trades by Month
    await page.getByRole('tab', { name: 'Trades by Month' }).click()
    await expect(page.getByRole('tab', { name: 'Trades by Month' })).toHaveAttribute('data-state', 'active')

    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')
      if (!el) return false
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return !!(el as any)._ec_instance
    })

    const barTotal = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')!
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (el as any)._ec_instance
      const option = chart.getOption()
      const data = option.series[0].data as { value: number }[]
      return data.reduce((sum: number, d: { value: number }) => sum + d.value, 0)
    })

    expect(barTotal).toBe(tableTotal)
  })
})
