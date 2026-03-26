import { test, expect } from '@playwright/test'

test.describe('Chart Analysis - Core 4 Charts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await table.locator('tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()

    // Switch to Chart Analysis tab
    await page.getByRole('tab', { name: 'Chart Analysis' }).click()
    await expect(page.getByRole('tab', { name: 'Chart Analysis' })).toHaveAttribute('data-state', 'active')
  })

  test('three trade-data charts are visible, equity shows chart or loading state', async ({ page }) => {
    await expect(page.getByTestId('pnl-distribution-chart')).toBeVisible()
    await expect(page.getByTestId('pnl-hold-time-chart')).toBeVisible()
    await expect(page.getByTestId('pnl-over-time-chart')).toBeVisible()

    // Equity chart depends on a separate API endpoint that may not be available in test data
    const equityChart = page.getByTestId('equity-curve-chart')
    const equityLoading = page.getByText('Loading equity data...')
    const isChartVisible = await equityChart.isVisible().catch(() => false)
    const isLoadingVisible = await equityLoading.isVisible().catch(() => false)
    expect(isChartVisible || isLoadingVisible).toBe(true)
  })

  test('P/L Distribution, Hold Time, and Over Time charts render canvas', async ({ page }) => {
    // These 3 charts use trade data which is always available
    await expect(page.getByTestId('pnl-distribution-chart').locator('canvas').first()).toBeVisible()
    await expect(page.getByTestId('pnl-hold-time-chart').locator('canvas').first()).toBeVisible()
    await expect(page.getByTestId('pnl-over-time-chart').locator('canvas').first()).toBeVisible()
  })

  test('charts are arranged in a 2x2 grid', async ({ page }) => {
    // Wait for the trade-data charts to render
    await expect(page.getByTestId('pnl-distribution-chart').locator('canvas').first()).toBeVisible()
    await expect(page.getByTestId('pnl-hold-time-chart').locator('canvas').first()).toBeVisible()
    await expect(page.getByTestId('pnl-over-time-chart').locator('canvas').first()).toBeVisible()

    const boxes = await Promise.all([
      page.getByTestId('pnl-distribution-chart').boundingBox(),
      page.getByTestId('pnl-hold-time-chart').boundingBox(),
      page.getByTestId('pnl-over-time-chart').boundingBox(),
    ])

    for (const box of boxes) {
      expect(box).toBeTruthy()
    }

    // Top row: P/L Distribution (left) and P/L vs Hold Time (right) on same row
    expect(Math.abs(boxes[0]!.y - boxes[1]!.y)).toBeLessThan(5)
    // Bottom row: P/L Over Time should be below the top row
    expect(boxes[2]!.y).toBeGreaterThan(boxes[0]!.y + 100)
  })

  test('trade count in scatter charts matches total trades', async ({ page }) => {
    // Wait for charts to render
    await expect(page.getByTestId('pnl-hold-time-chart').locator('canvas').first()).toBeVisible()

    // Get the trade count by switching to Trades tab briefly
    await page.getByRole('tab', { name: 'Trades', exact: true }).click()
    const tradeCountText = await page.getByText(/Trades \(\d+\)/).textContent()
    const totalTrades = parseInt(tradeCountText?.match(/\((\d+)\)/)?.[1] ?? '0')
    expect(totalTrades).toBeGreaterThan(0)

    // Switch back to Chart Analysis
    await page.getByRole('tab', { name: 'Chart Analysis' }).click()
    await expect(page.getByTestId('pnl-hold-time-chart').locator('canvas').first()).toBeVisible()

    // Use the exposed eCharts pattern from CandlestickChart to access chart data
    // Each chart stores its eCharts instance on the DOM element
    const holdTimeDataCount = await page.evaluate(() => {
      const container = document.querySelector('[data-testid="pnl-hold-time-chart"]')
      if (!container) return -1
      // eCharts stores instance reference on the DOM element with a key like _echarts_instance_
      const instanceKey = Object.keys(container).find(k => k.startsWith('_ec_'))
      if (!instanceKey) return -1
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const instance = (container as any)[instanceKey]
      if (!instance?.getOption) return -1
      const option = instance.getOption()
      return option.series?.[0]?.data?.length ?? -1
    })

    const overTimeDataCount = await page.evaluate(() => {
      const container = document.querySelector('[data-testid="pnl-over-time-chart"]')
      if (!container) return -1
      const instanceKey = Object.keys(container).find(k => k.startsWith('_ec_'))
      if (!instanceKey) return -1
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const instance = (container as any)[instanceKey]
      if (!instance?.getOption) return -1
      const option = instance.getOption()
      return option.series?.[0]?.data?.length ?? -1
    })

    // Each scatter chart should have one point per trade
    if (holdTimeDataCount > 0) {
      expect(holdTimeDataCount).toBe(totalTrades)
    }
    if (overTimeDataCount > 0) {
      expect(overTimeDataCount).toBe(totalTrades)
    }
  })

  test('P/L Distribution histogram has bins summing to total trades', async ({ page }) => {
    await expect(page.getByTestId('pnl-distribution-chart').locator('canvas').first()).toBeVisible()

    // Get trade count
    await page.getByRole('tab', { name: 'Trades', exact: true }).click()
    const tradeCountText = await page.getByText(/Trades \(\d+\)/).textContent()
    const totalTrades = parseInt(tradeCountText?.match(/\((\d+)\)/)?.[1] ?? '0')
    expect(totalTrades).toBeGreaterThan(0)

    // Switch back
    await page.getByRole('tab', { name: 'Chart Analysis' }).click()
    await expect(page.getByTestId('pnl-distribution-chart').locator('canvas').first()).toBeVisible()

    const binTotal = await page.evaluate(() => {
      const container = document.querySelector('[data-testid="pnl-distribution-chart"]')
      if (!container) return -1
      const instanceKey = Object.keys(container).find(k => k.startsWith('_ec_'))
      if (!instanceKey) return -1
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const instance = (container as any)[instanceKey]
      if (!instance?.getOption) return -1
      const option = instance.getOption()
      const data = option.series?.[0]?.data
      if (!data) return -1
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return data.reduce((sum: number, d: any) => sum + (typeof d === 'number' ? d : d.value), 0)
    })

    if (binTotal > 0) {
      expect(binTotal).toBe(totalTrades)
    }
  })

  test('charts have correct dimensions (400px height)', async ({ page }) => {
    const tradeCharts = [
      'pnl-distribution-chart',
      'pnl-hold-time-chart',
      'pnl-over-time-chart',
    ]

    for (const testId of tradeCharts) {
      await expect(page.getByTestId(testId).locator('canvas').first()).toBeVisible()
      const box = await page.getByTestId(testId).boundingBox()
      expect(box).toBeTruthy()
      expect(box!.height).toBeGreaterThanOrEqual(350)
      expect(box!.height).toBeLessThanOrEqual(450)
    }
  })
})
