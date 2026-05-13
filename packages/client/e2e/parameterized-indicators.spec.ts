import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'

const RUN_ID = '41a1f019-a7fd-44cd-9c7a-bf41e5b0bf31'

// Resolve the viewer_state.json path in the test catalog so we can clean it up
const __dirname = path.dirname(new URL(import.meta.url).pathname)
const viewerStatePath = path.resolve(
  __dirname,
  'test-data/backtest_catalog/backtest',
  RUN_ID,
  'viewer_state.json',
)

const navigateToRun = async (page: import('@playwright/test').Page) => {
  await page.goto(`/runs/${RUN_ID}`)
  // Wait for async trade data — Prev button only appears once trades load
  await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
}

const waitForChart = async (page: import('@playwright/test').Page) => {
  await expect(page.locator('canvas').first()).toBeVisible()
}

const openAddPopover = async (page: import('@playwright/test').Page) => {
  await page.getByTestId('add-indicator-button').click()
}

const pickIndicatorType = async (page: import('@playwright/test').Page, typeName: string) => {
  await page.locator('[data-testid="indicator-type-option"]', { hasText: typeName }).click()
}

const setParamAndSubmit = async (
  page: import('@playwright/test').Page,
  paramName: string,
  value: string,
) => {
  const input = page.getByTestId(`param-input-${paramName}`)
  await input.fill(value)
  await page.getByTestId('param-form-submit').click()
}

test.describe('Parameterized Indicators — user journey', () => {
  test.beforeEach(async () => {
      // Clean up any persisted viewer state from previous runs so tests start fresh
    if (fs.existsSync(viewerStatePath)) fs.unlinkSync(viewerStatePath)
    const tmpPath = viewerStatePath + '.tmp'
    if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath)
  })

  test.afterEach(() => {
    // Clean up viewer state written during the test
    if (fs.existsSync(viewerStatePath)) fs.unlinkSync(viewerStatePath)
    const tmpPath = viewerStatePath + '.tmp'
    if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath)
  })

  test('add, edit, remove, and persist indicators', async ({ page }) => {
    // Register a listener for the final PUT before it fires so we don't miss it.
    // The debounce fires 300ms after the last mutation; since we do many things
    // before reloading, this registration is safe to do early.
    const lastPutViewerState = () =>
      page.waitForResponse(
        resp => resp.url().includes('/viewer-state') && resp.request().method() === 'PUT',
        { timeout: 15_000 },
      )

    // Step 1-2: Navigate and wait for chart
    await navigateToRun(page)
    await waitForChart(page)

    // Step 3-5: Add SMA with default period 20
    await openAddPopover(page)
    await pickIndicatorType(page, 'SMA')
    // The param form appears — default period should be 20
    await expect(page.getByTestId('param-input-period')).toHaveValue('20')
    await page.getByTestId('param-form-submit').click()

    // Step 6: Assert SMA(20) chip appears
    const selector = page.getByTestId('indicator-instance-selector')
    await expect(selector.getByText('SMA(20)')).toBeVisible()

    // Step 7-8: Edit chip — change period to 30
    const sma20Chip = selector.locator('[data-testid="indicator-chip"]', { hasText: 'SMA(20)' })
    await sma20Chip.getByTestId('indicator-chip-edit').click()
    const periodInput = page.getByTestId('param-input-period')
    await periodInput.fill('30')
    await page.getByTestId('param-form-submit').click()

    // Step 9: Assert chip now reads SMA(30), SMA(20) is gone
    await expect(selector.getByText('SMA(30)')).toBeVisible()
    await expect(selector.getByText('SMA(20)')).not.toBeVisible()

    // Step 10: Add a second instance with period 50
    await openAddPopover(page)
    await pickIndicatorType(page, 'SMA')
    await setParamAndSubmit(page, 'period', '50')

    // Step 11: Both chips visible
    await expect(selector.getByText('SMA(30)')).toBeVisible()
    await expect(selector.getByText('SMA(50)')).toBeVisible()

    // Step 12: Remove the SMA(30) chip
    const sma30Chip = selector.locator('[data-testid="indicator-chip"]', { hasText: 'SMA(30)' })
    await sma30Chip.getByTestId('indicator-chip-remove').click()

    // Step 13: Only SMA(50) remains
    await expect(selector.getByText('SMA(50)')).toBeVisible()
    await expect(selector.getByText('SMA(30)')).not.toBeVisible()

    // Step 14-15: Reload and assert persistence
    // Register a fresh listener for the PUT that the remove triggers
    const finalPut = lastPutViewerState()
    // small grace period for the debounce to queue
    await finalPut
    await page.reload()
    await waitForChart(page)
    await expect(page.getByTestId('indicator-instance-selector').getByText('SMA(50)')).toBeVisible()
  })
})
