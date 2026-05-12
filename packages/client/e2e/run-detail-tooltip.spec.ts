import { test, expect } from '@playwright/test'

test.describe('Run Detail — bar_type chip tooltip', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    // Wait for the trade navigator to confirm the page is hydrated
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('hovering a chip reveals catalog metadata', async ({ page }) => {
    const chip = page.locator('[data-bartype]').first()
    await expect(chip).toBeVisible()
    await chip.hover()

    const tooltip = page.locator('[data-slot="tooltip-content"]').first()
    await expect(tooltip).toBeVisible()

    // The tooltip shows real provenance, not placeholders
    await expect(tooltip).toContainText(/Symbol/)
    await expect(tooltip).toContainText(/Range/)
    await expect(tooltip).toContainText(/Bars/)
    await expect(tooltip).toContainText(/Path/)
    // Real on-disk path lives under backtest_catalog/data/bar/
    await expect(tooltip).toContainText(/backtest_catalog\/data\/bar\//)
    // Range uses an arrow between two YYYY-MM-DD dates
    await expect(tooltip).toContainText(/\d{4}-\d{2}-\d{2}\s+→\s+\d{4}-\d{2}-\d{2}/)
    // Bar count is a non-zero number (formatted with optional thousands sep)
    await expect(tooltip).toContainText(/[1-9][\d,]*/)
  })

  test('clicking a chip pins the tooltip open', async ({ page }) => {
    const chip = page.locator('[data-bartype]').first()
    await chip.click()
    // After click, even when the mouse moves away the tooltip stays
    await page.mouse.move(0, 0)
    const tooltip = page.locator('[data-slot="tooltip-content"]').first()
    await expect(tooltip).toBeVisible()
    await expect(chip).toHaveAttribute('data-pinned', 'true')

    // Click again to unpin — tooltip closes after mouse leaves
    await chip.click()
    await expect(chip).not.toHaveAttribute('data-pinned', 'true')
    await page.mouse.move(0, 0)
    await expect(tooltip).not.toBeVisible()
  })

  test('chip with no catalog entry falls back to "Not in catalog"', async ({ page }) => {
    // Stub catalog response to be empty BEFORE navigating
    await page.route('**/api/catalog', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
    })

    // Re-navigate so the stubbed catalog is used
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    await runsSection.locator('[role="grid"]').getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()

    const chip = page.locator('[data-bartype]').first()
    await chip.hover()
    const tooltip = page.locator('[data-slot="tooltip-content"]').first()
    await expect(tooltip).toBeVisible()
    await expect(tooltip).toContainText('Not in catalog')
  })
})
