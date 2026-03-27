import { test, expect } from '@playwright/test'

test.describe('Backtest CRUD happy path', () => {
  test('create, verify, and delete a backtest run', async ({ page }) => {
    // Step 1: Navigate to create page
    await page.goto('/create')
    await expect(page.getByText('Create Backtest')).toBeVisible()

    // Step 2: Select EMACross strategy (built-in, always available)
    const strategySelect = page.locator('select').first()
    await expect(strategySelect).toBeVisible()
    await expect(strategySelect.locator('option').nth(1)).toBeAttached()
    await strategySelect.selectOption('EMACross')

    // Step 3: Select bar type
    const barTypeSelect = page.locator('select').nth(1)
    await expect(barTypeSelect).toBeVisible()
    await expect(barTypeSelect.locator('option').nth(1)).toBeAttached()
    const barTypeValue = await barTypeSelect.locator('option').nth(1).getAttribute('value')
    expect(barTypeValue).toBeTruthy()
    await barTypeSelect.selectOption(barTypeValue!)

    // Step 4: Submit
    const submitButton = page.getByRole('button', { name: 'Run Backtest' })
    await expect(submitButton).toBeEnabled()
    await submitButton.click()

    // Step 5: Wait for backtest to complete and redirect
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/, { timeout: 60_000 })

    // Capture run ID from URL
    const url = page.url()
    const runIdMatch = url.match(/\/runs\/([a-f0-9-]+)/)
    expect(runIdMatch).toBeTruthy()
    const runId = runIdMatch![1]

    // Step 6: Verify run detail page loaded
    await expect(page.getByRole('heading', { name: /Run [a-f0-9]+/ })).toBeVisible()

    // Step 7: Navigate to dashboard and verify run appears
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Look for EMACross strategy in the table
    const newRunRow = tabulator.locator('.tabulator-row', {
      has: page.locator('.tabulator-cell', { hasText: 'EMACross' }),
    }).first()
    await expect(newRunRow).toBeVisible()

    // Step 8: Delete the run
    page.once('dialog', (dialog) => dialog.accept())
    const deleteButton = newRunRow.locator('button[title="Delete"]')
    await deleteButton.click()

    // Step 9: Verify run removed
    await expect(
      tabulator.locator('.tabulator-row', {
        has: page.locator('[tabulator-field="run_id"]', { hasText: runId.slice(0, 8) }),
      })
    ).toHaveCount(0)
  })
})
