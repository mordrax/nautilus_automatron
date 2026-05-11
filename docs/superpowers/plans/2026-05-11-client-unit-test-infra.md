# Client Unit Test Infrastructure + 50-Bar Chart Default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Vitest unit testing in `packages/client`, extract the chart's default-visible-bars math into a pure helper, change the production default from 500 to 50, and unit-test the helper directly.

**Architecture:** A single new module `src/lib/chart-zoom.ts` holds the pure helper and the `DEFAULT_VISIBLE_BARS` constant. `CandlestickChart.tsx` imports the helper instead of inlining the math. Vitest configuration is added as a `test` block on the existing `vite.config.ts` (no new config file). Unit tests live next to the helper as `chart-zoom.test.ts`. The existing Playwright `default-zoom.spec.ts` is trimmed to a smoke check.

**Tech Stack:** Vitest 5.0.0-beta.2 (first version with Vite 8 support), Vite 8, React 19, TypeScript 5.9, Bun (package manager). No `jsdom`, no `@testing-library/react`, no setup file — pure-logic tests only.

**Spec:** `docs/superpowers/specs/2026-05-11-client-unit-test-infra-design.md`
**Trello:** https://trello.com/c/zh8Htuaw
**Branch:** `feat/client-unit-test-infra`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `packages/client/package.json` | Modify | Add `vitest@5.0.0-beta.2` devDep, add `test:unit` and `test:unit:watch` scripts |
| `packages/client/vite.config.ts` | Modify | Add `test` block at end of returned config; add `/// <reference types="vitest" />` |
| `packages/client/src/lib/chart-zoom.ts` | Create | Pure helper `computeDefaultStart` + `DEFAULT_VISIBLE_BARS` constant |
| `packages/client/src/lib/chart-zoom.test.ts` | Create | 6 unit tests covering boundary cases |
| `packages/client/src/components/chart/CandlestickChart.tsx` | Modify | Replace inline math (lines 142–146) with `computeDefaultStart(categoryData.length)` import call |
| `packages/client/e2e/default-zoom.spec.ts` | Modify | Trim to smoke check (assert `end === 100` and `start > 0`); drop tautological math assertions |
| `packages/client/bun.lock` | Auto-modify | Updated by `bun install` |

---

## Task 1: Install Vitest 5 beta and add npm scripts

**Files:**
- Modify: `packages/client/package.json`

- [ ] **Step 1: Add vitest@5.0.0-beta.2 as a devDependency**

Run from the repo root:

```bash
cd /Users/mordrax/code/nautilus_automatron && bun add -d -E vitest@5.0.0-beta.2 --cwd packages/client
```

The `-E` flag pins the exact version (no caret); this is required per the spec since 5.0.0-beta is a beta release we don't want to silently advance.

Expected: `bun.lock` updated, `package.json` shows `"vitest": "5.0.0-beta.2"` in `devDependencies` (no caret prefix).

- [ ] **Step 2: Verify pinned version**

Run:

```bash
grep -A1 '"devDependencies"' packages/client/package.json | grep -A1 vitest
```

Expected output (note: no leading `^`):

```
    "vitest": "5.0.0-beta.2"
```

If you see `"^5.0.0-beta.2"` instead, fix it by editing `package.json` to remove the caret, then run `cd packages/client && bun install` to regenerate the lockfile.

- [ ] **Step 3: Add the test scripts**

Edit `packages/client/package.json`. In the `"scripts"` block, add two new entries after the existing `"test:e2e:ui"` line:

```json
    "test:unit": "vitest run",
    "test:unit:watch": "vitest"
```

The final scripts block should look like:

```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "test:e2e": "playwright test --project=headless",
    "test:e2e:headed": "playwright test --project=headed",
    "test:e2e:ui": "playwright test --ui",
    "test:unit": "vitest run",
    "test:unit:watch": "vitest"
  },
```

