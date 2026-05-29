# Toggle indicators on/off — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each active indicator chip be toggled on/off by clicking it; only indicators that are both listed and enabled draw on the chart. Frontend-only.

**Architecture:** Add an `enabled` concern to `useIndicators` parallel to the existing `colors` (localStorage, `isEnabled`/`toggleEnabled`). `RunDetailPage` filters indicator results by `isEnabled` before passing them to `CandlestickChart`. `IndicatorChip` toggles on body click and dims when disabled. No backend or `CandlestickChart` changes.

**Tech Stack:** React, TypeScript, Vite, Bun, vitest (unit), Playwright (e2e), eCharts, shadcn/ui.

Run all commands from `packages/client` inside the worktree.

---

## File Structure

- `src/hooks/use-indicators.ts` — add `enabled` state + `isEnabled`/`toggleEnabled` (Task 1).
- `src/hooks/use-indicators.test.ts` — unit tests for the above (Task 1).
- `src/components/chart/indicator-selector/IndicatorChip.tsx` — click-to-toggle + dim + stopPropagation (Task 2).
- `src/components/chart/indicator-selector/IndicatorSelector.tsx` — thread `isEnabled`/`onToggle` (Task 2).
- `src/pages/RunDetailPage.tsx` — filter results by `isEnabled`, pass props to selector (Task 2).
- `e2e/indicator-toggle.spec.ts` — Playwright e2e for the toggle flow (Task 3).

---

## Task 1: Enabled state in `useIndicators` (TDD)

**Files:**
- Modify: `src/hooks/use-indicators.ts`
- Test: `src/hooks/use-indicators.test.ts`

- [ ] **Step 1: Write the failing tests**

Append this `describe` block to `src/hooks/use-indicators.test.ts` (after the closing `})` of the existing `describe('useIndicators', ...)`):

```ts
describe('useIndicators — enabled toggle', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('isEnabled returns true for an unknown id by default', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })
    await waitForSeed(result)
    expect(result.current.isEnabled('never-added')).toBe(true)
  })

  it('toggleEnabled flips an indicator off then back on', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })
    await waitForSeed(result)

    act(() => {
      result.current.toggleEnabled('sma-1')
    })
    expect(result.current.isEnabled('sma-1')).toBe(false)

    act(() => {
      result.current.toggleEnabled('sma-1')
    })
    expect(result.current.isEnabled('sma-1')).toBe(true)
  })

  it('persists the disabled state to localStorage under indicator-enabled-v1', async () => {
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })
    await waitForSeed(result)

    act(() => {
      result.current.toggleEnabled('sma-1')
    })

    const stored = JSON.parse(localStorage.getItem('indicator-enabled-v1') ?? '{}')
    expect(stored['sma-1']).toBe(false)
  })

  it('reads an existing disabled state from localStorage on mount', async () => {
    localStorage.setItem('indicator-enabled-v1', JSON.stringify({ 'sma-1': false }))
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useIndicators('run-123', 'BAR_TYPE'), { wrapper })
    await waitForSeed(result)
    expect(result.current.isEnabled('sma-1')).toBe(false)
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bun run test:unit -- src/hooks/use-indicators.test.ts`
Expected: FAIL — `result.current.isEnabled` / `result.current.toggleEnabled` are `undefined` (not a function).

- [ ] **Step 3: Implement the enabled state in the hook**

In `src/hooks/use-indicators.ts`:

(a) After the `saveColors` function (around line 31), add the storage helpers:

```ts
const ENABLED_STORAGE_KEY = 'indicator-enabled-v1'

const loadEnabled = (): Record<string, boolean> => {
  try {
    const stored = localStorage.getItem(ENABLED_STORAGE_KEY)
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

const saveEnabled = (enabled: Record<string, boolean>) => {
  try {
    localStorage.setItem(ENABLED_STORAGE_KEY, JSON.stringify(enabled))
  } catch {
    // ignore storage errors
  }
}
```

(b) Add state next to the `colors` state (after the `colors` line):

```ts
  const [enabled, setEnabledState] = useState<Record<string, boolean>>(loadEnabled)
```

(c) Add the two callbacks next to `getColor`/`setColor`:

```ts
  const isEnabled = useCallback(
    (id: string): boolean => enabled[id] ?? true,
    [enabled],
  )

  const toggleEnabled = useCallback((id: string) => {
    setEnabledState((prev) => {
      const next = { ...prev, [id]: !(prev[id] ?? true) }
      saveEnabled(next)
      return next
    })
  }, [])
```

(d) Add `isEnabled` and `toggleEnabled` to the returned object, in the `// indicators` section (next to `getColor`, `setColor`):

