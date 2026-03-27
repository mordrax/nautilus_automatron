# Dashboard Instrument Data Catalog View — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the runs page to "dashboard" and add a second table showing available instrument data (instrument, bar count, date range, timeframe) from the backtest catalog.

**Architecture:** New `GET /api/catalog` endpoint scans bar directories across all backtest runs, reads feather file schema metadata and ts_init column to extract instrument ID, bar count, and date range. Frontend adds a `CatalogTable` component alongside the existing `RunList` on a renamed `DashboardPage`.

**Tech Stack:** FastAPI, PyArrow, React, Effect-TS, Tabulator, React Query, wouter, shadcn/ui

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `packages/server/server/store/reader.py` | Add `list_catalog_entries()` — scans all runs for unique bar types, reads feather metadata |
| Modify | `packages/server/server/store/transforms.py` | Add `catalog_entry_to_dict()` and `_parse_timeframe()` — builds API-ready catalog dicts |
| Create | `packages/server/server/routes/catalog.py` | `GET /api/catalog` endpoint |
| Modify | `packages/server/server/main.py` | Register catalog router |
| Modify | `packages/client/src/types/api.ts` | Add `CatalogEntry` type |
| Modify | `packages/client/src/lib/api.ts` | Add `getCatalog()` |
| Create | `packages/client/src/hooks/use-catalog.ts` | `useCatalog()` React Query hook |
| Create | `packages/client/src/lib/catalog-columns.ts` | Tabulator column definitions for catalog table |
| Create | `packages/client/src/components/catalog/CatalogTable.tsx` | Tabulator table component |
| Rename | `packages/client/src/pages/RunsPage.tsx` → `DashboardPage.tsx` | Compose RunList + CatalogTable |
| Modify | `packages/client/src/App.tsx` | Update import to DashboardPage |
| Modify | `packages/client/src/components/layout/AppLayout.tsx` | Nav label "Runs" → "Dashboard" |
| Modify | `packages/client/e2e/runs-page.spec.ts` | Update assertions for rename + add catalog tests |

---

### Task 1: Backend reader — `list_catalog_entries()`

**Files:**
- Modify: `packages/server/server/store/reader.py`

- [ ] **Step 1: Add `list_catalog_entries` function to reader.py**

Add `import pyarrow.compute as pc` at the top alongside `import pyarrow as pa`.

Add after `read_bars_raw()`:

```python
def list_catalog_entries(store_path: Path) -> list[dict]:
    """Scan all runs to build a deduplicated catalog of available instrument data.

    For each unique bar_type directory across all runs, reads all feather files
    to extract instrument ID, total bar count, and date range.
    Returns one entry per unique bar_type.
    """
    seen: dict[str, dict] = {}

    for run_id in list_run_ids(store_path):
        bar_dir = store_path / "backtest" / run_id / "bar"
        if not bar_dir.exists():
            continue

        for bar_type_dir in sorted(bar_dir.iterdir()):
            if not bar_type_dir.is_dir():
                continue

            bar_type_name = bar_type_dir.name
            if bar_type_name in seen:
                continue

            total_bars = 0
            ts_min: int | None = None
            ts_max: int | None = None
            instrument_id = ""
            bar_type_str = ""

            for feather_file in sorted(bar_type_dir.glob("*.feather")):
                table = _read_ipc_stream(feather_file)
                if table is None:
                    continue

                total_bars += len(table)

                if not instrument_id:
                    metadata = table.schema.metadata or {}
                    instrument_id = metadata.get(b"instrument_id", b"").decode()
                    bar_type_str = metadata.get(b"bar_type", b"").decode()

                ts_init = table.column("ts_init")
                file_min = pc.min(ts_init).as_py()
                file_max = pc.max(ts_init).as_py()

                if ts_min is None or file_min < ts_min:
                    ts_min = file_min
                if ts_max is None or file_max > ts_max:
                    ts_max = file_max

            if total_bars > 0:
                seen[bar_type_name] = {
                    "instrument_id": instrument_id,
                    "bar_type": bar_type_str or bar_type_name,
                    "bar_count": total_bars,
                    "ts_min": ts_min,
                    "ts_max": ts_max,
                }

    return list(seen.values())
```