- [ ] **Step 4: Verify Vitest is installed and resolvable**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx vitest --version
```

Expected: prints a version starting with `5.0.0-beta`.

- [ ] **Step 5: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron && git add packages/client/package.json bun.lock && git commit -m "$(cat <<'EOF'
chore(client): add vitest 5 beta for unit testing

Vitest 4.x peer-deps on Vite ^6 || ^7 only; vite 8 support landed in
5.0.0-beta.2. Pinned exact (no caret) — beta upgrades should be
intentional. No jsdom / RTL yet; first use is pure-logic tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Configure Vitest via vite.config.ts

**Files:**
- Modify: `packages/client/vite.config.ts`

- [ ] **Step 1: Add Vitest types reference and test block**

Replace the entire contents of `packages/client/vite.config.ts` with:

```ts
/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, '../..'), '')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: parseInt(env.VITE_PORT ?? '5173'),
      strictPort: true,
      proxy: {
        '/api': env.VITE_API_URL ?? 'http://localhost:8000',
      },
    },
    test: {
      include: ['src/**/*.test.ts'],
      environment: 'node',
    },
  }
})
```

Two additions:
1. `/// <reference types="vitest" />` at the top — exposes Vitest's TS types so the `test` field is typed.
2. The `test` block — explicit `include` pattern for `src/**/*.test.ts` (excludes `e2e/`), `environment: 'node'` (default but explicit to avoid surprises).

- [ ] **Step 2: Verify Vitest resolves config and finds zero tests**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx vitest run --passWithNoTests
```

Expected: exits 0 with output mentioning "No test files found" (Vitest's normal message when nothing matches `src/**/*.test.ts` yet). If you see a config-parse error, the `test` block is malformed — fix and re-run.

- [ ] **Step 3: Verify the existing Vite build still works**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc -b --noEmit
```

