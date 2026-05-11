# Indicator Selector: Active Chips + cmdk Add Menu

**Status:** Approved (pending user sign-off on this rewrite)
**Date:** 2026-05-11
**Trello:** https://trello.com/c/Td6DDDNY/126-indicator-selector-active-chips-cmdk-add-menu

## Problem

`packages/client/src/components/chart/IndicatorToggles.tsx` renders every available indicator as a checkbox row, grouped flat by `Overlays` / `Panels`. As the catalog grows (more overlays, panels, upcoming key-level indicators, additional parameterizations of existing types like `EMA(30)` / `ZigZag(2%)`, future preset packs) the list runs off-screen and offers no way to search.

The control must scale to:
- ~30+ indicators in the near term, 100+ longer term
- New display categories (e.g. `Key Levels`, `Volume Profile`)
- Multiple instances of the same indicator type with different parameters (already true today: `EMA(20)` + `EMA(50)`, `ZigZag(5%)` + `ZigZag(3%)` + `ZigZag(0.1%)`)
- Future per-chip parameter editing (out of scope for this PR — see below)

## Type vs. instance model

Today's `INDICATOR_REGISTRY` (`packages/server/server/store/indicators.py`) stores **instances**, not types:

- `EMA_20`, `EMA_50` — two instances of the EMA type
- `ZigZag_5pct`, `ZigZag_3pct`, `ZigZag_01pct` — three instances of the ZigZag type
- `BollingerBands_20` — one instance of BB

The backend already returns these via `GET /api/indicators` as a flat `IndicatorMeta[]`. **Each registered ID is an instance** identified by its `label` (e.g. `EMA(20)`). The frontend treats instances as the unit of selection:

