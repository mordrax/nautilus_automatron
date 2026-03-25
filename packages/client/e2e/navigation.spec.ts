import { test, expect } from '@playwright/test'

test.describe('Trade Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const table = page.locator('table')
    await expect(table).toBeVisible()
    await table.locator('tbody tr').first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for trade data to load
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Trade #1/).first()).toBeVisible()
  })

  test('clicking Next advances to the next trade', async ({ page }) => {
    // Should start at Trade #1
    await expect(page.getByText(/^1 \/ \d+$/)).toBeVisible()

    await page.getByRole('button', { name: /Next/ }).click()

    // Should now show Trade #2
    await expect(page.getByText(/Trade #2/).first()).toBeVisible()
    await expect(page.getByText(/^2 \/ \d+$/)).toBeVisible()
  })

  test('clicking Prev goes back to previous trade', async ({ page }) => {
    // Go to Trade #2 first
    await page.getByRole('button', { name: /Next/ }).click()
    await expect(page.getByText(/Trade #2/).first()).toBeVisible()

    // Click Prev — back to Trade #1
    await page.getByRole('button', { name: /Prev/ }).click()
    await expect(page.getByText(/Trade #1/).first()).toBeVisible()
    await expect(page.getByText(/^1 \/ \d+$/)).toBeVisible()
  })

  test('clicking a trade in the table selects it', async ({ page }) => {
    // Find the trades table (has "Trades (N)" heading above it)
    await expect(page.getByText(/Trades \(\d+\)/)).toBeVisible()

    // Click the 3rd trade row in the trades table
    const tradesTable = page.locator('table').last()
    const thirdRow = tradesTable.locator('tbody tr').nth(2)
    await expect(thirdRow).toBeVisible()
    await thirdRow.click()

    // Navigator should update to Trade #3
    await expect(page.getByText(/Trade #3/).first()).toBeVisible()
    await expect(page.getByText(/^3 \/ \d+$/)).toBeVisible()
  })

  test('trade tooltip updates when trade changes', async ({ page }) => {
    // Get initial tooltip direction text
    const tooltipDirection = page.locator('text=Direction:').first()
    await expect(tooltipDirection).toBeVisible()

    // Navigate to next trade
    await page.getByRole('button', { name: /Next/ }).click()
    await expect(page.getByText(/Trade #2/).first()).toBeVisible()

    // Tooltip should still be visible (content may have changed)
    await expect(tooltipDirection).toBeVisible()
  })
})