```ts
    getColor,
    setColor,
    isEnabled,
    toggleEnabled,
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bun run test:unit -- src/hooks/use-indicators.test.ts`
Expected: PASS — all existing tests plus the 4 new ones.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/use-indicators.ts src/hooks/use-indicators.test.ts
git commit -m "feat: add enabled state to useIndicators"
```

---

## Task 2: Wire the toggle through chip → selector → page

This task changes three files together so the build stays green (adding required props to `IndicatorChip` breaks compilation until the selector and page pass them). No unit test — covered by typecheck and the Task 3 e2e.

**Files:**
- Modify: `src/components/chart/indicator-selector/IndicatorChip.tsx`
- Modify: `src/components/chart/indicator-selector/IndicatorSelector.tsx`
- Modify: `src/pages/RunDetailPage.tsx`

- [ ] **Step 1: Update `IndicatorChip`**

In `src/components/chart/indicator-selector/IndicatorChip.tsx`:

(a) Add the `cn` import at the top with the other imports:

```ts
import { cn } from '@/lib/utils'
```

(b) Add `enabled` and `onToggle` to `IndicatorChipProps`:

```ts
type IndicatorChipProps = {
  readonly instance: IndicatorInstance
  readonly type: IndicatorType
  readonly color: string
  readonly enabled: boolean
  readonly onToggle: () => void
  readonly onEdit: () => void
  readonly onRemove: () => void
  readonly onColorChange: (color: string) => void
}
```

(c) Destructure the new props in the component signature:

```ts
export const IndicatorChip = ({
  instance,
  type,
  color,
  enabled,
  onToggle,
  onEdit,
  onRemove,
  onColorChange,
}: IndicatorChipProps) => {
```

(d) Replace the root `<div>` opening tag with click-to-toggle, dim, accessibility, and `data-enabled`:

```tsx
    <div
      className={cn(
        'inline-flex items-center gap-1.5 pl-1 pr-1.5 py-0.5 rounded-md border border-border bg-background text-xs cursor-pointer',
        !enabled && 'opacity-50',
      )}
      data-testid="indicator-chip"
      data-instance-id={instance.id}
      data-enabled={enabled}
      role="button"
      aria-pressed={enabled}
      title={enabled ? 'Click to hide from chart' : 'Click to show on chart'}
      onClick={onToggle}
    >
```

(e) Add `e.stopPropagation()` to the color-swatch `PopoverTrigger` button so opening the color picker does not toggle. Change its button to:

```tsx
          <button
            type="button"
            aria-label={`Change color for ${label}`}
            className="w-3 h-3 rounded-sm border border-border cursor-pointer shrink-0 hover:scale-110 transition-transform"
            style={{ backgroundColor: color }}
            title="Change color"
            onClick={(e) => e.stopPropagation()}
          />
```

(f) Change the edit button's `onClick` to stop propagation before editing:

```tsx
        onClick={(e) => {
          e.stopPropagation()
          onEdit()
        }}
```

(g) Change the remove button's `onClick` to stop propagation before removing:

```tsx
        onClick={(e) => {
          e.stopPropagation()
          onRemove()
        }}
```

- [ ] **Step 2: Update `IndicatorSelector`**

In `src/components/chart/indicator-selector/IndicatorSelector.tsx`:

(a) Add the two props to `IndicatorInstanceSelectorProps`, in the `// indicators` group:

```ts
  readonly getColor: (id: string) => string
  readonly onSetColor: (id: string, color: string) => void
  readonly isEnabled: (id: string) => boolean
  readonly onToggle: (id: string) => void
```

(b) Destructure them in the component signature (next to `getColor`, `onSetColor`):

```ts
  getColor,
  onSetColor,
  isEnabled,
  onToggle,
```

(c) Pass them to `IndicatorChip` in the `.map` (add the two lines alongside `color`):

```tsx
                <IndicatorChip
                  instance={instance}
                  type={type}
                  color={getColor(instance.id)}
                  enabled={isEnabled(instance.id)}
                  onToggle={() => onToggle(instance.id)}
                  onEdit={() => handleEditOpen(instance)}
                  onRemove={() => onRemove(instance.id)}
                  onColorChange={color => onSetColor(instance.id, color)}
                />
```

- [ ] **Step 3: Update `RunDetailPage`**

In `src/pages/RunDetailPage.tsx`:

(a) Add `isEnabled` and `toggleEnabled` to the `useIndicators` destructure (next to `getColor`, `setColor`):

```ts
    getColor,
    setColor,
    isEnabled,
    toggleEnabled,
```

(b) Filter the indicators passed to `CandlestickChart`. Change the `indicators` prop:

```tsx
                indicators={indicatorData?.filter((r) => isEnabled(r.id))}
```

(c) Pass the two new props to `IndicatorInstanceSelector` (next to `getColor`, `onSetColor`):

```tsx
              getColor={getColor}
              onSetColor={setColor}
              isEnabled={isEnabled}
              onToggle={toggleEnabled}
```

- [ ] **Step 4: Typecheck and lint**

Run: `bunx tsc -b --noEmit && bun run lint`
Expected: no type errors, no lint errors.

- [ ] **Step 5: Run unit tests (regression)**

Run: `bun run test:unit`
Expected: PASS — all unit tests still green.

- [ ] **Step 6: Commit**

```bash
git add src/components/chart/indicator-selector/IndicatorChip.tsx src/components/chart/indicator-selector/IndicatorSelector.tsx src/pages/RunDetailPage.tsx
git commit -m "feat: toggle indicators on/off via chip click"
```

---

## Task 3: e2e test for the toggle flow

**Files:**
- Create: `e2e/indicator-toggle.spec.ts`

Pattern notes (from existing specs): the chart exposes `window.__ECHARTS_INSTANCE__`; overlay series are named `"<label> <field>"`, e.g. `"SMA(20) value"`. Use `enableIndicator(page, 'SMA')` from `./helpers`. Clear the run's `viewer_state.json` before/after each test as `indicator-selector.spec.ts` does. The chip carries `data-enabled` and `data-testid="indicator-chip"`.

- [ ] **Step 1: Write the e2e spec**

Create `e2e/indicator-toggle.spec.ts`:

```ts
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

const smaSeriesPresent = (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const series = (chart?.getOption()?.series ?? []) as any[]
    return series.some((s) => typeof s?.name === 'string' && s.name.includes('SMA(20)'))
  })

test.describe('Indicator on/off toggle', () => {
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

  test('toggle hides/shows the indicator on the chart and persists across reload', async ({ page }) => {
    await enableIndicator(page, 'SMA')

    const chip = page.getByTestId('indicator-chip').filter({ hasText: 'SMA(20)' })
    await expect(chip).toBeVisible()
    await expect(chip).toHaveAttribute('data-enabled', 'true')

    // Indicator series present on the chart.
    await expect.poll(() => smaSeriesPresent(page)).toBe(true)

    // Toggle off — click the chip body (label area, away from the controls).
    await chip.getByTestId('indicator-chip-label').click()

    // Chip stays listed but is now disabled, and the series is gone.
    await expect(chip).toHaveAttribute('data-enabled', 'false')
    await expect(chip).toBeVisible()
    await expect.poll(() => smaSeriesPresent(page)).toBe(false)

    // Toggle back on — series returns.
    await chip.getByTestId('indicator-chip-label').click()
    await expect(chip).toHaveAttribute('data-enabled', 'true')
    await expect.poll(() => smaSeriesPresent(page)).toBe(true)

    // Disable again, then reload — disabled state persists via localStorage.
    await chip.getByTestId('indicator-chip-label').click()
    await expect(chip).toHaveAttribute('data-enabled', 'false')

    await page.reload()
    const chipAfterReload = page.getByTestId('indicator-chip').filter({ hasText: 'SMA(20)' })
    await expect(chipAfterReload).toBeVisible()
    await expect(chipAfterReload).toHaveAttribute('data-enabled', 'false')
    await expect.poll(() => smaSeriesPresent(page)).toBe(false)
  })
})
```

> Note: clicking `indicator-chip-label` (the label `<span>` inside the chip) lands on the chip body, which bubbles to the root `div`'s `onClick={onToggle}`. This avoids the color/edit/remove controls, which `stopPropagation`. The label has `data-testid="indicator-chip-label"` (already present in `IndicatorChip`).

- [ ] **Step 2: Run the e2e test headless**

Run: `bun run test:e2e -- indicator-toggle.spec.ts`
Expected: PASS (1 test). Dev servers must be running on the worktree ports; the orchestration step starts them.

- [ ] **Step 3: Commit**

```bash
git add e2e/indicator-toggle.spec.ts
git commit -m "test(e2e): indicator on/off toggle flow"
```

---

## Self-Review

**Spec coverage:**
- AC1 (click toggles) → Task 2 Step 1d; Task 3.
- AC2 (disabled hidden, stays listed) → Task 2 Step 3b (filter); Task 3 assertions.
- AC3 (dimmed) → Task 2 Step 1d (`opacity-50`).
- AC4 (controls don't toggle) → Task 2 Step 1e/1f/1g (`stopPropagation`).
- AC5 (default enabled) → Task 1 Step 3c (`enabled[id] ?? true`); Task 1 test 1.
- AC6 (persist reload) → Task 1 Step 3a/3c; Task 1 tests 3-4; Task 3 reload assertion.
- AC7 (instant, no refetch) → fetch keyed on `instances`, untouched; filter is render-only.
- AC8 (panel/overlay removed) → filter drops the result; `CandlestickChart` rebuilds from prop (no change).
- AC9 (unit test) → Task 1.
- AC10 (e2e) → Task 3.

**Placeholder scan:** none.

**Type consistency:** `isEnabled: (id: string) => boolean` and `toggleEnabled`/`onToggle: (id: string) => void` consistent across hook return, selector props, and page wiring; `IndicatorChip.onToggle: () => void` (selector binds the id).