- [ ] **Step 2: Commit**

```bash
git add packages/server/server/store/reader.py
git commit -m "feat: add list_catalog_entries reader function"
```

---

### Task 2: Backend transforms — `catalog_entry_to_dict()`

**Files:**
- Modify: `packages/server/server/store/transforms.py`

- [ ] **Step 1: Add `_parse_timeframe` and `catalog_entry_to_dict` to transforms.py**

Add at the end of the file:

```python
def _parse_timeframe(bar_type: str, instrument_id: str) -> str:
    """Extract timeframe from bar_type by removing the instrument prefix.

    Example: 'AUD/USD.SIM-100-TICK-MID-INTERNAL' with instrument 'AUD/USD.SIM'
    returns '100-TICK-MID-INTERNAL'.
    """
    prefix = instrument_id + "-"
    if bar_type.startswith(prefix):
        return bar_type[len(prefix):]
    return bar_type


def catalog_entry_to_dict(entry: dict) -> dict:
    """Convert a raw catalog entry from the reader into an API-ready dict."""
    return {
        "instrument": entry["instrument_id"],
        "bar_count": entry["bar_count"],
        "start_date": _ns_to_iso(entry["ts_min"]),
        "end_date": _ns_to_iso(entry["ts_max"]),
        "timeframe": _parse_timeframe(entry["bar_type"], entry["instrument_id"]),
    }
```

- [ ] **Step 2: Commit**

```bash
git add packages/server/server/store/transforms.py
git commit -m "feat: add catalog entry transform and timeframe parser"
```

---

### Task 3: Backend route — `GET /api/catalog`

**Files:**
- Create: `packages/server/server/routes/catalog.py`
- Modify: `packages/server/server/main.py`

- [ ] **Step 1: Create `catalog.py` route**

Create `packages/server/server/routes/catalog.py`:

```python
"""Routes for listing available instrument data in the catalog."""

from pathlib import Path

from fastapi import APIRouter, Depends

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


@router.get("/catalog")
def list_catalog(store_path: Path = Depends(_store_path)):
    entries = reader.list_catalog_entries(store_path)
    return [transforms.catalog_entry_to_dict(e) for e in entries]
```

- [ ] **Step 2: Register router in main.py**

In `packages/server/server/main.py`, add import:

```python
from server.routes.catalog import router as catalog_router
```

Add after the existing `app.include_router(...)` lines:

```python
app.include_router(catalog_router, prefix="/api")
```

- [ ] **Step 3: Smoke test the endpoint**

```bash
cd packages/server
.venv/bin/python -c "
from server.store.reader import list_catalog_entries
from server.store.transforms import catalog_entry_to_dict
from pathlib import Path
entries = list_catalog_entries(Path('/Users/mordrax/code/nautilus_trader/backtest_catalog'))
for e in entries:
    print(catalog_entry_to_dict(e))
"
```

Expected: prints one dict with `instrument`, `bar_count`, `start_date`, `end_date`, `timeframe` keys.

- [ ] **Step 4: Commit**

```bash
git add packages/server/server/routes/catalog.py packages/server/server/main.py
git commit -m "feat: add GET /api/catalog endpoint"
```

---

### Task 4: Frontend types and API

**Files:**
- Modify: `packages/client/src/types/api.ts`
- Modify: `packages/client/src/lib/api.ts`

- [ ] **Step 1: Add `CatalogEntry` type to `types/api.ts`**

Add at the end of the file:

```typescript
export type CatalogEntry = {
  readonly instrument: string
  readonly bar_count: number
  readonly start_date: string
  readonly end_date: string
  readonly timeframe: string
}
```

