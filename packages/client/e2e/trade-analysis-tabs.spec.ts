import { test, expect } from '@playwright/test'

test.describe('Trade Analysis Tabs', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
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

  test('clicking Chart Analysis tab switches to chart content', async ({ page }) => {
    const chartTab = page.getByRole('tab', { name: 'Chart Analysis' })
    await chartTab.click()
    await expect(chartTab).toHaveAttribute('data-state', 'active')
    await expect(page.getByRole('tab', { name: 'Trades', exact: true })).toHaveAttribute('data-state', 'inactive')
  })

  test('all tabs are present', async ({ page }) => {
    const expectedTabs = [
      'Trades',
      'Chart Analysis',
      'Categorisation',
      'Trades by Month',
    ]
    for (const tabName of expectedTabs) {
      await expect(page.getByRole('tab', { name: tabName, exact: true })).toBeVisible()
    }
  })

  test('switching back to Trades tab restores trade table', async ({ page }) => {
    // Navigate away
    await page.getByRole('tab', { name: 'Chart Analysis' }).click()
    await expect(page.getByTestId('pnl-distribution-chart')).toBeVisible()

    // Navigate back
    await page.getByRole('tab', { name: 'Trades', exact: true }).click()
    await expect(page.getByRole('tab', { name: 'Trades', exact: true })).toHaveAttribute('data-state', 'active')
    await expect(page.getByText(/Trades \(\d+\)/)).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Direction' })).toBeVisible()
  })
})
