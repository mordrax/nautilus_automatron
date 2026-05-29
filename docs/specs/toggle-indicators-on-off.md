# Spec: Toggle indicators on/off on the backtest chart

- Trello card: [#135](https://trello.com/c/IPyxrubs/135-toggle-indicators-on-off-on-the-backtest-chart)
- Branch: `feat/toggle-indicators-on-off`

## Goal

On the backtest run detail view, each active indicator chip can be toggled
enabled/disabled by clicking it. An indicator draws on the chart only when it is
**both** present in the indicator list **and** enabled. A disabled indicator
stays in the list, rendered dimmed, but is hidden from the chart. This is a
frontend-only change — no server, API, or backend changes.

## Background

Indicators on `RunDetailPage` are managed by the `useIndicators` hook
(`src/hooks/use-indicators.ts`):

- `instances: IndicatorInstance[]` — the list of added indicators, persisted
  server-side via viewer-state.
- `data: IndicatorResult[]` — computed indicator series fetched from the server,
  keyed on `instances`.
- `colors` — per-indicator colors, persisted **client-side** in `localStorage`
  (`indicator-colors-v2`).

`RunDetailPage` passes `data` to `<CandlestickChart>` and `instances` to
`<IndicatorInstanceSelector>`, which renders one `<IndicatorChip>` per instance.

The new "enabled" flag is the same kind of concern as `colors`: a viewer-side,
frontend-only preference. It is stored in `localStorage` parallel to colors —
**not** in server viewer-state.

## Design

### Enabled state in `useIndicators`

Add an `enabled` concern parallel to the existing `colors`:

- New `localStorage` key `indicator-enabled-v1`, holding `Record<string, boolean>`
  keyed by indicator instance id.
- `loadEnabled()` / `saveEnabled()` helpers, mirroring `loadColors()` /
  `saveColors()` (try/catch, ignore storage errors).
- New state `enabled` seeded from `loadEnabled()`.
- `isEnabled(id): boolean` — returns `enabled[id] ?? true`. **Absence of an id
  means enabled** — so newly added indicators are enabled by default with no
  extra write.
- `toggleEnabled(id): void` — flips `enabled[id] ?? true`, writes the new map
  through to `localStorage` (same write-through pattern as `setColor`).
- The hook returns `isEnabled` and `toggleEnabled`.

No pruning of removed indicators' entries — consistent with how `colors`
already behaves; instance ids are UUIDs, so stale entries are inert and tiny.

Toggling does **not** trigger a refetch. All instances continue to be fetched
regardless of enabled state; `enabled` is purely a render-time filter, so
toggling is instant.

### Chart filtering in `RunDetailPage`

`RunDetailPage` filters the indicator results before passing them to
`<CandlestickChart>`:

```tsx
indicators={indicatorData?.filter((r) => isEnabled(r.id))}
```

`<IndicatorInstanceSelector>` still receives the full `instances` list, plus
`isEnabled` and `toggleEnabled`.

Because `IndicatorResult.id` equals `IndicatorInstance.id`, the filter cleanly
removes a disabled indicator's series. `CandlestickChart` already rebuilds
overlay series and panels (and recomputes its height) from its `indicators`
prop using `replaceMerge`, so disabling a panel indicator removes its panel and
shrinks the chart, and disabling an overlay/spike indicator removes its
lines/markers — **no `CandlestickChart` change required**.

### Chip interaction in `IndicatorChip`

`IndicatorChip` gains two props: `enabled: boolean` and `onToggle: () => void`.

- The chip root `<div>` gets `onClick={onToggle}`, `cursor-pointer`, a `title`,
  and `data-enabled={enabled}` (for e2e assertions). It deliberately does **not**
  carry `role="button"`/`aria-pressed`: a `role="button"` derives its accessible
  name from its contents, which would absorb the inner swatch button's label and
  collide with role-based queries (and is invalid nested-interactive ARIA). The
  chip stays a plain clickable container; its inner controls remain proper buttons.
- When `enabled` is false, the root div is dimmed (`opacity-50`).
- The color picker's `PopoverContent` also calls `e.stopPropagation()` on click.
  React routes synthetic events through the React tree, not the DOM, so a click
  inside the portaled popover would otherwise bubble to the chip's `onClick` and
  toggle the indicator. (The edit popover lives in `IndicatorSelector` as a
  sibling of the chip, so it is unaffected.)
- The three existing controls — color-swatch `PopoverTrigger`, edit pencil,
  remove X — call `e.stopPropagation()` in their `onClick` so they do not also
  toggle the chip. They remain fully functional while the chip is dimmed.

The chip is wrapped by the edit `Popover`'s controlled `PopoverTrigger`. That
popover opens only via the explicit edit handler (`open={isEditing}`;
`onOpenChange` ignores opening), so a body click does not open it — it only runs
`onToggle`.

### Prop threading

`IndicatorInstanceSelector` gains `isEnabled: (id: string) => boolean` and
`onToggle: (id: string) => void`, passing `enabled={isEnabled(instance.id)}` and
`onToggle={() => onToggle(instance.id)}` to each `IndicatorChip`.

## Files changed

| File | Change |
|------|--------|
| `src/hooks/use-indicators.ts` | Add `enabled` state, `loadEnabled`/`saveEnabled`, `isEnabled`, `toggleEnabled`; export the two new functions. |
| `src/pages/RunDetailPage.tsx` | Destructure `isEnabled`/`toggleEnabled`; filter `indicatorData` by `isEnabled`; pass props to the selector. |
| `src/pages/InstrumentPage.tsx` | Second consumer of `IndicatorInstanceSelector`; same wiring (type-forced once the selector props are required). Toggle works here too. |
| `src/components/chart/indicator-selector/IndicatorSelector.tsx` | Add `isEnabled`/`onToggle` props; thread to `IndicatorChip`. |
| `src/components/chart/indicator-selector/IndicatorChip.tsx` | Add `enabled`/`onToggle` props; click-to-toggle on root div; dim when disabled; `stopPropagation` on the three controls. |
| `src/hooks/use-indicators.test.ts` | Unit tests for `isEnabled`/`toggleEnabled` + localStorage. |
| `e2e/indicator-toggle.spec.ts` (new) | Playwright e2e for the toggle flow. |

## Testing

**Unit (`use-indicators.test.ts`):**

- `isEnabled` returns `true` for an unknown id (default).
- `toggleEnabled` flips an indicator to disabled, then back to enabled.
- The disabled state is written to `localStorage` under `indicator-enabled-v1`.
- A hook mounted with an existing `indicator-enabled-v1` entry reads the
  disabled state.

**e2e (`e2e/indicator-toggle.spec.ts`, headless):**

- Navigate to a run detail page, add an indicator → chip listed, series on the
  chart.
- Click the chip → indicator hidden from the chart, chip still listed and dimmed
  (`data-enabled="false"`).
- Click again → indicator reappears on the chart.
- Reload the page → the disabled indicator is still disabled (localStorage
  persistence).

Tests wait for async data, never timeouts. e2e runs with `--project=headless`.

## Out of scope

- Any server/API/backend change; persisting enabled state to server
  viewer-state.
- Bulk enable/disable, grouping, or reordering indicators.
- Changes to add/remove/edit indicator behavior, or to `CandlestickChart`
  internals.
