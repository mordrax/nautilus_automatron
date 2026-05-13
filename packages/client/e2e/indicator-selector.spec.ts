import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { enableIndicator, removeIndicator } from './helpers'

const __dirname = path.dirname(new URL(import.meta.url).pathname)
const RUN_ID = '41a1f019-a7fd-44cd-9c7a-bf41e5b0bf31'
const viewerStatePath = path.resolve(
  __dirname,
  'test-data/backtest_catalog/backtest',
  RUN_ID,
  'viewer_state.json',
)

const clearViewerState = () => {
  if (fs.existsSync(viewerStatePath)) fs.unlinkSync(viewerStatePath)
  const tmpPath = viewerStatePath + '.tmp'
  if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath)
}

test.describe('Indicator Instance Selector (new behavior)', () => {
  test.beforeEach(async ({ page }) => {
    clearViewerState()
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test.afterEach(() => {
    clearViewerState()
  })

  test('empty state shows only the Add button', async ({ page }) => {
    const selector = page.getByTestId('indicator-instance-selector')
    await expect(selector.getByTestId('add-indicator-button')).toBeVisible()
    // No chips yet
    await expect(selector.locator('[data-testid="indicator-chip"]')).toHaveCount(0)
  })

  test('Add popover opens with indicator type list', async ({ page }) => {
    await page.getByTestId('add-indicator-button').click()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' })).toBeVisible()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'RSI' })).toBeVisible()
  })

  test('picking SMA shows the param form', async ({ page }) => {
    await page.getByTestId('add-indicator-button').click()
    await page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' }).click()
    await expect(page.getByTestId('param-input-period')).toBeVisible()
    await expect(page.getByTestId('param-form-submit')).toBeVisible()
  })

  test('multiple instances of same type coexist as separate chips', async ({ page }) => {
    await enableIndicator(page, 'SMA')

    // Add another SMA (will also default to 20, but with a different id)
    await page.getByTestId('add-indicator-button').click()
    await page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' }).click()
    await page.getByTestId('param-input-period').fill('50')
    await page.getByTestId('param-form-submit').click()
    await expect(page.getByTestId('param-form-submit')).not.toBeVisible()

    const selector = page.getByTestId('indicator-instance-selector')
    await expect(selector.getByText('SMA(20)')).toBeVisible()
    await expect(selector.getByText('SMA(50)')).toBeVisible()
  })

  test('clicking outside closes the Add popover without adding anything', async ({ page }) => {
    await page.getByTestId('add-indicator-button').click()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' })).toBeVisible()
    // Click outside the popover to dismiss it
    await page.mouse.click(10, 10)
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' })).not.toBeVisible()
    const selector = page.getByTestId('indicator-instance-selector')
    await expect(selector.locator('[data-testid="indicator-chip"]')).toHaveCount(0)
  })

  test('removing a chip leaves others intact', async ({ page }) => {
    await enableIndicator(page, 'SMA')
    await enableIndicator(page, 'EMA')

    const selector = page.getByTestId('indicator-instance-selector')
    await expect(selector.locator('[data-testid="indicator-chip"]')).toHaveCount(2)

    await removeIndicator(page, 'SMA(20)')
    await expect(selector.locator('[data-testid="indicator-chip"]')).toHaveCount(1)
    await expect(selector.getByText('EMA(20)')).toBeVisible()
  })
})