- The Add menu lists instances (flat, grouped by `display`).
- Each chip represents one enabled instance.
- A given instance can only be enabled once (it's already on the chart).
- Multiple instances of the same type coexist naturally because they have distinct IDs.

When parameters become editable in the future, the gear popover on a chip will swap one instance ID for another (or call a new backend endpoint that accepts ad-hoc params) — the UI surface doesn't need to land in this PR.

## Solution

A **two-tier control** in the chart toolbar (same slot `IndicatorToggles` occupies today):

1. **Active chips row** — one chip per enabled instance: color swatch + label + `✕`. Screen footprint is proportional to *active* count, not total available.
2. **`+ Add indicator ▾` button** — opens a [`cmdk`](https://cmdk.paco.me/)-powered command palette (shadcn's `Command`) with fuzzy search and grouped sections.

```
┌─ Chart toolbar ───────────────────────────────────────┐
│ Active: [■ EMA(20) ✕] [■ EMA(50) ✕] [■ RSI(14) ✕]     │
│         [+ Add indicator ▾]                           │
└───────────────────────────────────────────────────────┘
                    ▼ click
              ┌─────────────────────┐
              │ 🔍 search…          │
              │ ─ Overlays ───────  │
              │   EMA(20)           │  ← hidden once enabled
              │   EMA(50)           │
              │   SMA(20)           │
              │   BB(20,2)          │
              │   ZigZag(5%)        │
              │   ZigZag(3%)        │
              │ ─ Panels ─────────  │
              │   RSI(14)           │  ← hidden once enabled
              │   MACD(12,26)       │
              │   ATR(14)           │
              │   Stoch(14,3)       │
              └─────────────────────┘
```

### Decisions locked in

| Decision | Choice |
|---|---|
| Add-menu grouping | By `display` category only (`Overlays`, `Panels`). Future categories (`Key Levels`, etc.) slot in by adding a new `display` variant. |
| Already-enabled in menu | **Hidden.** The specific enabled instance disappears from the menu; other instances of the same type remain visible. |
| Empty state | Just the `+ Add indicator` button. No hint text. |
| Toolbar position | Same place `IndicatorToggles` renders today — drop-in replacement. |
| Gear / knobs | **Deferred entirely** — no gear icon in this PR. Chip = swatch + label + close. The gear lands when backend supports ad-hoc params. |

### Chip anatomy

| Element | Behavior |
|---|---|
| Color swatch | Click → existing color picker popover (preserved from current implementation). |
| Label | Instance `label` from `IndicatorMeta` (e.g. `EMA(20)`, `ZigZag(5%)`). |
| `✕` close | Click → disable the instance (equivalent to current `onToggle`). |

### Add-menu (cmdk) behavior

- Search input auto-focuses on open; fuzzy match against `label`.
- Sections in display order: `Overlays`, then `Panels`. Future categories append.
- Already-enabled instances are filtered out of the listing entirely.
- `Enter` on the highlighted row enables that instance and closes the menu.
- `Esc` closes the menu without changes.
- Arrow keys navigate within and across sections.

## Architecture

### Component split

Replace the single `IndicatorToggles` component with three focused components:

```
IndicatorSelector              (orchestrator)
├── ActiveIndicatorChip        (one per enabled instance)
│   └── ColorSwatchPopover     (reuses current color picker logic)
└── AddIndicatorMenu           (cmdk Command popover)
```

**Why three components, not one:** each has a single purpose, each is independently testable, and the chip is reusable if we add a sidebar variant later.

### File layout

```
packages/client/src/components/chart/
├── IndicatorToggles.tsx              (DELETE — replaced)
└── indicator-selector/
    ├── IndicatorSelector.tsx          (orchestrator)
    ├── ActiveIndicatorChip.tsx
    └── AddIndicatorMenu.tsx
```

### Props contract (preserved)

`IndicatorSelector` accepts the same props as today's `IndicatorToggles`:

```ts
type IndicatorSelectorProps = {
  readonly indicators: readonly IndicatorMeta[]
  readonly enabledIds: ReadonlySet<string>
  readonly onToggle: (id: string) => void
  readonly getColor: (id: string) => string
  readonly onColorChange: (id: string, color: string) => void
}
```

The existing `useIndicators` hook and parent pages (`InstrumentPage`, `RunDetailPage`) **do not change**. Only the import path and component name change at the call sites.

### Grouping logic

```ts
const GROUP_ORDER: readonly IndicatorMeta['display'][] = ['overlay', 'panel']
const GROUP_LABELS: Record<IndicatorMeta['display'], string> = {
  overlay: 'Overlays',
  panel: 'Panels',
}
```

When new `display` variants are added (e.g. `"key-level"`), they slot in by extending these maps — no structural changes needed.

## Dependencies

**No new packages.** shadcn's `Command` (cmdk) and `Popover` (Radix) are already in the project. If `Command` is not yet generated in this project, add it via the standard shadcn CLI — it's a generated component, not a runtime dep.

## Testing

### Playwright e2e (`packages/client/e2e/`)

A new spec `indicator-selector.spec.ts` covering:

1. **Enable from menu:** open add-menu, search `EMA`, click `EMA(20)`, assert chip renders and chart series appears.
2. **Disable via chip:** click `✕` on `EMA(20)` chip, assert chip removed and chart series removed.
3. **Search filter:** type `rsi`, assert only `RSI(14)` appears in menu.
4. **Color change:** click chip swatch, pick a color, assert chart series uses new color.
5. **Keyboard nav:** open menu, arrow down + Enter, assert instance enabled.
6. **Already-enabled hidden:** enable `EMA(20)`, reopen menu, assert `EMA(20)` no longer listed but `EMA(50)` still is.
7. **Multiple instances of same type:** enable `EMA(20)` and `EMA(50)`, assert both chips render and both chart series appear.

Existing `indicators.spec.ts` and `indicator-colors.spec.ts` will need their selectors updated since they target the checkbox markup.

### Unit tests

None required — components are thin wrappers over shadcn primitives. Behavior covered by e2e.

## Accessibility

- Add-menu uses cmdk which provides ARIA roles (`combobox`, `listbox`, `option`).
- Chips:
  - Close button: `aria-label="Disable {label}"`.
  - Color swatch: existing `aria-label="Change color for {label}"` preserved.
- Keyboard: Tab cycles through chips and the Add button; Enter/Space activates the focused control; Esc closes any open popover.

## Out of scope (future)

- **Parameter knobs.** Gear icon, knob popover, and ad-hoc parameterization land later when the backend supports it.
- **Key Levels group.** Slots in by adding the `"key-level"` display variant to `IndicatorMeta` and extending `GROUP_LABELS` — no selector changes.
- **Presets / saved packs.** "Save preset" button can land later under the chip row.
- **Drag-to-reorder chips.** Order follows the `enabledIds` insertion order; reordering is a future concern.

## Acceptance criteria

- [ ] Active chips render for each enabled instance (color swatch, label, close).
- [ ] Clicking `✕` on a chip disables the instance.
- [ ] `+ Add indicator` button opens a searchable popover grouped by `Overlays` / `Panels`.
- [ ] Search filters instances as the user types.
- [ ] Selecting an instance from the popover enables it and adds a chip.
- [ ] Already-enabled instances do not appear in the add menu; other instances of the same type still do.
- [ ] Multiple instances of the same type (e.g. `EMA(20)` + `EMA(50)`) can coexist as separate chips.
- [ ] Color picker still reachable from the chip swatch.
- [ ] Keyboard navigation works in the cmdk popover (arrows + enter, esc closes).
- [ ] Empty state renders only the `+ Add indicator` button (no hint text).
- [ ] No regressions to chart rendering or indicator overlay/panel behavior.
- [ ] `IndicatorToggles.tsx` is deleted; call sites in `InstrumentPage` and `RunDetailPage` import `IndicatorSelector` instead.
- [ ] Playwright e2e covers all scenarios listed above.

## Amendment 2026-05-11: Key Levels unification

The `IndicatorSelector` component was extended to absorb key-level detector selection, eliminating the separate `KeyLevelsPanel` checkbox list. The Add menu now has a third group — "Key Levels" — after Overlays and Panels; selected detectors render as chips in the same row as indicator chips, using the server-supplied `DetectorMeta.color` as the swatch background. Unlike indicator chips, key-level chip swatches are non-interactive (plain `<span>`, no color-picker popover) because detector colors are backend-defined. Both parent pages (`RunDetailPage` and `InstrumentPage`) pass detector props to `IndicatorSelector` and the `KeyLevelsPanel` component has been deleted; the `useDetectors` and `useKeyLevels` hooks remain unchanged and still drive chart rendering.
