import { test, expect } from '@playwright/test'

test.describe('Trade Analysis Tabs', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await table.locator('tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for async data to load
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('Trades tab is selected by default and shows trade table', async ({ page }) => {
    const tradesTab = page.getByRole('tab', { name: 'Trades', exact: true })
    await expect(tradesTab).toBeVisible()
    await expect(tradesTab).toHaveAttribute('data-state', 'active')
    await expect(page.getByText(/Trades \(\d+\)/)).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Direction' })).toBeVisible()
  })

  test('clicking a tab switches to that tab content', async ({ page }) => {
    // Click P/L Distribution tab
    const plTab = page.getByRole('tab', { name: 'P/L Distribution' })
    await plTab.click()
    await expect(plTab).toHaveAttribute('data-state', 'active')
    // Trades tab should no longer be active
    await expect(page.getByRole('tab', { name: 'Trades', exact: true })).toHaveAttribute('data-state', 'inactive')
    // Placeholder content should be visible
    await expect(page.getByText('Coming soon').first()).toBeVisible()
  })

  test('all tabs are present', async ({ page }) => {
    const expectedTabs = [
      'Trades',
      'P/L Distribution',
      'P/L vs Hold Time',
      'P/L Over Time',
      'Equity Curve',
      'Categorisation',
      'Trades by Month',
    ]
    for (const tabName of expectedTabs) {
      await expect(page.getByRole('tab', { name: tabName, exact: true })).toBeVisible()
    }
  })

  test('switching back to Trades tab restores trade table', async ({ page }) => {
    // Navigate away
    await page.getByRole('tab', { name: 'Equity Curve' }).click()
    await expect(page.getByText('Coming soon').first()).toBeVisible()

    // Navigate back
    await page.getByRole('tab', { name: 'Trades', exact: true }).click()
    await expect(page.getByRole('tab', { name: 'Trades', exact: true })).toHaveAttribute('data-state', 'active')
    await expect(page.getByText(/Trades \(\d+\)/)).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Direction' })).toBeVisible()
  })
})
