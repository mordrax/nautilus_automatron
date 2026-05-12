# Chip Data Source Tooltip — Design

**Trello card:** [#127](https://trello.com/c/FsId0yRP/127-data-source-hover-info-on-symbol-timeframe-chips)
**Date:** 2026-05-11
**Branch:** `feat/chip-data-source-tooltip`

## Problem

On the run detail page, each symbol/timeframe is rendered as a flat `<Badge>` chip
(e.g. `XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL`). When debugging a run there's no way
to see which parquet directory backed that chip, where it lives on disk, how
many bars are in it, what date range it covers, or which venue produced it.

The catalog endpoint already exposes most of these facts — but the UI doesn't
surface them, and the endpoint is missing the on-disk path and a venue token.

## Goal

Hovering a chip on `RunDetailPage` shows a tooltip with the data source's
provenance. Clicking a chip pins the tooltip open so the path can be selected
and copied. Tooltip data comes from the existing `/api/catalog` endpoint, with
three small additions to its response.

## Non-Goals

- Listing individual parquet files inside a bar_type directory — directory + file count is enough.
- Mapping venue codes to friendly names (e.g. `IBCFD` → "Interactive Brokers CFD"). Pass through whatever token the symbol stream provides.
- A separate metadata file (`provenance.json` or similar) recording provider info. The bar_type string is the only source of provenance for this card.
- Tooltips on non-bar chip types (none exist on `RunDetailPage` today).

## Architecture

```
RunDetailPage
  ├─ useRunDetail(runId)       ── existing
  ├─ useCatalog()              ── existing hook, not currently called here
  │
  └─ runDetail.bar_types.map(bt =>
        <BarTypeChip barType={bt} entry={catalogMap[bt]} />)
                                            │
                                            ▼
                          Radix Tooltip wrapping <Badge>
                                            │
                                            ▼
                          <CatalogTooltipContent entry={...} />
```

`catalogMap` is `Object.fromEntries(catalog.map(e => [e.bar_type, e]))`, built
on render. Catalog response is cached by TanStack Query — one fetch per session.

## Server Changes

### `/api/catalog` response — three new fields

Current per-entry shape (`packages/server/server/store/transforms.py:220-229`):

```python
{
  "instrument": str,
  "bar_type": str,
  "bar_count": int,
  "start_date": str,   # ISO 8601
  "end_date": str,
  "timeframe": str,
}
```

Add:

```python
  "venue": str | None,    # parsed from bar_type, e.g. "IBCFD" or null
  "path": str,            # absolute path to the bar_type directory
  "file_count": int,      # number of .parquet files in that directory
```

### Where the new fields come from

- **`venue`** — derived from `bar_type` only. Format is `{symbol}.{venue}-{aggregation}-...`,
  so the venue is `bar_type.split(".", 1)[1].split("-", 1)[0]` when a `.` is
  present; otherwise `None`. No mapping table — pass the raw token through.
- **`path`** — `catalog_reader` already iterates `<store>/data/bar/<bar_type>/`
  to enumerate entries. Expose that directory's absolute path on the entry.
- **`file_count`** — `len(list(bar_type_dir.glob("*.parquet")))`. Computed
  during enumeration; no extra disk pass.

### File touchpoints

- `packages/server/server/store/catalog_reader.py` — extend `list_catalog_entries()` to capture the bar_type directory path and parquet file count, and pass both into the entry it returns.
- `packages/server/server/store/transforms.py` — `catalog_entry_to_dict()` adds `venue`, `path`, `file_count`.
- `packages/server/tests/` — add `test_catalog_route_provenance_fields` covering the three new fields, including the `venue=null` case.

## Client Changes

### New components

#### `src/components/BarTypeChip.tsx`

Props:

```ts
type Props = {
  barType: string
  entry: CatalogEntry | undefined
}
```

Behavior:

- Wraps `<Badge variant="outline">{barType}</Badge>` in `<Tooltip>` / `<TooltipTrigger asChild>`.
- Local `pinned` state (`useState(false)`). `onClick` toggles `pinned`.
- Passes `open` to `Tooltip` as `pinned || hovered` via the controlled `open` prop. When `pinned` is true, Radix's own hover-close is suppressed.
- Renders `<CatalogTooltipContent entry={entry} barType={barType} />` inside `<TooltipContent>`.

#### `src/components/CatalogTooltipContent.tsx`

Props:

```ts
type Props = {
  barType: string
  entry: CatalogEntry | undefined
}
```

Layout (compact 2-column grid, `text-xs`):

```
Symbol      XAUUSD.IBCFD
Venue       IBCFD
Timeframe   1m
Range       2026-02-25  →  2026-03-27
Bars        12,345
Path        /.../backtest_catalog/data/bar/XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL  [copy] (3 files)
```

- Path row uses a monospace span; copy icon button copies the path string via `navigator.clipboard.writeText`.
- If `entry` is `undefined`: render "Not in catalog" + the bar_type string only.

### Modified files

- `src/pages/RunDetailPage.tsx:76-78` — replace bare `<Badge>` with `<BarTypeChip>`; add `useCatalog()` call at top; build `catalogMap`.
- `src/lib/api.ts` — extend `CatalogEntry` type with `venue: string | null`, `path: string`, `file_count: number`.
- `src/hooks/use-catalog.ts` — no change (already returns the array).

## Testing

### Server unit test (`packages/server/tests/test_catalog_route.py`)

- Asserts the response includes `venue`, `path`, `file_count` for at least one entry.
- Asserts `venue` parses correctly from a bar_type like `XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL` → `"IBCFD"`.
- Asserts `venue` is `null` for a synthetic bar_type with no `.`.

### Playwright (`packages/client/tests/run-detail-tooltip.spec.ts`)

- Loads a run page that has at least one bar_type chip.
- Hovers the first chip; asserts tooltip contains:
  - the real on-disk path (substring match on `backtest_catalog/data/bar/`),
  - the venue token,
  - a numeric bar count (not `Loading…` or `—`),
  - a date range with `→`.
- Clicks the chip; moves the mouse away; asserts tooltip remains open (pin works).
- Clicks the chip again; asserts tooltip closes.

Run headless first, then in UI mode for human review per the orchestration skill.

## Error & Edge Cases

| Case | Behavior |
|---|---|
| `bar_type` from run isn't in `/api/catalog` (race or stale) | Tooltip renders "Not in catalog" + raw bar_type string. No crash. |
| `path` directory missing on disk | `file_count` returns 0; path string still rendered as-is. |
| `bar_type` has no `.` (synthetic / malformed) | `venue` is `null`, Venue row omitted from tooltip. |
| Catalog hasn't loaded yet | Chip renders without tooltip metadata until query resolves; on resolve, tooltip populates. |
| `clipboard.writeText` rejected (insecure context) | Copy button is a no-op; tooltip otherwise unaffected. |

## Out of Scope (future cards)

- A web-based parquet viewer for inspecting bar contents in-browser.
- A persistent provenance metadata file capturing provider beyond the venue token.
- Tooltip on non-bar data types (ticks, quotes) — none rendered on `RunDetailPage` today.