- [ ] **Step 2: Add `getCatalog` to `api.ts`**

Add `CatalogEntry` to the import line:

```typescript
import type { RunsResponse, RunDetail, Trade, OhlcData, EquityPoint, Position, IndicatorMeta, IndicatorResult, CatalogEntry } from '@/types/api'
```

Add the function after `getBarTypes`:

```typescript
export const getCatalog = () =>
  fetchJson<readonly CatalogEntry[]>('/api/catalog')
```

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/types/api.ts packages/client/src/lib/api.ts
git commit -m "feat: add CatalogEntry type and getCatalog API function"
```

---

### Task 5: Frontend hook — `useCatalog`

**Files:**
- Create: `packages/client/src/hooks/use-catalog.ts`

- [ ] **Step 1: Create `use-catalog.ts`**

```typescript
import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useCatalog = () =>
  useQuery({
    queryKey: ['catalog'],
    queryFn: () => api.runEffect(api.getCatalog()),
  })
```

- [ ] **Step 2: Commit**

```bash
git add packages/client/src/hooks/use-catalog.ts
git commit -m "feat: add useCatalog React Query hook"
```

---

### Task 6: Frontend column definitions — `catalog-columns.ts`

**Files:**
- Create: `packages/client/src/lib/catalog-columns.ts`

- [ ] **Step 1: Create `catalog-columns.ts`**

Reuses `stringHeaderFilter` and `numericHeaderFilter` already exported from `run-columns.ts`.

```typescript
import type { ColumnDefinition } from 'tabulator-tables'
import { stringHeaderFilter, numericHeaderFilter } from '@/lib/run-columns'

export const createCatalogColumns = (): ColumnDefinition[] => [
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
]
```

- [ ] **Step 2: Commit**

```bash
git add packages/client/src/lib/catalog-columns.ts
git commit -m "feat: add catalog table column definitions"
```

---

### Task 7: Frontend component — `CatalogTable`

**Files:**
- Create: `packages/client/src/components/catalog/CatalogTable.tsx`

- [ ] **Step 1: Create `CatalogTable.tsx`**

Mirrors the existing `RunList.tsx` Tabulator pattern.

```typescript
import { useRef, useEffect } from 'react'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator.min.css'
import type { CatalogEntry } from '@/types/api'
import { createCatalogColumns } from '@/lib/catalog-columns'

type CatalogTableProps = {
  readonly entries: readonly CatalogEntry[]
}

