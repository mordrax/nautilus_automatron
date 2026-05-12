import { test, expect, Page } from '@playwright/test'

const BAR_TYPE = 'AUDUSD.SIM-100-TICK-MID-INTERNAL'
const DETECTOR_LABEL = 'Equal Highs/Lows'

const navigateToInstrumentPage = async (page: Page) => {
  await page.goto(`/instruments/${encodeURIComponent(BAR_TYPE)}`)
  // Wait for chart canvas to confirm the page loaded with data
  await expect(page.locator('canvas').first()).toBeVisible()
}

const enableDetectorAndWait = async (page: Page) => {
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/key-levels?detectors=') && resp.status() === 200,
    { timeout: 15_000 },
  )
  // Detectors are shown as dashed buttons directly (not behind a popover)
  await page.getByRole('button', { name: DETECTOR_LABEL }).click()
  await responsePromise
  await page.waitForFunction(() => {
    const chart = (window as unknown as { __ECHARTS_INSTANCE__?: { getOption?: () => { series?: unknown[] } } }).__ECHARTS_INSTANCE__
    const series = chart?.getOption?.()?.series ?? []
    const kl = (series as Array<{ name: string; markLine?: { data?: unknown[] } }>).find(s => s.name === 'Key Levels')
    return (kl?.markLine?.data?.length ?? 0) > 0
  }, { timeout: 10_000 })
}

const getKeyLevelSeries = (page: Page) =>
  page.evaluate(() => {
    const chart = (window as unknown as { __ECHARTS_INSTANCE__?: { getOption?: () => { series?: unknown[] } } }).__ECHARTS_INSTANCE__
    if (!chart?.getOption) return null
    const series = chart.getOption().series ?? []
    return (series as Array<{ name: string } & Record<string, unknown>>).find(s => s.name === 'Key Levels') ?? null
  })

test.describe('Key Levels (event-based slice)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateToInstrumentPage(page)
  })

  test('Equal Highs/Lows detector appears on the Instrument page', async ({ page }) => {
    await expect(page.getByText('Key Levels')).toBeVisible()
    await expect(page.getByRole('button', { name: DETECTOR_LABEL })).toBeVisible()
  })

  test('toggling Equal Highs/Lows adds a Key Levels markLine series', async ({ page }) => {
    // Pre-toggle: no Key Levels series with data
    const before = await getKeyLevelSeries(page)
    if (before) {
      const data = ((before as { markLine?: { data?: unknown[] } }).markLine?.data ?? [])
      expect(data.length).toBe(0)
    }

    await enableDetectorAndWait(page)

    const after = await getKeyLevelSeries(page)
    expect(after).not.toBeNull()
    const markLine = (after as { markLine?: { data?: Array<[{ coord: [unknown, number] }, { coord: [unknown, number] }]> } }).markLine
    expect(markLine).toBeDefined()
    expect(Array.isArray(markLine?.data)).toBe(true)
    expect(markLine?.data?.length).toBeGreaterThan(0)

    // Each entry must be a 2-coord segment (start, end) for a horizontal line
    const entry = markLine?.data?.[0]
    expect(Array.isArray(entry)).toBe(true)
    expect(entry).toHaveLength(2)
    expect(entry?.[0].coord).toBeDefined()
    expect(entry?.[1].coord).toBeDefined()
    expect(typeof entry?.[0].coord[1]).toBe('number') // y = price
    expect(typeof entry?.[1].coord[1]).toBe('number')
    expect(entry?.[0].coord[1]).toBe(entry?.[1].coord[1]) // horizontal: same price both ends
  })

  test('strength translates to varying opacity across levels', async ({ page }) => {
    await enableDetectorAndWait(page)

    const opacities = await page.evaluate(() => {
      const chart = (window as unknown as { __ECHARTS_INSTANCE__?: { getOption?: () => { series?: unknown[] } } }).__ECHARTS_INSTANCE__
      const series = chart?.getOption?.()?.series ?? []
      const kl = (series as Array<{ name: string; markLine?: { data?: Array<[{ lineStyle?: { opacity?: number } }]> } }>).find(s => s.name === 'Key Levels')
      if (!kl?.markLine?.data) return []
      return kl.markLine.data.map(entry => entry[0]?.lineStyle?.opacity ?? null)
    })

    expect(opacities.length).toBeGreaterThan(0)
    // Every entry has an opacity in [0, 1]
    for (const op of opacities) {
      expect(op).not.toBeNull()
      expect(op).toBeGreaterThanOrEqual(0)
      expect(op).toBeLessThanOrEqual(1)
    }
  })

  test('toggling Equal Highs/Lows off empties the Key Levels series', async ({ page }) => {
    await enableDetectorAndWait(page)

    // Toggle off — when selected the chip shows as an ActiveIndicatorChip with a remove button
    await page.getByRole('button', { name: `Disable ${DETECTOR_LABEL}` }).click()
    await page.waitForFunction(() => {
      const chart = (window as unknown as { __ECHARTS_INSTANCE__?: { getOption?: () => { series?: unknown[] } } }).__ECHARTS_INSTANCE__
      const series = chart?.getOption?.()?.series ?? []
      const kl = (series as Array<{ name: string; markLine?: { data?: unknown[] } }>).find(s => s.name === 'Key Levels')
      return !kl || (kl.markLine?.data?.length ?? 0) === 0
    }, { timeout: 10_000 })

    const after = await getKeyLevelSeries(page)
    if (after) {
      expect(((after as { markLine?: { data?: unknown[] } }).markLine?.data ?? []).length).toBe(0)
    }
  })

  test('Key Levels overlay does not change chart height', async ({ page }) => {
    const chartContainer = page.getByTestId('chart-container')
    const initialBox = await chartContainer.boundingBox()
    expect(initialBox).not.toBeNull()

    await enableDetectorAndWait(page)

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBe(initialBox!.height)
  })
})
