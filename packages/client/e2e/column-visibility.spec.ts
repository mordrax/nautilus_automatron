import { test, expect } from '@playwright/test'

test.describe('Column Visibility', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage to start fresh
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.removeItem('column-visibility:run-list')
      localStorage.removeItem('column-visibility:catalog-table')
    })
    await page.reload()
  })

  test('cog icon is visible on both tables', async ({ page }) => {
    const configButtons = page.getByRole('button', { name: 'Configure columns' })
    await expect(configButtons).toHaveCount(2)
  })

  test('clicking cog opens column visibility popover', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const cogButton = runsSection.getByRole('button', { name: 'Configure columns' })
    await cogButton.click()

    const popover = page.getByRole('dialog')
    await expect(popover).toBeVisible()
    await expect(popover.getByText('Columns')).toBeVisible()
  })

  test('popover lists all toggleable columns for runs table', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const cogButton = runsSection.getByRole('button', { name: 'Configure columns' })
    await cogButton.click()

    const popover = page.getByRole('dialog')
    for (const col of ['Trader', 'Strategy', 'Total PnL', 'Win Rate', 'Sharpe', 'Avg Hold']) {
      await expect(popover.getByText(col)).toBeVisible()
    }
  })

  test('unchecking a column hides it from the table', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Verify Sharpe column is visible
    await expect(tabulator.locator('.tabulator-col-title', { hasText: 'Sharpe' })).toBeVisible()

    // Open popover and uncheck Sharpe
    const cogButton = runsSection.getByRole('button', { name: 'Configure columns' })
    await cogButton.click()

    const popover = page.getByRole('dialog')
    const sharpeCheckbox = popover.locator('label', { hasText: 'Sharpe' }).locator('input')
    await sharpeCheckbox.uncheck()

    // Close popover by clicking outside
    await page.locator('body').click({ position: { x: 10, y: 10 } })

    // Verify Sharpe column is hidden
    await expect(tabulator.locator('.tabulator-col-title', { hasText: 'Sharpe' })).toBeHidden()
  })

  test('re-checking a column shows it again', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    const cogButton = runsSection.getByRole('button', { name: 'Configure columns' })

    // Hide Sharpe
    await cogButton.click()
    const popover = page.getByRole('dialog')
    const sharpeCheckbox = popover.locator('label', { hasText: 'Sharpe' }).locator('input')
    await sharpeCheckbox.uncheck()
    await page.locator('body').click({ position: { x: 10, y: 10 } })
    await expect(tabulator.locator('.tabulator-col-title', { hasText: 'Sharpe' })).toBeHidden()

    // Show Sharpe again
    await cogButton.click()
    const popover2 = page.getByRole('dialog')
    const sharpeCheckbox2 = popover2.locator('label', { hasText: 'Sharpe' }).locator('input')
    await sharpeCheckbox2.check()
    await page.locator('body').click({ position: { x: 10, y: 10 } })
    await expect(tabulator.locator('.tabulator-col-title', { hasText: 'Sharpe' })).toBeVisible()
  })

  test('column visibility persists across page reload', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Hide Sharpe
    const cogButton = runsSection.getByRole('button', { name: 'Configure columns' })
    await cogButton.click()
    const popover = page.getByRole('dialog')
    await popover.locator('label', { hasText: 'Sharpe' }).locator('input').uncheck()
    await page.locator('body').click({ position: { x: 10, y: 10 } })
    await expect(tabulator.locator('.tabulator-col-title', { hasText: 'Sharpe' })).toBeHidden()

    // Reload page
    await page.reload()

    // Verify Sharpe is still hidden after reload
    const runsSection2 = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator2 = runsSection2.locator('.tabulator')
    await expect(tabulator2.locator('.tabulator-row').first()).toBeVisible()
    await expect(tabulator2.locator('.tabulator-col-title', { hasText: 'Sharpe' })).toBeHidden()
  })

  test('catalog table cog opens popover with catalog columns', async ({ page }) => {
    const catalogSection = page.locator('section', { has: page.getByText('Instrument Data Catalog') })
    const cogButton = catalogSection.getByRole('button', { name: 'Configure columns' })
    await cogButton.click()

    const popover = page.getByRole('dialog')
    await expect(popover).toBeVisible()
    for (const col of ['Instrument', 'Bar Count', 'Start Date', 'End Date', 'Timeframe']) {
      await expect(popover.getByText(col)).toBeVisible()
    }
  })
})
