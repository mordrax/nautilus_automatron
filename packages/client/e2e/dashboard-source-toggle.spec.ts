import { test, expect } from '@playwright/test'

test.describe('Dashboard source toggle + accordion', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('defaults to Backtest Runs tab', async ({ page }) => {
    const backtestTab = page.getByRole('tab', { name: 'Backtest Runs' })
    const catalogTab = page.getByRole('tab', { name: 'Instrument Data Catalog' })

    await expect(backtestTab).toHaveAttribute('aria-selected', 'true')
    await expect(catalogTab).toHaveAttribute('aria-selected', 'false')

    const runsSection = page.locator('section', { has: page.getByRole('heading', { name: /Backtest Runs/ }) })
    await expect(runsSection.locator('.tabulator')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Instrument Data Catalog' })).toBeHidden()
  })

  test('clicking Instrument Data Catalog tab swaps the visible section', async ({ page }) => {
    await page.getByRole('tab', { name: 'Instrument Data Catalog' }).click()

    const catalogSection = page.locator('section', { has: page.getByRole('heading', { name: 'Instrument Data Catalog' }) })
    await expect(catalogSection.locator('.tabulator')).toBeVisible()
    await expect(page.getByRole('heading', { name: /Backtest Runs/ })).toBeHidden()
  })

  test('chevron collapses and re-expands the Backtest Runs table', async ({ page }) => {
    const runsSection = page.locator('section', { has: page.getByRole('heading', { name: /Backtest Runs/ }) })
    const tabulator = runsSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    const collapseButton = page.getByRole('button', { name: /Collapse Backtest Runs/ })
    await collapseButton.click()
    await expect(tabulator).toBeHidden()

    const expandButton = page.getByRole('button', { name: /Expand Backtest Runs/ })
    await expandButton.click()
    await expect(tabulator).toBeVisible()
  })

  test('chevron collapses and re-expands the catalog table independently', async ({ page }) => {
    await page.getByRole('tab', { name: 'Instrument Data Catalog' }).click()

    const catalogSection = page.locator('section', { has: page.getByRole('heading', { name: 'Instrument Data Catalog' }) })
    const tabulator = catalogSection.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    await page.getByRole('button', { name: 'Collapse Instrument Data Catalog' }).click()
    await expect(tabulator).toBeHidden()

    await page.getByRole('button', { name: 'Expand Instrument Data Catalog' }).click()
    await expect(tabulator).toBeVisible()
  })
})
