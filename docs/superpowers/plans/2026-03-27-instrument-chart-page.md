# Instrument Chart Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated page to view raw instrument bar data as a candlestick chart, reachable by clicking an instrument row in the dashboard catalog table.

**Architecture:** New backend endpoint reads raw bars from `data/bar/` via `ParquetDataCatalog.bars()`. Frontend gets a new `/instruments/:barType` route with `InstrumentPage` component. The existing `CandlestickChart` is modified to make trades optional so it can be reused without trade overlays. The catalog API is updated to include the full `bar_type` string so the frontend can construct URLs.

**Tech Stack:** FastAPI, ParquetDataCatalog (NautilusTrader), React, wouter, eCharts, Effect-TS, TanStack React Query

**Spec:** `docs/superpowers/specs/2026-03-27-instrument-chart-page-design.md`
**Trello:** Card #106

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `packages/server/server/store/transforms.py` | Add `bar_type` field to catalog entry dict |
| Modify | `packages/server/server/store/reader.py` | Scan `data/bar/` via ParquetDataCatalog instead of backtest feather files |
| Create | `packages/server/server/routes/catalog_bars.py` | New endpoint for raw catalog bar data |
| Modify | `packages/server/server/main.py` | Register new router |
| Modify | `packages/client/src/types/api.ts` | Add `bar_type` field to `CatalogEntry` |
| Modify | `packages/client/src/lib/api.ts` | Add `getCatalogBars()` function |
| Create | `packages/client/src/hooks/use-catalog-bars.ts` | `useCatalogBars(barType)` hook |
| Modify | `packages/client/src/components/chart/CandlestickChart.tsx` | Make trades optional |
| Modify | `packages/client/src/components/catalog/CatalogTable.tsx` | Add row click handler |
| Create | `packages/client/src/pages/InstrumentPage.tsx` | New instrument chart page |
| Modify | `packages/client/src/App.tsx` | Add route for instrument page |

---

### Task 1: Backend — Add `bar_type` field to catalog entry response

The frontend needs the full `bar_type` string (e.g., `XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL`) to construct the URL for the bars endpoint. Currently `catalog_entry_to_dict` only returns a parsed `timeframe`.

**Files:**
- Modify: `packages/server/server/store/transforms.py:220-228`

- [ ] **Step 1: Add `bar_type` to `catalog_entry_to_dict`**

In `packages/server/server/store/transforms.py`, update the function:

```python
def catalog_entry_to_dict(entry: dict) -> dict:
    """Convert a raw catalog entry from the reader into an API-ready dict."""
    return {
        "instrument": entry["instrument_id"],
        "bar_type": entry["bar_type"],
        "bar_count": entry["bar_count"],
        "start_date": _ns_to_iso(entry["ts_min"]),
        "end_date": _ns_to_iso(entry["ts_max"]),
        "timeframe": _parse_timeframe(entry["bar_type"], entry["instrument_id"]),
    }
```

- [ ] **Step 2: Verify server starts**

Run: `cd packages/server && python -m uvicorn server.main:app --port 8000`
Expected: Server starts without errors. Hit `http://localhost:8000/api/catalog` and confirm each entry now has a `bar_type` field.

- [ ] **Step 3: Commit**

```bash
git add packages/server/server/store/transforms.py
git commit -m "feat: add bar_type field to catalog entry response"
```

---

### Task 2: Backend — Update `list_catalog_entries` to scan `data/bar/`

Currently `list_catalog_entries()` scans `backtest/{run_id}/bar/` directories with manual PyArrow reads. Update it to scan `data/bar/` using `ParquetDataCatalog.bars()` since the instrument data lives in `data/`, not in backtest runs.

**Files:**
- Modify: `packages/server/server/store/reader.py:49-127`
- Modify: `packages/server/server/routes/catalog.py`

- [ ] **Step 1: Rewrite `list_catalog_entries` to use ParquetDataCatalog**

Replace the `list_catalog_entries` function in `packages/server/server/store/reader.py`:

```python
def list_catalog_entries(
    store_path: Path,
    catalog: ParquetDataCatalog | None = None,
) -> list[dict]:
    """Scan the data catalog to build a list of available instrument bar data.

    Reads bar type directories from data/bar/ and extracts instrument ID,
    total bar count, and date range for each.
    Returns one entry per unique bar_type.
    """
    if catalog is None:
        return []

    data_bar_dir = store_path / "data" / "bar"
    if not data_bar_dir.exists():
        return []

    entries: list[dict] = []

    for bar_type_dir in sorted(data_bar_dir.iterdir()):
        if not bar_type_dir.is_dir():
            continue

        bar_type_name = bar_type_dir.name
        bars = catalog.bars(bar_types=[bar_type_name])

        if not bars:
            continue

        instrument_id = str(bars[0].bar_type.instrument_id)
        ts_min = min(b.ts_event for b in bars)
        ts_max = max(b.ts_event for b in bars)

        entries.append({
            "instrument_id": instrument_id,
            "bar_type": bar_type_name,
            "bar_count": len(bars),
            "ts_min": ts_min,
            "ts_max": ts_max,
        })

    return entries
```

Also add the import at the top of `reader.py` if not already present — `ParquetDataCatalog` is already imported via `TYPE_CHECKING`.

- [ ] **Step 2: Simplify the catalog route**

The route in `packages/server/server/routes/catalog.py` already passes `catalog` — no changes needed. But `_store_path` dependency is still needed. Verify the route still works:

```python
@router.get("/catalog")
def list_catalog(
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    entries = reader.list_catalog_entries(store_path, catalog=catalog)
    return [transforms.catalog_entry_to_dict(e) for e in entries]
```

- [ ] **Step 3: Remove unused imports**

In `packages/server/server/store/reader.py`, remove the `pyarrow` imports that are no longer needed:

```python
import pyarrow as pa
import pyarrow.compute as pc
```

Also remove the `_read_ipc_stream` function if nothing else uses it. Check first:

Run: `cd packages/server && grep -r "_read_ipc_stream" --include="*.py" .`

If only used in `reader.py`, delete it.

- [ ] **Step 4: Verify server starts and catalog returns data**

Run: `cd packages/server && python -m uvicorn server.main:app --port 8000`
Hit: `http://localhost:8000/api/catalog`
Expected: Returns entries from `data/bar/` with `XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL` and `XAUUSD.IBCFD-5-MINUTE-MID-EXTERNAL`.

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/reader.py
git commit -m "feat: scan data/bar/ for catalog entries instead of backtest runs"
```

---

### Task 3: Backend — New endpoint for raw catalog bar data

Create `GET /api/catalog/bars/{bar_type}` that reads raw bars from `data/bar/` and returns `OhlcData`.

**Files:**
- Create: `packages/server/server/routes/catalog_bars.py`
- Modify: `packages/server/server/main.py`

- [ ] **Step 1: Create the catalog bars route**

Create `packages/server/server/routes/catalog_bars.py`:

```python
"""Routes for raw instrument bar data from the data catalog."""

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store import transforms

router = APIRouter()


