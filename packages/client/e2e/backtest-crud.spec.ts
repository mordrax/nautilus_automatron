import { test, expect } from '@playwright/test'

test.describe('Backtest CRUD happy path', () => {
  test.skip('create, verify, and delete a backtest run', async ({ page }) => {
    // Step 1: Navigate to the create page
    await page.goto('/create')
    await expect(page.getByText('Create Backtest')).toBeVisible()

    // Step 2: Wait for the strategy dropdown to load, then select BBBStrategy
    const strategySelect = page.locator('select').first()
    await expect(strategySelect).toBeVisible()

    // Wait for strategies to load (options should appear beyond the placeholder)
    await expect(strategySelect.locator('option').nth(1)).toBeAttached()
    await strategySelect.selectOption('BBBStrategy')

    // Step 3: Select the bar type — use the first available option from the dropdown
    const barTypeSelect = page.locator('select').nth(1)
    await expect(barTypeSelect).toBeVisible()

    // Wait for bar types to load
    await expect(barTypeSelect.locator('option').nth(1)).toBeAttached()

    // Get the value of the first real option (index 0 is the placeholder "Select bar type...")
    const barTypeValue = await barTypeSelect.locator('option').nth(1).getAttribute('value')
    expect(barTypeValue).toBeTruthy()
    await barTypeSelect.selectOption(barTypeValue!)

    // Verify Run Backtest button is now enabled
    const submitButton = page.getByRole('button', { name: 'Run Backtest' })
    await expect(submitButton).toBeEnabled()

    // Step 4: Submit the form — real backtest may take several seconds
    await submitButton.click()

    // Wait for the button to show "Running backtest..." (mutation is pending)
    await expect(page.getByRole('button', { name: 'Running backtest...' })).toBeVisible()

    // Step 5: Wait for redirect to /runs/{new_run_id} — allow up to 60s for backtest to complete
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/, { timeout: 60_000 })

    // Capture the run ID from the URL
    const url = page.url()
    const runIdMatch = url.match(/\/runs\/([a-f0-9-]+)/)
    expect(runIdMatch).toBeTruthy()
    const runId = runIdMatch![1]

    // Verify we're on the run detail page (some content should be visible)
    await expect(page.getByText(/Run Details|Backtest Run|run_id/i).first()).toBeVisible()

    // Step 6: Navigate back to the runs list (dashboard)
    await page.goto('/')
    await expect(page.getByText('Backtest Runs')).toBeVisible()

    // Step 7: Verify the new run appears in the list
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    // Wait for rows to load and find the new run row
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Look for a row containing the new run ID (first 8 chars are displayed in delete confirm)
    // The strategy column should show BBBStrategy
    const newRunRow = tabulator.locator('.tabulator-row', {
      has: tabulator.locator(`[tabulator-field="strategy"]`, { hasText: 'BBBStrategy' }),
    }).first()

    // Verify a BBBStrategy row exists
    await expect(newRunRow).toBeVisible()

    // Step 8: Delete the new run
    // The delete button is the ✕ button. We need to click the one in the new run's row.
    // We handle the confirm dialog first
    page.once('dialog', (dialog) => dialog.accept())

    // Click the ✕ (delete) button in the new run row
    const deleteButton = tabulator.locator('.tabulator-row').filter({
      hasText: 'BBBStrategy',
    }).first().locator('button[title="Delete"]')
    await deleteButton.click()

    // Step 9: Verify the run is removed — wait for the row count to decrease
    // After deletion, no BBBStrategy rows should remain (since we only created one)
    await expect(
      tabulator.locator('.tabulator-row', {
        has: page.locator('[tabulator-field="run_id"]', { hasText: runId.slice(0, 8) }),
      })
    ).toHaveCount(0)
  })
})
