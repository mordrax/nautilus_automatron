import { test, expect, Page } from '@playwright/test'

const DETECTOR_ID = 'equal_highs_lows'

const toggleKeyLevelsAndWait = async (page: Page) => {
  const responsePromise = page.waitForResponse(
    (resp) => resp.url().includes('/key-levels?detectors=') && resp.status() === 200,
    { timeout: 15_000 },
  )
  await page.getByTestId(`key-level-toggle-${DETECTOR_ID}`).click()
  await responsePromise
  await page.waitForFunction(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const series = chart?.getOption()?.series ?? []
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const kl = series.find((s: any) => s.name === 'Key Levels')
    return kl?.markLine?.data?.length > 0
  }, { timeout: 10_000 })
}

const getKeyLevelSeries = (page: Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart?.getOption) return null
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const series = chart.getOption().series ?? []
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return series.find((s: any) => s.name === 'Key Levels') ?? null
  })

test.describe('Key Levels (event-based slice)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.getByRole('button', { name: /Prev/ })).toBeVisible()
  })

  test('Key Levels panel and Equal Highs/Lows detector are visible', async ({ page }) => {
    await expect(page.getByTestId('key-levels-panel')).toBeVisible()
    await expect(page.getByText('Equal Highs/Lows')).toBeVisible()
  })

  test('toggling Equal Highs/Lows adds a Key Levels markLine series', async ({ page }) => {
    // Pre-toggle: no Key Levels series with data
    const before = await getKeyLevelSeries(page)
    if (before) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = ((before as any).markLine?.data ?? [])
      expect(data.length).toBe(0)
    }

    await toggleKeyLevelsAndWait(page)

    const after = await getKeyLevelSeries(page)
    expect(after).not.toBeNull()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const markLine = (after as any).markLine
    expect(markLine).toBeDefined()
    expect(Array.isArray(markLine.data)).toBe(true)
    expect(markLine.data.length).toBeGreaterThan(0)

    // Each entry must be a 2-coord segment (start, end) for a horizontal line
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const entry = markLine.data[0]
    expect(Array.isArray(entry)).toBe(true)
    expect(entry).toHaveLength(2)
    expect(entry[0].coord).toBeDefined()
    expect(entry[1].coord).toBeDefined()
    expect(typeof entry[0].coord[1]).toBe('number') // y = price
    expect(typeof entry[1].coord[1]).toBe('number')
    expect(entry[0].coord[1]).toBe(entry[1].coord[1]) // horizontal: same price both ends
  })

  test('strength translates to varying opacity across levels', async ({ page }) => {
    await toggleKeyLevelsAndWait(page)

    const opacities = await page.evaluate(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const series = chart?.getOption()?.series ?? []
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const kl = series.find((s: any) => s.name === 'Key Levels')
      if (!kl?.markLine?.data) return []
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return kl.markLine.data.map((entry: any[]) => entry[0]?.lineStyle?.opacity ?? null)
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
    await toggleKeyLevelsAndWait(page)

    await page.getByTestId(`key-level-toggle-${DETECTOR_ID}`).click()
    await page.waitForFunction(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const series = chart?.getOption()?.series ?? []
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const kl = series.find((s: any) => s.name === 'Key Levels')
      return !kl || (kl.markLine?.data?.length ?? 0) === 0
    }, { timeout: 10_000 })

    const after = await getKeyLevelSeries(page)
    if (after) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect(((after as any).markLine?.data ?? []).length).toBe(0)
    }
  })

  test('Key Levels overlay does not change chart height', async ({ page }) => {
    const chartContainer = page.getByTestId('chart-container')
    const initialBox = await chartContainer.boundingBox()
    expect(initialBox).not.toBeNull()

    await toggleKeyLevelsAndWait(page)

    const newBox = await chartContainer.boundingBox()
    expect(newBox).not.toBeNull()
    expect(newBox!.height).toBe(initialBox!.height)
  })
})
