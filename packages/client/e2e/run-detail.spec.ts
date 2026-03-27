import { test, expect } from '@playwright/test'

test.describe('Run Detail Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for async data to load — trade navigator only renders after trades arrive
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('header shows run ID and badges', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Run [a-f0-9]+/ })).toBeVisible()
    await expect(page.getByText(/\d+ positions/)).toBeVisible()
    await expect(page.getByText(/\d+ fills/)).toBeVisible()
    await expect(page.getByText(/AUDUSD/)).toBeVisible()
  })

  test('candlestick chart renders with data', async ({ page }) => {
    // eCharts renders to canvas — verify the canvas element exists
    const chartCanvas = page.locator('canvas').first()
    await expect(chartCanvas).toBeVisible()
    // eCharts also renders axis labels and the dataZoom slider as DOM elements
    // Wait for x-axis labels (date/time) to confirm chart has data
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
    // Verify the chart canvas has non-zero dimensions (data is rendered)
    const box = await chartCanvas.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.width).toBeGreaterThan(100)
    expect(box!.height).toBeGreaterThan(100)
  })

  test('trade navigator is visible with controls', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Next/ })).toBeVisible()
    await expect(page.getByText(/Trade #\d+/).first()).toBeVisible()
    await expect(page.getByText(/\d+ \/ \d+/)).toBeVisible()
  })

  test('trade table displays with correct columns', async ({ page }) => {
    // Wait for the trades section heading to confirm data is loaded
    const tradesHeading = page.getByText(/Trades \(\d+\)/)
    await expect(tradesHeading).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Direction' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Entry Time' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Exit Time' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Entry Price' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Exit Price' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'P&L' })).toBeVisible()
  })

  test('trade tooltip overlay is visible', async ({ page }) => {
    // The draggable trade tooltip renders after trade data loads
    await expect(page.getByText(/Direction:/).first()).toBeVisible()
    await expect(page.getByText(/Entry:/).first()).toBeVisible()
    await expect(page.getByText(/Exit:/).first()).toBeVisible()
  })
})