export const CatalogTable = ({ entries }: CatalogTableProps) => {
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)

  useEffect(() => {
    if (!tableRef.current) return

    const table = new Tabulator(tableRef.current, {
      data: entries as CatalogEntry[],
      columns: createCatalogColumns(),
      layout: 'fitColumns',
      height: '300px',
      initialSort: [{ column: 'instrument', dir: 'asc' }],
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [entries])

  return <div ref={tableRef} />
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/client/src/components/catalog/CatalogTable.tsx
git commit -m "feat: add CatalogTable component"
```

---

### Task 8: Rename RunsPage → DashboardPage and compose both tables

**Files:**
- Rename: `packages/client/src/pages/RunsPage.tsx` → `packages/client/src/pages/DashboardPage.tsx`
- Modify: `packages/client/src/App.tsx`
- Modify: `packages/client/src/components/layout/AppLayout.tsx`

- [ ] **Step 1: Delete `RunsPage.tsx` and create `DashboardPage.tsx`**

```typescript
import { RunList } from '@/components/runs/RunList'
import { CatalogTable } from '@/components/catalog/CatalogTable'
import { useRuns } from '@/hooks/use-runs'
import { useCatalog } from '@/hooks/use-catalog'

export const DashboardPage = () => {
  const { data: runsData, isLoading: runsLoading, error: runsError } = useRuns()
  const { data: catalogData, isLoading: catalogLoading, error: catalogError } = useCatalog()

  return (
    <div className="px-2 py-4 space-y-8">
      <section>
        <h2 className="text-xl font-semibold mb-4 px-2">Instrument Data Catalog</h2>
        {catalogLoading && <div className="text-muted-foreground p-4">Loading catalog...</div>}
        {catalogError && <div className="text-destructive p-4">Error loading catalog</div>}
        {catalogData && catalogData.length > 0 && <CatalogTable entries={catalogData} />}
        {catalogData && catalogData.length === 0 && (
          <div className="text-muted-foreground p-4">No instrument data in catalog</div>
        )}
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4 px-2">
          Backtest Runs {runsData ? `(${runsData.total})` : ''}
        </h2>
        {runsLoading && <div className="text-muted-foreground p-4">Loading runs...</div>}
        {runsError && <div className="text-destructive p-4">Error loading runs</div>}
        {runsData && <RunList runs={runsData.runs} />}
      </section>
    </div>
  )
}
```

- [ ] **Step 2: Update `App.tsx`**

Replace `import { RunsPage } from '@/pages/RunsPage'` with `import { DashboardPage } from '@/pages/DashboardPage'`.

Replace `<Route path="/" component={RunsPage} />` with `<Route path="/" component={DashboardPage} />`.

- [ ] **Step 3: Update `AppLayout.tsx` nav label**

Replace `{ href: '/', label: 'Runs' }` with `{ href: '/', label: 'Dashboard' }`.

- [ ] **Step 4: Commit**

```bash
git rm packages/client/src/pages/RunsPage.tsx
git add packages/client/src/pages/DashboardPage.tsx packages/client/src/App.tsx packages/client/src/components/layout/AppLayout.tsx
git commit -m "feat: rename runs page to dashboard, add catalog table section"
```

---

### Task 9: Update Playwright tests

**Files:**
- Modify: `packages/client/e2e/runs-page.spec.ts`

- [ ] **Step 1: Update "Runs" nav link assertion**

Replace:
```typescript
await expect(page.getByRole('link', { name: 'Runs' })).toBeVisible()
```
With:
```typescript
await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible()
```

- [ ] **Step 2: Add catalog table test**

Add at the end of the `describe` block:

```typescript
test('instrument data catalog table is visible', async ({ page }) => {
  await expect(page.getByText('Instrument Data Catalog')).toBeVisible()

  const catalogSection = page.locator('section', { has: page.getByText('Instrument Data Catalog') })
  const tabulator = catalogSection.locator('.tabulator')
  await expect(tabulator).toBeVisible()

  for (const col of ['Instrument', 'Bar Count', 'Start Date', 'End Date', 'Timeframe']) {
    await expect(tabulator.locator('.tabulator-col-title', { hasText: col }).first()).toBeVisible()
  }

  await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()
  await expect(tabulator.locator('.tabulator-cell', { hasText: 'AUD/USD.SIM' }).first()).toBeVisible()
})
```

- [ ] **Step 3: Commit**

```bash
git add packages/client/e2e/runs-page.spec.ts
git commit -m "test: update e2e tests for dashboard rename and catalog table"
```

---

### Task 10: Run all Playwright tests headless

- [ ] **Step 1: Run tests**

```bash
cd packages/client
TEST_VITE_PORT=5174 TEST_API_PORT=8001 npx playwright test --project=headless
```

Expected: All tests pass.

- [ ] **Step 2: Fix any failures, commit fixes**

---

## Verification

1. **Backend:** `curl http://localhost:8000/api/catalog` returns JSON array with entries like `{"instrument": "AUD/USD.SIM", "bar_count": 1000, "start_date": "...", "end_date": "...", "timeframe": "100-TICK-MID-INTERNAL"}`
2. **Frontend:** Navigate to `http://localhost:5173/` — see "Dashboard" nav link, "Instrument Data Catalog" table with data, and "Backtest Runs" table below
3. **E2E:** All Playwright tests pass headless
4. **Browser validation:** Use Chrome MCP to verify the page renders both tables with real data
