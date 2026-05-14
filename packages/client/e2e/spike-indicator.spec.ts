import { test, expect, Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'

const __dirname = path.dirname(new URL(import.meta.url).pathname)

const clearAllViewerStates = () => {
  // Defensive: viewer-state files live alongside each run's data and can
  // pollute repeat runs.
  const root = path.resolve(__dirname, 'test-data/backtest_catalog/backtest')
  if (!fs.existsSync(root)) return
  for (const runId of fs.readdirSync(root)) {
    const p = path.join(root, runId, 'viewer_state.json')
    if (fs.existsSync(p)) fs.unlinkSync(p)
    const tmp = p + '.tmp'
    if (fs.existsSync(tmp)) fs.unlinkSync(tmp)
  }
}

const openFirstRun = async (page: Page) => {
  await page.goto('/')
  const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
  const grid = runsSection.locator('[role="grid"]')
  await expect(grid).toBeVisible()
  await grid.getByRole('button', { name: 'View' }).first().click()
  await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
  await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
}

const addSpikeWithDefaultsAndWait = async (page: Page) => {
  // Listen for the POST /indicators response before clicking, to avoid a
  // race where the response lands before the listener attaches.
  const responsePromise = page.waitForResponse(
    (resp) =>
      resp.url().includes('/indicators') &&
      resp.request().method() === 'POST' &&
      resp.status() === 200,
    { timeout: 15_000 },
  )

  await page.getByTestId('add-indicator-button').click()
  await page
    .locator('[data-testid="indicator-type-option"]', { hasText: 'Spike' })
    .click()
  // Form is pre-seeded with defaults for all 9 params (3 enum, 6 numeric).
  await page.getByTestId('param-form-submit').click()
  await expect(page.getByTestId('param-form-submit')).not.toBeVisible()
  await responsePromise

  // Wait until the chart includes Spike series (regardless of whether spikes
  // actually fired on this test data — the series are present even when sparse).
  await page.waitForFunction(
    () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      if (!chart?.getOption) return false
      const series = chart.getOption().series ?? []
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return series.some((s: any) =>
        typeof s?.name === 'string' && s.name.toLowerCase().includes('spike'),
      )
    },
    { timeout: 10_000 },
  )
}

test.describe('Spike indicator e2e', () => {
  test.beforeEach(() => clearAllViewerStates())
  test.afterEach(() => clearAllViewerStates())

  test('add Spike with defaults registers spike_up and spike_down series', async ({
    page,
  }) => {
    await openFirstRun(page)
    await addSpikeWithDefaultsAndWait(page)

    const seriesNames = await page.evaluate(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return ((chart?.getOption()?.series ?? []) as any[]).map((s) => s?.name ?? '')
    })

    // Two scatter series — one for up, one for down — both labelled with
    // the Spike instance label.
    const spikeSeries = seriesNames.filter((n: string) =>
      typeof n === 'string' && n.toLowerCase().includes('spike'),
    )
    expect(spikeSeries.length).toBeGreaterThanOrEqual(2)
    expect(spikeSeries.some((n: string) => n.endsWith('up'))).toBe(true)
    expect(spikeSeries.some((n: string) => n.endsWith('down'))).toBe(true)
  })
})
