import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { enableIndicator } from './helpers'

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

test.describe('Indicator Selector', () => {
  test.beforeEach(async ({ page }) => {
    clearViewerState()
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
  })

  test.afterEach(() => {
    clearViewerState()
  })

  test('add menu opens and shows indicator types', async ({ page }) => {
    await page.getByTestId('add-indicator-button').click()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' })).toBeVisible()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'RSI' })).toBeVisible()
    await expect(page.locator('[data-testid="indicator-type-option"]', { hasText: 'BB' })).toBeVisible()
  })

  test('selecting SMA from menu creates an active chip', async ({ page }) => {
    await enableIndicator(page, 'SMA')
    const chip = page.getByTestId('indicator-instance-selector').getByText('SMA(20)')
    await expect(chip).toBeVisible()
  })

  test('enabling RSI increases chart height', async ({ page }) => {
    const chartContainer = page.getByTestId('chart-container')
    const initialBox = await chartContainer.boundingBox()
    expect(initialBox).not.toBeNull()
    const initialHeight = initialBox!.height

    await enableIndicator(page, 'RSI')

    await page.waitForFunction(
      (prevHeight) => {
        const el = document.querySelector('[data-testid="chart-container"]')
        return el ? el.getBoundingClientRect().height > prevHeight : false
      },
      initialHeight,
    )

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBeGreaterThan(initialHeight)
  })

  test('panel indicator does not overlap main chart x-axis', async ({ page }) => {
    await enableIndicator(page, 'RSI')

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height > 600 : false
    })

    const positions = await page.evaluate(() => {
      const container = document.querySelector('[data-testid="chart-container"]')
      if (!container) return null
      const canvas = container.querySelector('canvas')
      if (!canvas) return null
      return {
        containerHeight: container.getBoundingClientRect().height,
        canvasHeight: canvas.getBoundingClientRect().height,
      }
    })

    expect(positions).not.toBeNull()
    expect(positions!.containerHeight).toBeGreaterThan(700)
    expect(positions!.canvasHeight).toBeGreaterThan(700)
  })

  test('multiple panels stack without overlapping each other', async ({ page }) => {
    await enableIndicator(page, 'RSI')
    await enableIndicator(page, 'ATR')

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height > 750 : false
    })

    const containerHeight = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height : 0
    })

    expect(containerHeight).toBeGreaterThan(850)
  })

  test('panel x-axis labels are visible on the bottom panel', async ({ page }) => {
    await enableIndicator(page, 'RSI')

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="chart-container"]')
      return el ? el.getBoundingClientRect().height > 600 : false
    })

    await expect(page.getByText(/Jan-\d+|Feb-\d+/).first()).toBeVisible()
  })

  test('clicking × on chip removes the indicator', async ({ page }) => {
    await enableIndicator(page, 'SMA')
    const selector = page.getByTestId('indicator-instance-selector')
    await expect(selector.getByText('SMA(20)')).toBeVisible()

    const chip = selector.locator('[data-testid="indicator-chip"]', { hasText: 'SMA(20)' })
    await chip.getByTestId('indicator-chip-remove').click()
    await expect(selector.getByText('SMA(20)')).not.toBeVisible()
  })
})