@router.get("/catalog/bars/{bar_type:path}")
def get_catalog_bars(bar_type: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    """Return OHLC data for a raw catalog bar type."""
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")
    return transforms.bars_to_ohlc(bars)
```

Note: `{bar_type:path}` allows slashes in the bar type string (instrument IDs can contain `/` like `AUD/USD.SIM`).

- [ ] **Step 2: Register the router in main.py**

In `packages/server/server/main.py`, add the import and include the router. Add it **before** the existing `catalog_router` to avoid path conflicts:

```python
from server.routes.catalog_bars import router as catalog_bars_router
```

Add to the router registration section:

```python
app.include_router(catalog_bars_router, prefix="/api")
```

Place it after `catalog_router` — the `/catalog/bars/` prefix is more specific than `/catalog` so order doesn't matter here, but keeping it near `catalog_router` is logical.

- [ ] **Step 3: Verify the endpoint works**

Run: `cd packages/server && python -m uvicorn server.main:app --port 8000`
Hit: `http://localhost:8000/api/catalog/bars/XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL`
Expected: JSON response with `datetime`, `open`, `high`, `low`, `close`, `volume` arrays.

Also verify 404 for nonexistent bar types:
Hit: `http://localhost:8000/api/catalog/bars/FAKE-BAR-TYPE`
Expected: 404 with error message.

- [ ] **Step 4: Commit**

```bash
git add packages/server/server/routes/catalog_bars.py packages/server/server/main.py
git commit -m "feat: add GET /api/catalog/bars/{bar_type} endpoint for raw catalog data"
```

---

### Task 4: Frontend — Add `bar_type` to CatalogEntry type and API function

**Files:**
- Modify: `packages/client/src/types/api.ts:118-124`
- Modify: `packages/client/src/lib/api.ts`
- Create: `packages/client/src/hooks/use-catalog-bars.ts`

- [ ] **Step 1: Add `bar_type` to CatalogEntry type**

In `packages/client/src/types/api.ts`, update the `CatalogEntry` type:

```typescript
export type CatalogEntry = {
  readonly instrument: string
  readonly bar_type: string
  readonly bar_count: number
  readonly start_date: string
  readonly end_date: string
  readonly timeframe: string
}
```

- [ ] **Step 2: Add `getCatalogBars` API function**

In `packages/client/src/lib/api.ts`, add after the `getCatalog` function:

```typescript
export const getCatalogBars = (barType: string) =>
  fetchJson<OhlcData>(`/api/catalog/bars/${encodeURIComponent(barType)}`)
```

- [ ] **Step 3: Create `useCatalogBars` hook**

Create `packages/client/src/hooks/use-catalog-bars.ts`:

```typescript
import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useCatalogBars = (barType: string) =>
  useQuery({
    queryKey: ['catalog-bars', barType],
    queryFn: () => api.runEffect(api.getCatalogBars(barType)),
    enabled: !!barType,
  })
```

- [ ] **Step 4: Verify types compile**

Run: `cd packages/client && bunx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/client/src/types/api.ts packages/client/src/lib/api.ts packages/client/src/hooks/use-catalog-bars.ts
git commit -m "feat: add catalog bars API function and hook"
```

---

### Task 5: Frontend — Make CandlestickChart trades optional

**Files:**
- Modify: `packages/client/src/components/chart/CandlestickChart.tsx`

- [ ] **Step 1: Update the props type**

In `packages/client/src/components/chart/CandlestickChart.tsx`, change the props type (lines 7-14):

```typescript
type CandlestickChartProps = {
  readonly ohlc: OhlcData
  readonly trades?: readonly Trade[]
  readonly indicators?: readonly IndicatorResult[]
  readonly currentTradeIndex?: number
  readonly onSelectTrade?: (index: number) => void
  readonly onChartReady?: (chart: echarts.ECharts) => void
}
```

- [ ] **Step 2: Update the component to guard trade usage**

Update the component function (starting at line 268). The key changes:

1. Default `trades` to `[]` in the destructuring
2. Guard the click handler — only bind when `onSelectTrade` is provided
3. Guard the `TradeTooltip` — only render when trades and `currentTradeIndex` are provided

```typescript
export const CandlestickChart = ({
  ohlc,
  trades = [],
  indicators = [],
  currentTradeIndex,
  onSelectTrade,
  onChartReady,
}: CandlestickChartProps) => {
  const chartDivRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const selectTradeRef = useRef(onSelectTrade)

  useEffect(() => {
    selectTradeRef.current = onSelectTrade
  })

  const panelCount = indicators.filter(i => i.display === 'panel').length
  const chartHeight = 600 + panelCount * 150

  // Init chart and bind click on ohlc/trades change (destroys + recreates)
  useEffect(() => {
    if (!chartDivRef.current) return

    const chart = echarts.init(chartDivRef.current)
    chartRef.current = chart
    onChartReady?.(chart)

    const option = buildOption(ohlc, trades, indicators)
    chart.setOption(option)

    // Expose chart for e2e testing
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).__ECHARTS_INSTANCE__ = chart

    if (selectTradeRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      chart.on('click', { componentType: 'markLine' }, (params: any) => {
        const trade = params.data?.trade
        if (!trade) return
        const idx = trades.findIndex((t) => t.relative_id === trade.relative_id)
        if (idx >= 0) selectTradeRef.current?.(idx)
      })
    }

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
      chartRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- indicators handled by the update effect below; selectTradeRef is a stable ref
  }, [ohlc, trades, onChartReady])

  // Update indicators without destroying chart (preserves zoom/state)
  useEffect(() => {
    if (!chartRef.current) return
    const fullOption = buildOption(ohlc, trades, indicators)
    const { dataZoom: _, ...optionWithoutZoom } = fullOption // eslint-disable-line @typescript-eslint/no-unused-vars
    chartRef.current.setOption(optionWithoutZoom, { replaceMerge: ['series', 'grid', 'xAxis', 'yAxis'] })
    chartRef.current.resize()
  }, [ohlc, trades, indicators])

  const showTooltip = trades.length > 0 && currentTradeIndex !== undefined
  const currentTrade = showTooltip ? trades[currentTradeIndex] : undefined

  return (
    <div data-testid="chart-container" style={{ position: 'relative', width: '100%', height: `${chartHeight}px` }}>
      <div ref={chartDivRef} style={{ width: '100%', height: '100%' }} />
      {showTooltip && <TradeTooltip trade={currentTrade} />}
    </div>
  )
}
```

- [ ] **Step 3: Verify the run detail page still works**

Run: `cd packages/client && bun run dev`
Navigate to a run detail page. Confirm:
- Candlestick chart renders with trade mark lines
- Clicking mark lines still selects trades
- Trade tooltip still appears
- Indicators still work

- [ ] **Step 4: Verify types compile**

Run: `cd packages/client && bunx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/client/src/components/chart/CandlestickChart.tsx
git commit -m "refactor: make CandlestickChart trades optional for reuse"
```

---

### Task 6: Frontend — Add CatalogTable row click handler

**Files:**
- Modify: `packages/client/src/components/catalog/CatalogTable.tsx`
- Modify: `packages/client/src/lib/catalog-columns.ts`

- [ ] **Step 1: Add `onViewInstrument` prop to CatalogTable**

Update `packages/client/src/components/catalog/CatalogTable.tsx`:

```typescript
import { useRef, useEffect, useMemo } from 'react'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { CatalogEntry } from '@/types/api'
import { createCatalogColumns } from '@/lib/catalog-columns'
import { useColumnVisibility } from '@/hooks/use-column-visibility'
import { ColumnVisibilityPopover } from '@/components/table/ColumnVisibilityPopover'

type CatalogTableProps = {
  readonly entries: readonly CatalogEntry[]
  readonly title: string
  readonly onViewInstrument: (barType: string) => void
}

export const CatalogTable = ({ entries, title, onViewInstrument }: CatalogTableProps) => {
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)
  const { hiddenColumns, toggleColumn, applyVisibility } = useColumnVisibility('catalog-table')

  const columns = useMemo(() => createCatalogColumns(onViewInstrument), [onViewInstrument])

  const toggleableColumns = useMemo(
    () =>
      columns
        .filter((col) => col.field)
        .map((col) => ({ field: col.field!, title: col.title ?? col.field! })),
    [columns]
  )

  useEffect(() => {
    if (!tableRef.current) return

    const table = new Tabulator(tableRef.current, {
      data: entries as CatalogEntry[],
      columns,
      layout: 'fitColumns',
      height: '300px',
      initialSort: [{ column: 'instrument', dir: 'asc' }],
    })

    table.on('tableBuilt', () => {
      applyVisibility(table)
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [entries, columns, applyVisibility])

  return (
    <div>
      <div className="flex items-center justify-between mb-4 px-2">
        <h2 className="text-xl font-semibold">{title}</h2>
        <ColumnVisibilityPopover
          columns={toggleableColumns}
          hiddenColumns={hiddenColumns}
          onToggle={(field) => toggleColumn(field, tabulatorRef.current)}
        />
      </div>
      <div ref={tableRef} />
    </div>
  )
}
```

- [ ] **Step 2: Add View button column to catalog columns**

Update `packages/client/src/lib/catalog-columns.ts`. Check how the run list does it first — look at `packages/client/src/lib/run-columns.ts` for the "View" button pattern. Add a similar column:

```typescript
import type { ColumnDefinition, CellComponent } from 'tabulator-tables'
import { stringHeaderFilter, numericHeaderFilter } from '@/lib/run-columns'

export const createCatalogColumns = (onViewInstrument: (barType: string) => void): ColumnDefinition[] => [
  {
    title: 'Instrument',
    field: 'instrument',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: 'Bar Count',
    field: 'bar_count',
    sorter: 'number',
    hozAlign: 'right',
    formatter: (cell) => {
      const value = cell.getValue() as number
      return value.toLocaleString()
    },
    ...numericHeaderFilter,
  },
  {
    title: 'Start Date',
    field: 'start_date',
    sorter: 'string',
    formatter: (cell) => {
      const value = cell.getValue() as string
      if (!value) return '—'
      return new Date(value).toLocaleDateString()
    },
    ...stringHeaderFilter,
  },
  {
    title: 'End Date',
    field: 'end_date',
    sorter: 'string',
    formatter: (cell) => {
      const value = cell.getValue() as string
      if (!value) return '—'
      return new Date(value).toLocaleDateString()
    },
    ...stringHeaderFilter,
  },
  {
    title: 'Timeframe',
    field: 'timeframe',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: '',
    formatter: () => '<button class="text-blue-500 hover:underline text-sm">View</button>',
    width: 80,
    hozAlign: 'center',
    headerSort: false,
    cellClick: (_e: UIEvent, cell: CellComponent) => {
      const data = cell.getRow().getData() as { bar_type: string }
      onViewInstrument(data.bar_type)
    },
  },
]
```

- [ ] **Step 3: Update DashboardPage to pass the callback**

In `packages/client/src/pages/DashboardPage.tsx`, update the `CatalogTable` usage:

```typescript
{catalogData && catalogData.length > 0 && (
  <CatalogTable
    entries={catalogData}
    title="Instrument Data Catalog"
    onViewInstrument={(barType) => setLocation(`/instruments/${encodeURIComponent(barType)}`)}
  />
)}
```

- [ ] **Step 4: Verify types compile**

Run: `cd packages/client && bunx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/client/src/components/catalog/CatalogTable.tsx packages/client/src/lib/catalog-columns.ts packages/client/src/pages/DashboardPage.tsx
git commit -m "feat: add View button to catalog table for instrument navigation"
```

---

### Task 7: Frontend — Create InstrumentPage and route

**Files:**
- Create: `packages/client/src/pages/InstrumentPage.tsx`
- Modify: `packages/client/src/App.tsx`

- [ ] **Step 1: Create InstrumentPage component**

Create `packages/client/src/pages/InstrumentPage.tsx`:

```typescript
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import { useCatalogBars } from '@/hooks/use-catalog-bars'

type InstrumentPageProps = {
  readonly barType: string
}

export const InstrumentPage = ({ barType }: InstrumentPageProps) => {
  const decodedBarType = decodeURIComponent(barType)
  const { data: ohlc, isLoading, error } = useCatalogBars(decodedBarType)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold">{decodedBarType}</h2>
        {ohlc && <Badge variant="secondary">{ohlc.datetime.length.toLocaleString()} bars</Badge>}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading && (
            <div className="h-[600px] flex items-center justify-center text-muted-foreground">
              Loading chart data...
            </div>
          )}
          {error && (
            <div className="h-[600px] flex items-center justify-center text-destructive">
              Error loading bar data
            </div>
          )}
          {ohlc && <CandlestickChart ohlc={ohlc} />}
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Add route in App.tsx**

In `packages/client/src/App.tsx`, add the import and route:

```typescript
import { InstrumentPage } from '@/pages/InstrumentPage'
```

Add the route inside the `<Switch>`, after the `/create` route:

```typescript
<Route path="/instruments/:barType">
  {(params) => <InstrumentPage barType={params.barType} />}
</Route>
```

The full `<Switch>` should be:

```typescript
<Switch>
  <Route path="/" component={DashboardPage} />
  <Route path="/runs/:runId">
    {(params) => <RunDetailPage runId={params.runId} />}
  </Route>
  <Route path="/create" component={CreateBacktestPage} />
  <Route path="/instruments/:barType">
    {(params) => <InstrumentPage barType={params.barType} />}
  </Route>
</Switch>
```

- [ ] **Step 3: Verify types compile**

Run: `cd packages/client && bunx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 4: End-to-end verification**

Run both server and client:
- Server: `cd packages/server && python -m uvicorn server.main:app --port 8000`
- Client: `cd packages/client && bun run dev`

Test the full flow:
1. Dashboard loads and shows catalog entries with "View" buttons
2. Click "View" on an instrument → navigates to `/instruments/XAUUSD.IBCFD-1-MINUTE-MID-EXTERNAL`
3. Candlestick chart renders with OHLC data
4. No trade mark lines, no trade tooltip
5. DataZoom slider works
6. Go back to dashboard, navigate to a run detail page → trades still work normally

- [ ] **Step 5: Commit**

```bash
git add packages/client/src/pages/InstrumentPage.tsx packages/client/src/App.tsx
git commit -m "feat: add instrument chart page with route"
```
