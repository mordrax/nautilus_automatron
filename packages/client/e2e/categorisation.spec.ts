import { test, expect } from '@playwright/test'

test.describe('Trade Categorisation Table', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const grid = page.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for async data to load
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    // Navigate to Categorisation tab
    await page.getByRole('tab', { name: 'Categorisation' }).click()
    await expect(page.getByRole('tab', { name: 'Categorisation' })).toHaveAttribute('data-state', 'active')
  })

  test('categorisation table renders with 7 categories', async ({ page }) => {
    const catTable = page.getByTestId('categorisation-table')
    await expect(catTable).toBeVisible()

    // Verify all 7 category rows exist
    for (let i = 1; i <= 7; i++) {
      await expect(page.getByTestId(`category-row-${i}`)).toBeVisible()
    }

    // Verify column headers
    await expect(page.getByRole('columnheader', { name: 'Key' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Description' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Count' })).toBeVisible()
  })

  test('all category counts start at zero', async ({ page }) => {
    for (let i = 1; i <= 7; i++) {
      await expect(page.getByTestId(`category-count-${i}`)).toHaveText('0')
    }
  })

  test('total categorised trades matches trades assigned via hotkeys', async ({ page }) => {
    // Helper to dispatch keydown with CapsLock modifier (CapsLock toggle is unreliable in headless)
    const pressWithCapsLock = (key: string) =>
      page.evaluate((k) => {
        const event = new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true })
        Object.defineProperty(event, 'getModifierState', {
          value: (mod: string) => mod === 'CapsLock',
        })
        document.dispatchEvent(event)
      }, key)

    // Get total trade count from the Trades tab header
    await page.getByRole('tab', { name: 'Trades', exact: true }).click()
    const tradesHeading = page.getByText(/Trades \((\d+)\)/)
    await expect(tradesHeading).toBeVisible()
    const headingText = await tradesHeading.textContent()
    const totalTrades = Number(headingText!.match(/Trades \((\d+)\)/)![1])
    expect(totalTrades).toBeGreaterThan(0)

    // Go back to categorisation tab
    await page.getByRole('tab', { name: 'Categorisation' }).click()
    await expect(page.getByTestId('categorisation-table')).toBeVisible()

    // Assign all trades to category 1: press '1' then ArrowRight for each trade
    for (let i = 0; i < totalTrades; i++) {
      await pressWithCapsLock('1')
      if (i < totalTrades - 1) {
        await pressWithCapsLock('ArrowRight')
      }
    }

    // Verify category 1 count matches total trades
    await expect(page.getByTestId('category-count-1')).toHaveText(String(totalTrades))

    // Sum of all category counts should equal total trades
    let totalCategorised = 0
    for (let i = 1; i <= 7; i++) {
      const countText = await page.getByTestId(`category-count-${i}`).textContent()
      totalCategorised += Number(countText)
    }
    expect(totalCategorised).toBe(totalTrades)
  })
})
