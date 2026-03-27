# Trades by Month Bar Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bar chart showing the number of trades per month, wired into the existing "Trades by Month" tab on the Run Detail page.

**Architecture:** Pure utility function groups trades by YYYY-MM of `exit_datetime`, chart component follows the exact same pattern as `PnlDistributionChart` (simplest existing chart — no click handlers). The tab placeholder already exists in `RunDetailPage.tsx` at line 252 — we just replace the "Coming soon" div.

**Tech Stack:** eCharts 6, React, TypeScript, Playwright

**Trello Card:** [#90 — Trade Analysis: Trades by Month Bar Chart](https://trello.com/c/vPVy6mG1/90-trade-analysis-trades-by-month-bar-chart)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `packages/client/src/lib/trade-analysis.ts` | Add `computeTradesByMonth()` utility |
| Create | `packages/client/src/components/chart/TradesByMonthChart.tsx` | eCharts bar chart component |
| Modify | `packages/client/src/pages/RunDetailPage.tsx` | Wire chart into "Trades by Month" tab |
| Create | `packages/client/e2e/trades-by-month.spec.ts` | Playwright e2e tests |

---

### Task 1: Add `computeTradesByMonth` utility function

**Files:**
- Modify: `packages/client/src/lib/trade-analysis.ts`

- [ ] **Step 1: Add the `TradesByMonth` type and `computeTradesByMonth` function**

Append to the end of `packages/client/src/lib/trade-analysis.ts`:

```typescript
export type TradesByMonth = {
  readonly months: readonly string[]
  readonly counts: readonly number[]
}

export const computeTradesByMonth = (trades: readonly Trade[]): TradesByMonth => {
  if (trades.length === 0) return { months: [], counts: [] }

  const monthCounts = new Map<string, number>()

  for (const trade of trades) {
    const month = trade.exit_datetime.slice(0, 7) // "YYYY-MM"
    monthCounts.set(month, (monthCounts.get(month) ?? 0) + 1)
  }

  const sorted = [...monthCounts.entries()].sort(([a], [b]) => a.localeCompare(b))

  return {
    months: sorted.map(([m]) => m),
    counts: sorted.map(([, c]) => c),
  }
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd packages/client && npx tsc -b --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/lib/trade-analysis.ts
git commit -m "feat: add computeTradesByMonth utility function"
```

---

### Task 2: Create `TradesByMonthChart` component

**Files:**
- Create: `packages/client/src/components/chart/TradesByMonthChart.tsx`

- [ ] **Step 1: Create the chart component**

Create `packages/client/src/components/chart/TradesByMonthChart.tsx`:

```tsx
import { useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { CHART_COLORS } from '@/lib/chart-config'
import { computeTradesByMonth } from '@/lib/trade-analysis'
import type { Trade } from '@/types/api'

type TradesByMonthChartProps = {
  readonly trades: readonly Trade[]
}

const buildOption = (trades: readonly Trade[]): echarts.EChartsOption => {
  const { months, counts } = computeTradesByMonth(trades)

  return {
    animation: false,
    title: { text: 'Trades by Month', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const p = (params as readonly { readonly value: number; readonly name: string }[])[0]
        return `${p.name}<br/>Trades: ${p.value}`
      },
    },
    xAxis: {
      type: 'category',
      data: months as string[],
      name: 'Month',
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: 'Trades',
      minInterval: 1,
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: '2%' },
    ],
    grid: { left: '8%', right: '5%', bottom: '18%', top: '15%' },
    series: [
      {
        type: 'bar',
        data: counts.map(c => ({
          value: c,
          itemStyle: { color: CHART_COLORS.tradeWin },
        })),
      },
    ],
  }
}

export const TradesByMonthChart = ({ trades }: TradesByMonthChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chart.setOption(buildOption(trades))

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
    }
  }, [trades])

  return (
    <div
      ref={chartDivRef}
      data-testid="trades-by-month-chart"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd packages/client && npx tsc -b --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/components/chart/TradesByMonthChart.tsx
git commit -m "feat: add TradesByMonthChart component"
```

---

### Task 3: Wire chart into RunDetailPage

**Files:**
- Modify: `packages/client/src/pages/RunDetailPage.tsx`

- [ ] **Step 1: Add the import**

Add after the `EquityCurveChart` import (line 10 of RunDetailPage.tsx):

```typescript
import { TradesByMonthChart } from '@/components/chart/TradesByMonthChart'
```

- [ ] **Step 2: Replace the "Coming soon" placeholder**

Replace the `trades-by-month` TabsContent (lines 252-254):

```tsx
        <TabsContent value="trades-by-month" className="min-h-[400px]">
          <div className="flex items-center justify-center h-[400px] text-muted-foreground">Coming soon</div>
        </TabsContent>
```

With:

```tsx
        <TabsContent value="trades-by-month" className="min-h-[400px]">
          {trades && trades.length > 0 ? (
            <Card>
              <CardContent className="p-2">
                <div className="h-[500px]">
                  <TradesByMonthChart trades={trades} />
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-[400px] text-muted-foreground">
              Loading trade data...
            </div>
          )}
        </TabsContent>
```

- [ ] **Step 3: Verify types compile and lint passes**

Run: `cd packages/client && npx tsc -b --noEmit && bun run lint`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add packages/client/src/pages/RunDetailPage.tsx
git commit -m "feat: wire TradesByMonthChart into Trades by Month tab"
```

---

### Task 4: Write Playwright e2e tests

**Files:**
- Create: `packages/client/e2e/trades-by-month.spec.ts`

**Context for test author:** The test navigates to a run detail page (first run in the runs table). The "Trades by Month" tab already exists in the tab list. Clicking it should show the chart. The eCharts instance is on the DOM element — access internal data via the `_ec_` prefixed property key (see `chart-analysis.spec.ts` for the pattern). The `data-testid` is `trades-by-month-chart`.

- [ ] **Step 1: Create the test file**

Create `packages/client/e2e/trades-by-month.spec.ts`:

```typescript
import { test, expect } from '@playwright/test'

test.describe('Trades by Month Chart', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const firstRow = page.locator('table tbody tr').first()
    await firstRow.waitFor()
    await firstRow.click()
    await page.waitForURL(/\/runs\//)

    // Switch to Trades by Month tab
    await page.getByRole('tab', { name: 'Trades by Month' }).click()
  })

  test('chart renders with a canvas element', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    const canvas = chart.locator('canvas')
    await expect(canvas).toBeVisible()
  })

  test('chart container has expected height', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    const box = await chart.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.height).toBeGreaterThanOrEqual(450)
    expect(box!.height).toBeLessThanOrEqual(550)
  })

  test('bar count matches number of distinct trade months', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    // Wait for eCharts to render
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')
      if (!el) return false
      const key = Object.keys(el).find(k => k.startsWith('_ec_'))
      return !!key
    })

    const barCount = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')!
      const key = Object.keys(el).find(k => k.startsWith('_ec_'))!
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (el as any)[key]
      const option = chart.getOption()
      return option.xAxis[0].data.length
    })

    expect(barCount).toBeGreaterThan(0)
  })

  test('total trades across all bars equals total trade count', async ({ page }) => {
    const chart = page.getByTestId('trades-by-month-chart')
    await expect(chart).toBeVisible()

    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')
      if (!el) return false
      const key = Object.keys(el).find(k => k.startsWith('_ec_'))
      return !!key
    })

    const { barTotal, tableTotal } = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="trades-by-month-chart"]')!
      const key = Object.keys(el).find(k => k.startsWith('_ec_'))!
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (el as any)[key]
      const option = chart.getOption()
      const data = option.series[0].data as { value: number }[]
      const barTotal = data.reduce((sum: number, d: { value: number }) => sum + d.value, 0)

      // Get total trades from the Trades tab badge
      const badge = document.querySelector('[data-slot="badge"]')
      const text = badge?.textContent ?? '0'
      const tableTotal = parseInt(text.replace(/[^0-9]/g, ''), 10)

      return { barTotal, tableTotal }
    })

    expect(barTotal).toBe(tableTotal)
  })
})
```

- [ ] **Step 2: Run tests headless**

Run: `cd packages/client && bun run test:e2e -- --grep "Trades by Month"`
Expected: All 4 tests pass

- [ ] **Step 3: Commit**

```bash
git add packages/client/e2e/trades-by-month.spec.ts
git commit -m "test: add Playwright e2e tests for trades-by-month chart"
```

---

## Execution Checklist

1. Task 1 — `computeTradesByMonth` utility (pure function)
2. Task 2 — `TradesByMonthChart` component (eCharts bar chart)
3. Task 3 — Wire into `RunDetailPage` (replace "Coming soon" placeholder)
4. Task 4 — Playwright e2e tests
