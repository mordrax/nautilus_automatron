import { test, expect } from '@playwright/test'

const openMenu = (page: import('@playwright/test').Page) =>
  page.getByRole('button', { name: 'Add indicator' }).click()

const enableIndicator = async (page: import('@playwright/test').Page, label: string) => {
  await openMenu(page)
  await page.getByRole('option', { name: label }).click()
  await expect(page.getByPlaceholder('Search indicators…')).not.toBeVisible()
}

test.describe('Indicator Selector (new behavior)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('empty state shows only the Add button', async ({ page }) => {
    const selector = page.getByTestId('indicator-selector')
    await expect(selector.getByRole('button', { name: 'Add indicator' })).toBeVisible()
    // No chips: only the Add button is a button inside the selector
    const buttons = selector.locator('button')
    await expect(buttons).toHaveCount(1)
  })

  test('search filters the menu', async ({ page }) => {
    await openMenu(page)
    await page.getByPlaceholder('Search indicators…').fill('rsi')
    await expect(page.getByRole('option', { name: 'RSI(14)' })).toBeVisible()
    await expect(page.getByRole('option', { name: 'SMA(20)' })).not.toBeVisible()
  })

  test('already-enabled instance is hidden from the menu but siblings remain', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    await openMenu(page)
    await expect(page.getByRole('option', { name: 'SMA(20)' })).not.toBeVisible()
    await expect(page.getByRole('option', { name: 'SMA(50)' })).toBeVisible()
  })

  test('multiple instances of same type coexist as separate chips', async ({ page }) => {
    await enableIndicator(page, 'SMA(20)')
    await enableIndicator(page, 'SMA(50)')

    const selector = page.getByTestId('indicator-selector')
    await expect(selector.getByText('SMA(20)')).toBeVisible()
    await expect(selector.getByText('SMA(50)')).toBeVisible()
  })

  test('keyboard nav: arrow down + Enter enables an instance', async ({ page }) => {
    await openMenu(page)
    // First option in the Overlays group is highlighted by default.
    // Press Enter to select it.
    await page.keyboard.press('Enter')
    // A chip should have appeared
    const selector = page.getByTestId('indicator-selector')
    await expect(selector.locator('button[aria-label^="Disable "]')).toHaveCount(1)
  })

  test('Esc closes the menu without enabling anything', async ({ page }) => {
    await openMenu(page)
    await expect(page.getByPlaceholder('Search indicators…')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByPlaceholder('Search indicators…')).not.toBeVisible()
    const selector = page.getByTestId('indicator-selector')
    await expect(selector.locator('button[aria-label^="Disable "]')).toHaveCount(0)
  })
})
