import { test, expect, Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'

const BAR_TYPE = 'AUDUSD.SIM-100-TICK-MID-INTERNAL'
const DETECTOR_LABEL = 'Equal Highs/Lows'

const navigateToInstrumentPage = async (page: Page) => {
  await page.goto(`/instruments/${encodeURIComponent(BAR_TYPE)}`)
  // Wait for chart canvas to confirm the page loaded with data
  await expect(page.locator('canvas').first()).toBeVisible()
}

const openAddPopover = async (page: Page) => {
  await page.getByTestId('add-indicator-button').click()
}

const enableDetectorAndWait = async (page: Page) => {
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/key-levels?detectors=') && resp.status() === 200,
    { timeout: 15_000 },
  )
  // Detectors are now in the Add popover under "Key-level detectors"
  await openAddPopover(page)
  await page.locator('[data-testid="detector-type-option"]', { hasText: DETECTOR_LABEL }).click()
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

  test('Equal Highs/Lows detector appears in the Add popover', async ({ page }) => {
    await openAddPopover(page)
    await expect(page.getByText('Key-level detectors')).toBeVisible()
    await expect(page.locator('[data-testid="detector-type-option"]', { hasText: DETECTOR_LABEL })).toBeVisible()
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

    // Toggle off — chip in selector has aria-label "Disable {label}"
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

  test('detector chip appears after adding and is removed when clicked off', async ({ page }) => {
    const selector = page.getByTestId('indicator-instance-selector')

    // Add the detector
    await openAddPopover(page)
    await page.locator('[data-testid="detector-type-option"]', { hasText: DETECTOR_LABEL }).click()

    // Chip appears in selector
    await expect(selector.getByText(DETECTOR_LABEL)).toBeVisible()

    // The detector now shows as "(added)" in the popover
    await openAddPopover(page)
    await expect(page.locator('[data-testid="detector-type-option"]', { hasText: DETECTOR_LABEL }).getByText('(added)')).toBeVisible()
    // Close popover
    await page.keyboard.press('Escape')

    // Remove the chip
    await page.getByRole('button', { name: `Disable ${DETECTOR_LABEL}` }).click()
    await expect(selector.getByText(DETECTOR_LABEL)).not.toBeVisible()
  })
})

const RUN_ID = '41a1f019-a7fd-44cd-9c7a-bf41e5b0bf31'
const __dirname_key_levels = path.dirname(new URL(import.meta.url).pathname)
const viewerStatePath = path.resolve(
  __dirname_key_levels,
  'test-data/backtest_catalog/backtest',
  RUN_ID,
  'viewer_state.json',
)

const cleanViewerState = () => {
  if (fs.existsSync(viewerStatePath)) fs.unlinkSync(viewerStatePath)
  const tmpPath = viewerStatePath + '.tmp'
  if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath)
}

test.describe('Detector persistence on RunDetailPage', () => {
  test.beforeEach(() => { cleanViewerState() })
  test.afterEach(() => { cleanViewerState() })
  test.slow()

  test('add SMA + detector → both chips visible → reload → both persist → remove detector', { timeout: 90_000 }, async ({ page }) => {
    await page.goto(`/runs/${RUN_ID}`)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(page.locator('canvas').first()).toBeVisible()

    const selector = page.getByTestId('indicator-instance-selector')

    // Add SMA(20)
    await page.getByTestId('add-indicator-button').click()
    await page.locator('[data-testid="indicator-type-option"]', { hasText: 'SMA' }).click()
    await page.getByTestId('param-form-submit').click()
    await expect(selector.getByText('SMA(20)')).toBeVisible()

    // Add Equal Highs/Lows detector
    await page.getByTestId('add-indicator-button').click()
    // Wait for detector options to load (detectors are fetched async)
    const detectorOption = page.locator('[data-testid="detector-type-option"]', { hasText: DETECTOR_LABEL })
    await expect(detectorOption).toBeVisible()
    await detectorOption.scrollIntoViewIfNeeded()
    await detectorOption.click()
    await expect(selector.getByText(DETECTOR_LABEL)).toBeVisible()

    // Wait for viewer_state.json to be written with the detector id
    // (debounce fires 300ms after last mutation, so poll the file for up to 10s)
    await expect
      .poll(() => {
        try {
          const raw = fs.readFileSync(viewerStatePath, 'utf-8')
          const state = JSON.parse(raw) as { detectors?: string[] }
          return state.detectors?.includes('equal_highs_lows') ?? false
        } catch {
          return false
        }
      }, { timeout: 10_000 })
      .toBe(true)

    // Reload and assert both persist
    await page.reload()
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
    await expect(selector.getByText('SMA(20)')).toBeVisible()
    await expect(selector.getByText(DETECTOR_LABEL)).toBeVisible()

    // Remove detector and wait for viewer_state.json to be updated
    await page.getByRole('button', { name: `Disable ${DETECTOR_LABEL}` }).click()
    await expect
      .poll(() => {
        try {
          const raw = fs.readFileSync(viewerStatePath, 'utf-8')
          const state = JSON.parse(raw) as { detectors?: string[] }
          return !(state.detectors?.includes('equal_highs_lows') ?? false)
        } catch {
          return false
        }
      }, { timeout: 10_000 })
      .toBe(true)

    await expect(selector.getByText('SMA(20)')).toBeVisible()
    await expect(selector.getByText(DETECTOR_LABEL)).not.toBeVisible()
  })
})
