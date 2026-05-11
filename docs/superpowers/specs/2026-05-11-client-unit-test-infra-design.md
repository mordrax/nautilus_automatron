# Client Unit Test Infrastructure + 50-Bar Chart Default

**Trello:** https://trello.com/c/zh8Htuaw
**Status:** Approved design (2026-05-11)

## Background

`packages/client` has no unit test runner today — only Playwright e2e. The recent code review of PR #47 (chart default zoom to last 500 bars) flagged the math as test-worthy pure logic that was only covered indirectly by an e2e test that re-derived the same formula it was asserting.

This change does two things in one PR:

1. Stand up a Vitest unit test suite in `packages/client`.
2. Use it for the first real test: extract the chart's "default visible bars" math into a pure helper, change the production default from 500 to 50, and unit-test the helper directly.

The 50-bar default isn't the headline change — it's the vehicle that proves the unit test pattern works on something real instead of a synthetic example.

## Goals

- A working `bun run test:unit` command in `packages/client` that runs Vitest against pure-logic tests.
- A reusable pattern for future pure-helper tests: co-located `foo.ts` + `foo.test.ts` in `src/lib/`.
- The chart's default-visible-bars math lives in a pure, exported function.
- Production default changes from 500 → 50 visible bars on initial chart render.
- Unit tests cover the boundary cases that the prior Playwright spec couldn't.

## Non-Goals

- Component testing, hook testing, or DOM testing. These need `jsdom` + `@testing-library/react` and will be a follow-up card once the infrastructure exists and there's a real first use case.
- Effect-TS runtime testing (`Effect.runSync` / `TestContext`). Same — defer to a follow-up card.
- Server-side test changes.
- CI changes. Unit tests are a local-only check per durable user feedback; the existing Playwright e2e suite remains the authoritative PR gate.

## Design

### Test runner

**Vitest**, minimal install. Vitest is the canonical pairing for Vite-based projects: shares Vite's config (so TS/JSX/path aliases just work), Jest-compatible API, first-party VS Code extension, and is what the React + Vite ecosystem has converged on. Bun runs Vitest fine — we keep Bun as the package manager and runtime; Vitest becomes the test runner for `packages/client`.

DevDependencies to add: `vitest` only. No `jsdom`, no `@testing-library/react`, no setup file — the first test is pure logic over numbers.

### Config

Add a `test` block to the existing `packages/client/vite.config.ts` rather than introducing a separate `vitest.config.ts`. Vitest reads the `test` field from `vite.config.ts`, so transforms, plugins, and path aliases are shared automatically without `mergeConfig` boilerplate or risk of drift between two files. No `environment` override (defaults to `node`, correct for pure-logic tests). A separate `vitest.config.ts` is a fine future option if test config grows enough to warrant it, but is unwarranted today.

### Scripts

Added to `packages/client/package.json`:

- `"test:unit": "vitest run"` — one-shot, used from the terminal and in iteration.
- `"test:unit:watch": "vitest"` — interactive watch mode for fast inner-loop feedback.

No `test` alias to avoid confusion with the existing `test:e2e` scripts.

### Helper extraction

New file `packages/client/src/lib/chart-zoom.ts`:

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

The helper lives in `src/lib/` alongside other pure helpers (`chart-config.ts`, `trade-utils.ts`, etc.) — that's the established home for framework-agnostic, freely testable code. The `visible` parameter is overridable so future callers can pass a different window without hardcoding 50 everywhere.

### Helper consumer

In `packages/client/src/components/chart/CandlestickChart.tsx`, replace the inline math block:

```ts
const defaultVisibleBars = 500
const totalBars = categoryData.length
const defaultStart = totalBars > defaultVisibleBars
  ? ((totalBars - defaultVisibleBars) / totalBars) * 100
  : 0
```

with:

```ts
import { computeDefaultStart } from '@/lib/chart-zoom'
// ...
const defaultStart = computeDefaultStart(categoryData.length)
```

Both `dataZoom` entries continue using `start: defaultStart, end: 100`. The existing indicator-update effect at the bottom of the file (which preserves the user's current zoom on re-renders) is unaffected — it reads the chart instance's current `dataZoom` start/end, not the option's default.

### Production default

`DEFAULT_VISIBLE_BARS = 50` (down from 500). The constant is the single source of truth.

### Unit tests

New file `packages/client/src/lib/chart-zoom.test.ts`:

| Case | Input | Expected |
|---|---|---|
| Empty dataset | `computeDefaultStart(0)` | `0` |
| Smaller than default | `computeDefaultStart(30)` | `0` |
| Equal to default | `computeDefaultStart(50)` | `0` |
| One bar more than default | `computeDefaultStart(51)` | `(1/51)*100` via `toBeCloseTo` |
| Much larger than default | `computeDefaultStart(1000)` | `95` (exact) |
| Custom `visible` override | `computeDefaultStart(1000, 100)` | `90` (exact) |

Assertions use concrete numbers (`toBe(0)`, `toBe(95)`, `toBe(90)`) rather than re-deriving the production formula. Only the float-boundary case uses `toBeCloseTo`. This is the assertion shape the PR #47 reviewer specifically called for.

### E2e test update

`packages/client/e2e/default-zoom.spec.ts` is kept (per Approach 2) but trimmed to a smoke check:

- Open a run, wait for the chart to render.
- Assert `dataZoom[0].end === 100`.
- Assert `dataZoom[0].start > 0` (some default window is applied, not full-range).

Removed: the visible-bars-count math (now covered by unit tests) and the tautological formula re-derivation. The 1000-bar e2e dataset still satisfies `start > 0` under the new 50-bar default, so the spec stays green without test-data changes.

## Risk + Mitigation

- **The 50-bar default may be too tight for some workflows.** Mitigation: it's a constant in one file (`chart-zoom.ts`) and the user can still drag the dataZoom slider out to the full range. If 50 turns out to be wrong, it's a one-line follow-up.
- **Vitest config drift from Vite config.** Mitigation: extending the same `defineConfig` keeps them in sync. If they diverge, type-check failures will surface immediately in `tsc --noEmit` (already in CI).
- **Indicator-update effect interaction.** The effect reads `chartRef.current.getOption().dataZoom[0].start`, so any change to the *default* `start` only affects first render. Verified by reading the effect at `CandlestickChart.tsx:328-347` during brainstorming.

## Out of Scope (Explicit)

- CI integration for unit tests (per user feedback: unit tests run locally only).
- Migrating any existing test to Vitest.
- Removing `default-zoom.spec.ts` (kept as smoke check).
- Test coverage tooling (`@vitest/coverage-v8`).

## Decisions Locked In During Brainstorming

| Decision | Choice | Why |
|---|---|---|
| Test runner | Vitest | Canonical for Vite + React |
| Install scope | Minimal (no jsdom / RTL) | Defer until first component test |
| Helper location | `src/lib/chart-zoom.ts` | Matches existing pure-helper home |
| Test file layout | Co-located (`foo.ts` + `foo.test.ts`) | Standard Vitest pattern; mirrors prod source |
| Default value | 50 | Per user request |
| E2e spec | Keep as smoke check (Approach 2) | User wants e2e gate preserved |
| CI | No unit-test step | Per user feedback: e2e is the PR gate |
