import { test, expect } from '@playwright/test'

test.describe('Runs Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('page loads with app title', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Nautilus Automatron' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible()
  })

  test('runs table is visible with metric columns', async ({ page }) => {
    await expect(page.getByText('Backtest Runs')).toBeVisible()

    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    // Verify key columns exist in header
    for (const col of ['Run ID', 'Strategy', 'Total PnL', 'Win Rate', 'Sharpe', 'Avg Hold']) {
      await expect(tabulator.locator('.tabulator-col-title', { hasText: col }).first()).toBeVisible()
    }
  })

  test('strategy column shows actual names, not Unknown', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    // Wait for data rows to render
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Check that "Unknown" does not appear in any cell
    const unknownCount = await tabulator.locator('.tabulator-cell', { hasText: 'Unknown' }).count()
    expect(unknownCount).toBe(0)

    // Verify actual strategy name appears
    await expect(tabulator.locator('.tabulator-cell', { hasText: 'EMACross-000' }).first()).toBeVisible()
  })

  test('metric columns display numeric values', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Total PnL column should have a colored value (+ or -)
    // The PnL formatter wraps values in a <span> with color
    const firstRow = tabulator.locator('.tabulator-row').first()
    const pnlCell = firstRow.locator('[tabulator-field="total_pnl"]')
    const pnlText = await pnlCell.textContent()
    expect(pnlText).not.toBe('—')
    expect(pnlText).toMatch(/[+-]?\d+\.?\d*/)
  })

  test('clicking View button navigates to detail page', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Click the View button in the first row
    const viewButton = tabulator.locator('.tabulator-row').first().locator('button', { hasText: 'View' })
    await viewButton.click()

    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
  })

  test('columns are sortable', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Click Total PnL header to sort
    const pnlHeader = tabulator.locator('.tabulator-col', { hasText: 'Total PnL' }).first()
    await pnlHeader.click()

    // Verify sort indicator appears (Tabulator adds a sort arrow)
    await expect(pnlHeader.locator('.tabulator-col-sorter')).toBeVisible()
  })

  test('header filters are present and functional', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Type in the Strategy header filter
    const strategyCol = tabulator.locator('.tabulator-col', { hasText: 'Strategy' }).first()
    const strategyFilter = strategyCol.locator('input')
    await strategyFilter.fill('EMACross')

    // All visible rows should still exist (EMACross matches the test data)
    const rows = tabulator.locator('.tabulator-row')
    const count = await rows.count()
    expect(count).toBeGreaterThan(0)
  })

  test('Total PnL numeric filter works with eval predicate', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    const pnlCol = tabulator.locator('.tabulator-col', { hasText: 'Total' }).first()
    const pnlFilter = pnlCol.locator('input')

    // Test data has PnL of -2967.06, so >0 should hide all rows
    await pnlFilter.click()
    await pnlFilter.fill('>0')
    await pnlFilter.press('Enter')
    await expect(tabulator.locator('.tabulator-row')).toHaveCount(0)

    // <0 should show the row back
    await pnlFilter.fill('<0')
    await pnlFilter.press('Enter')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Clear filter should show all rows again
    await pnlFilter.fill('')
    await pnlFilter.press('Enter')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()
  })

  test('instrument data catalog table is visible', async ({ page }) => {
    await expect(page.getByText('Instrument Data Catalog')).toBeVisible()

    const catalogSection = page.locator('section', { has: page.getByText('Instrument Data Catalog') })
    const tabulator = catalogSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    for (const col of ['Instrument', 'Bar Count', 'Start Date', 'End Date', 'Timeframe']) {
      await expect(tabulator.locator('.tabulator-col-title', { hasText: col }).first()).toBeVisible()
    }

    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()
    await expect(tabulator.locator('.tabulator-cell', { hasText: 'AUD/USD.SIM' }).first()).toBeVisible()
  })
})
