import { test, expect } from '@playwright/test'

test.describe('Runs Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('page loads with app title', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Nautilus Automatron' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Runs' })).toBeVisible()
  })

  test('runs table is visible with correct columns', async ({ page }) => {
    await expect(page.getByText('Backtest Runs')).toBeVisible()
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await expect(table.getByText('Run ID')).toBeVisible()
    await expect(table.getByText('Trader')).toBeVisible()
    await expect(table.getByText('Strategy')).toBeVisible()
    await expect(table.getByText('Positions')).toBeVisible()
    await expect(table.getByText('Fills')).toBeVisible()
  })

  test('strategy column shows actual names, not Unknown', async ({ page }) => {
    const table = page.locator('table')
    await expect(table).toBeVisible()
    // Wait for data to load
    await expect(table.getByText('EMACross-000').first()).toBeVisible()
    // Ensure no "Unknown" values in the strategy column
    const unknownCount = await table.getByText('Unknown').count()
    expect(unknownCount).toBe(0)
  })

  test('clicking a run navigates to detail page', async ({ page }) => {
    const table = page.locator('table')
    await expect(table).toBeVisible()
    // Click the first run row (uses onClick on table row)
    const firstRow = table.locator('tbody tr').first()
    await expect(firstRow).toBeVisible()
    await firstRow.click()
    // Should navigate to /runs/<runId>
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
  })
})