Expected: exits 0 with no output. This confirms the new `<reference types="vitest" />` directive resolves (Vitest's types are installed transitively).

- [ ] **Step 4: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron && git add packages/client/vite.config.ts && git commit -m "$(cat <<'EOF'
chore(client): add vitest test block to vite.config.ts

Shares the same defineConfig as the build, so transforms, plugins, and
the @/ path alias are reused without mergeConfig boilerplate. Pure-node
environment, src/**/*.test.ts include pattern.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: TDD — write the failing unit tests

**Files:**
- Create: `packages/client/src/lib/chart-zoom.test.ts`

- [ ] **Step 1: Create the test file with all 6 cases**

Create `packages/client/src/lib/chart-zoom.test.ts` with this exact content:

```ts
import { describe, expect, it } from 'vitest'
import { computeDefaultStart } from './chart-zoom'

describe('computeDefaultStart', () => {
  it('returns 0 when the dataset is empty', () => {
    expect(computeDefaultStart(0)).toBe(0)
  })

  it('returns 0 when the dataset is smaller than the default window', () => {
    expect(computeDefaultStart(30)).toBe(0)
  })

  it('returns 0 when the dataset is exactly the default window', () => {
    expect(computeDefaultStart(50)).toBe(0)
  })

  it('returns a small positive percentage when one bar past the default', () => {
    expect(computeDefaultStart(51)).toBeCloseTo((1 / 51) * 100, 10)
  })

  it('returns 95 for 1000 bars with the 50-bar default', () => {
    expect(computeDefaultStart(1000)).toBe(95)
  })

  it('respects a custom visible-window override', () => {
    expect(computeDefaultStart(1000, 100)).toBe(90)
  })
})
```

Six cases total, matching the spec's acceptance criterion #1 ("6 passing tests"). Do NOT import `DEFAULT_VISIBLE_BARS` — the tsconfig has `noUnusedLocals: true` and the constant isn't referenced directly (the default-arg behaviour is verified via the cases that use 50 implicitly).

Note: assertions use concrete numbers (`toBe(0)`, `toBe(95)`, `toBe(90)`) — these do NOT re-derive the production formula. Only the float-boundary case uses `toBeCloseTo`, which is the necessary exception.

- [ ] **Step 2: Run the tests to verify they fail with "cannot resolve module"**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx vitest run
```

Expected: tests fail at the import step — message similar to "Failed to load url ./chart-zoom from src/lib/chart-zoom.test.ts" or "Module not found". This confirms the test runner is wired correctly and the missing implementation file is what's blocking the tests.

If the failure message is anything else (e.g. config error, transform error), stop and fix the config before proceeding.

---

## Task 4: Implement chart-zoom.ts to make the tests pass

**Files:**
- Create: `packages/client/src/lib/chart-zoom.ts`

- [ ] **Step 1: Create the helper file**

Create `packages/client/src/lib/chart-zoom.ts` with this exact content:

```ts
export const DEFAULT_VISIBLE_BARS = 50

export const computeDefaultStart = (
  totalBars: number,
  visible: number = DEFAULT_VISIBLE_BARS,
): number => {
  if (totalBars <= visible) return 0
  return ((totalBars - visible) / totalBars) * 100
}
```

- [ ] **Step 2: Run the tests to verify they all pass**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx vitest run
```

Expected:

```
 ✓ src/lib/chart-zoom.test.ts  (6 tests)
   ✓ computeDefaultStart > returns 0 when the dataset is empty
   ✓ computeDefaultStart > returns 0 when the dataset is smaller than the default window
   ✓ computeDefaultStart > returns 0 when the dataset is exactly the default window
   ✓ computeDefaultStart > returns a small positive percentage when one bar past the default
   ✓ computeDefaultStart > returns 95 for 1000 bars with the 50-bar default
   ✓ computeDefaultStart > respects a custom visible-window override

 Test Files  1 passed (1)
      Tests  6 passed (6)
```

If any test fails, do NOT modify the test — re-read the production code and fix the bug there.

- [ ] **Step 3: Run typecheck**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc -b --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 4: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron && git add packages/client/src/lib/chart-zoom.ts packages/client/src/lib/chart-zoom.test.ts && git commit -m "$(cat <<'EOF'
feat(chart): add pure computeDefaultStart helper

Extracts the chart default-visible-bars math into src/lib/chart-zoom.ts
so it can be tested directly. Constant DEFAULT_VISIBLE_BARS = 50 is the
single source of truth for the initial chart window.

Test coverage: empty dataset, smaller than window, equal to window, one
past window (float boundary), much larger than window, custom override.
Assertions use concrete numbers, not re-derived formulas — closes the
"tautological assertion" gap flagged in PR #47 review.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Wire helper into CandlestickChart.tsx

**Files:**
- Modify: `packages/client/src/components/chart/CandlestickChart.tsx` (lines 140–146)

- [ ] **Step 1: Find the current inline math block**

Run:

```bash
grep -n "defaultVisibleBars\|defaultStart" packages/client/src/components/chart/CandlestickChart.tsx
```

Expected output (the block to replace):

```
142:  const defaultVisibleBars = 500
143:  const totalBars = categoryData.length
144:  const defaultStart = totalBars > defaultVisibleBars
145:    ? ((totalBars - defaultVisibleBars) / totalBars) * 100
146:    : 0
177:      { type: 'inside', start: defaultStart, end: 100, xAxisIndex: allXAxisIndices },
178:      { type: 'slider', start: defaultStart, end: 100, bottom: '2%', xAxisIndex: allXAxisIndices },
```

If line numbers differ, locate the equivalent block before proceeding.

- [ ] **Step 2: Add the import**

In `packages/client/src/components/chart/CandlestickChart.tsx`, add the import near the other `@/` imports. Find the existing line:

```ts
import { CHART_COLORS, getDefaultIndicatorColor } from '@/lib/chart-config'
```

Add this directly underneath:

```ts
import { computeDefaultStart } from '@/lib/chart-zoom'
```

- [ ] **Step 3: Replace the inline math with the helper call**

Replace the entire block:

```ts
  const defaultVisibleBars = 500
  const totalBars = categoryData.length
  const defaultStart = totalBars > defaultVisibleBars
    ? ((totalBars - defaultVisibleBars) / totalBars) * 100
    : 0
```

with this single line:

```ts
  const defaultStart = computeDefaultStart(categoryData.length)
```

Leave the two `dataZoom` entries that consume `defaultStart` unchanged — they still read `start: defaultStart, end: 100`.

- [ ] **Step 4: Run typecheck**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc -b --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 5: Run lint**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bun run lint
```

Expected: exits 0 with no errors.

- [ ] **Step 6: Run unit tests again to confirm the helper is consumed**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx vitest run
```

Expected: all 6 tests still pass. (Sanity check that nothing in the rewire broke imports.)

- [ ] **Step 7: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron && git add packages/client/src/components/chart/CandlestickChart.tsx && git commit -m "$(cat <<'EOF'
feat(chart): default zoom to last 50 bars via shared helper

CandlestickChart now imports computeDefaultStart from @/lib/chart-zoom
instead of inlining the math. The user-facing change is the default
visible window dropping from 500 to 50 bars (DEFAULT_VISIBLE_BARS in
chart-zoom.ts). Affects both RunDetailPage and InstrumentPage, which
both consume CandlestickChart.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Trim the e2e default-zoom smoke check

**Files:**
- Modify: `packages/client/e2e/default-zoom.spec.ts`

- [ ] **Step 1: Replace the entire spec with the trimmed smoke check**

Replace the entire contents of `packages/client/e2e/default-zoom.spec.ts` with:

```ts
import { test, expect } from '@playwright/test'

const getZoom = (page: import('@playwright/test').Page) =>
  page.evaluate(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const chart = (window as any).__ECHARTS_INSTANCE__
    if (!chart) return null
    const opt = chart.getOption()
    const zoom = opt?.dataZoom?.[0]
    return zoom ? { start: zoom.start as number, end: zoom.end as number } : null
  })

test.describe('Default chart zoom', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    const runsSection = page.locator('section', { has: page.getByText('Backtest Runs') })
    const grid = runsSection.locator('[role="grid"]')
    await expect(grid).toBeVisible()
    await grid.getByRole('button', { name: 'View' }).first().click()
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
    await expect(page.locator('canvas').first()).toBeVisible()
    await page.waitForFunction(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const chart = (window as any).__ECHARTS_INSTANCE__
      const opt = chart?.getOption()
      return Array.isArray(opt?.xAxis?.[0]?.data) && opt.xAxis[0].data.length > 0
    })
  })

  test('chart opens with a default window applied (not full range)', async ({ page }) => {
    const zoom = await getZoom(page)
    expect(zoom).not.toBeNull()
    expect(zoom!.end).toBe(100)
    expect(zoom!.start).toBeGreaterThan(0)
  })
})
```

Two structural changes from the previous version:
1. The `getZoom` helper no longer returns `total` (the math case that used it is gone).
2. The single test asserts only the smoke conditions: `end === 100` and `start > 0`. The visible-bar math is fully covered by unit tests.

- [ ] **Step 2: Run the trimmed spec headless**

First find two available ports (do NOT use 5173 or 8000 — those are the main repo's):

```bash
lsof -i :5180 -i :8010 2>/dev/null | head -5
```

If both ports are free (no output), use them. Otherwise pick higher numbers (e.g. 5181/8011) until both are free.

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && TEST_VITE_PORT=5180 TEST_API_PORT=8010 bunx playwright test default-zoom.spec.ts --project=headless
```

Expected output (last few lines):

```
  1 passed (Xs)
```

If the test fails, do NOT modify the assertion thresholds — debug the actual rendering. The 1000-bar e2e dataset should satisfy `start > 0` under the 50-bar default (`start ≈ 95`).

- [ ] **Step 3: Run typecheck and lint**

Run:

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc -b --noEmit && bun run lint
```

Expected: both exit 0.

- [ ] **Step 4: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron && git add packages/client/e2e/default-zoom.spec.ts && git commit -m "$(cat <<'EOF'
test(e2e): trim default-zoom spec to a wiring smoke check

The visible-bar math is now unit-tested in chart-zoom.test.ts using
concrete-number assertions. This e2e spec is kept as a smoke check
that the helper is actually wired into the chart's dataZoom: opens a
run, asserts end === 100 and start > 0. Drops the tautological math
re-derivation flagged in PR #47 review.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Final acceptance verification

**Files:**
- None modified; this is a verification-only task.

- [ ] **Step 1: Run unit tests**

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bun run test:unit
```

Expected: exits 0 with 6 passing tests in `src/lib/chart-zoom.test.ts`, matching spec acceptance criterion #1.

- [ ] **Step 2: Run typecheck**

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc -b --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 3: Run lint**

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bun run lint
```

Expected: exits 0 with no output.

- [ ] **Step 4: Run the trimmed e2e spec**

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && TEST_VITE_PORT=5180 TEST_API_PORT=8010 bunx playwright test default-zoom.spec.ts --project=headless
```

Expected: `1 passed`.

- [ ] **Step 5: Verify the constant value**

```bash
grep "DEFAULT_VISIBLE_BARS = " packages/client/src/lib/chart-zoom.ts
```

Expected: `export const DEFAULT_VISIBLE_BARS = 50`

- [ ] **Step 6: Verify no files outside the spec's allowed set were touched**

```bash
git diff --name-only main..HEAD
```

Expected output (exactly these 7 paths — `bun.lock` is the auto-update from Task 1):

```
bun.lock
docs/superpowers/specs/2026-05-11-client-unit-test-infra-design.md
packages/client/e2e/default-zoom.spec.ts
packages/client/package.json
packages/client/src/components/chart/CandlestickChart.tsx
packages/client/src/lib/chart-zoom.test.ts
packages/client/src/lib/chart-zoom.ts
packages/client/vite.config.ts
```

If any other file appears, stop and report — it indicates scope drift.

- [ ] **Step 7: Report to the human**

Report:

```
Implementation complete. Acceptance criteria:
  ✓ bun run test:unit → 6 passing
  ✓ bunx tsc -b --noEmit → 0 errors
  ✓ bun run lint → 0 errors
  ✓ default-zoom.spec.ts (headless) → 1 passing
  ✓ DEFAULT_VISIBLE_BARS === 50
  ✓ File scope matches spec (no drift)

Browser validation (Step 8 of feature-orchestration) is still required
before moving the Trello card to Review.
```

---

## Notes for the executing agent

- **You are NOT in a worktree for this card.** This card was started before the feature-orchestration skill was updated to require worktree-first; the branch `feat/client-unit-test-infra` lives in the main repo at `/Users/mordrax/code/nautilus_automatron`. Future cards will be worktree-first. For this card, run all commands from the main repo path.
- **Bun, not npm.** The repo's package manager is Bun. Always `bun add -d -E`, `bun install`, `bun run <script>`. Use `bunx` to run binaries.
- **Pinned exact, not caret.** When adding Vitest, `-E` (exact) is required because we're on a beta. Do not let `bun add` default to caret.
- **Test failures fix the production code, not the assertion.** If a test in `chart-zoom.test.ts` fails after Task 4, the bug is in `chart-zoom.ts`. The assertions were derived directly from the spec and are correct.
- **Worktree ports don't apply.** Since we're not in a worktree, the dev servers stay on their default ports (5173, 8000). Use 5180/8010 for the Playwright run.
