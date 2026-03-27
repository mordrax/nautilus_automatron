# Separate Indicators from Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple indicator computation from backtest run IDs — indicators are pure functions on bar type, computed from catalog bars.

**Architecture:** New backend endpoint reads bars from `data/bar/` via `catalog.bars()` instead of `backtest/{run_id}/`. Frontend drops `runId` from the indicator API call and hook. Old run-based endpoint commented out.

**Tech Stack:** Python/FastAPI (backend), TypeScript/React/Effect-TS (frontend), NautilusTrader ParquetDataCatalog

**Spec:** `docs/superpowers/specs/2026-03-27-separate-indicators-from-runs-design.md`

---

### Task 1: Add new bar-type-based indicator endpoint

**Files:**
- Modify: `packages/server/server/routes/indicators.py`

- [ ] **Step 1: Comment out the old run-based endpoint and add the new bar-type endpoint**

Replace the entire file with:

```python
"""Routes for technical indicator data."""

from fastapi import APIRouter, Depends, HTTPException, Query

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.routes.dependencies import _catalog
from server.store.indicators import (
    IndicatorMeta,
    IndicatorResult,
    compute_indicator,
    list_available_indicators,
)

router = APIRouter()


@router.get("/indicators")
def get_available_indicators() -> list[IndicatorMeta]:
    return list_available_indicators()


@router.get("/bars/{bar_type:path}/indicators")
def get_indicators_for_bar_type(
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    """Compute indicators from catalog bars by bar type.

    Bar type identifies instrument + timeframe (e.g. XAUUSD.IBCFD-5-MINUTE-MID-EXTERNAL).
    Indicators are pure functions on bars — they don't need a run ID.
    """
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    indicator_ids = [i.strip() for i in ids.split(",") if i.strip()]
    results = []
    for indicator_id in indicator_ids:
        try:
            results.append(compute_indicator(indicator_id, bars))
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown indicator: {indicator_id}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error computing {indicator_id}: {str(e)}",
            )

    return results


# --- Deprecated endpoint ---
# The run-based indicator endpoint has been removed.
# Indicators are pure functions on bar type and don't need a run ID.
# Use GET /api/bars/{bar_type}/indicators?ids=... instead.
#
# @router.get("/runs/{run_id}/bars/{bar_type:path}/indicators")
# def get_indicators(run_id, bar_type, ids, catalog):
#     ...
```

- [ ] **Step 2: Verify the module loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.routes.indicators import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/server/server/routes/indicators.py
git commit -m "feat: add bar-type-based indicator endpoint, deprecate run-based endpoint"
```

---

### Task 2: Update frontend API function

**Files:**
- Modify: `packages/client/src/lib/api.ts`

- [ ] **Step 1: Update `getIndicatorResult` to drop `runId` parameter**

Find and replace the `getIndicatorResult` function (lines 95-98):

```typescript
// Before:
export const getIndicatorResult = (runId: string, barType: string, ids: readonly string[]) =>
  fetchJson<readonly IndicatorResult[]>(
    `/api/runs/${runId}/bars/${encodeURIComponent(barType)}/indicators?ids=${ids.join(',')}`
  )
```

Replace with:

```typescript
export const getIndicatorResult = (barType: string, ids: readonly string[]) =>
  fetchJson<readonly IndicatorResult[]>(
    `/api/bars/${encodeURIComponent(barType)}/indicators?ids=${ids.join(',')}`
  )
```

- [ ] **Step 2: Commit**

```bash
git add packages/client/src/lib/api.ts
git commit -m "refactor: update getIndicatorResult to use bar-type endpoint (no runId)"
```

---

### Task 3: Update `useIndicators` hook

**Files:**
- Modify: `packages/client/src/hooks/use-indicators.ts`

- [ ] **Step 1: Remove `runId` parameter from hook**

Replace the entire file with:

```typescript
import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as api from '@/lib/api'

export const useIndicators = (barType: string) => {
  const [enabledIds, setEnabledIds] = useState<ReadonlySet<string>>(new Set())

  const { data: available } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => api.runEffect(api.getIndicators()),
  })

  const sortedIds = [...enabledIds].sort()

  const { data } = useQuery({
    queryKey: ['indicator-data', barType, sortedIds],
    queryFn: () => api.runEffect(api.getIndicatorResult(barType, sortedIds)),
    enabled: !!barType && sortedIds.length > 0,
  })

  const toggle = useCallback((id: string) => {
    setEnabledIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  return { available: available ?? [], data: data ?? [], enabledIds, toggle }
}
```

Changes:
- Signature: `useIndicators(runId: string, barType: string)` → `useIndicators(barType: string)`
- Query key: removed `runId`
- Query function: `getIndicatorResult(runId, barType, sortedIds)` → `getIndicatorResult(barType, sortedIds)`
- Enabled condition: removed `!!runId`

- [ ] **Step 2: Commit**

```bash
git add packages/client/src/hooks/use-indicators.ts
git commit -m "refactor: useIndicators takes barType only, no runId"
```

---

### Task 4: Update `RunDetailPage` caller

**Files:**
- Modify: `packages/client/src/pages/RunDetailPage.tsx`

- [ ] **Step 1: Update the `useIndicators` call**

Find line 98:

```typescript
const { available, data: indicatorData, enabledIds, toggle } = useIndicators(runId, barType)
```

Replace with:

```typescript
const { available, data: indicatorData, enabledIds, toggle } = useIndicators(barType)
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add packages/client/src/pages/RunDetailPage.tsx
git commit -m "refactor: update RunDetailPage to use barType-only useIndicators"
```

---

### Task 5: Verification

- [ ] **Step 1: Verify backend loads and new endpoint is registered**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.main import app; routes = [r.path for r in app.routes]; print([r for r in routes if 'indicator' in r])"`

Expected: Should include `/api/bars/{bar_type}/indicators` and NOT include `/api/runs/{run_id}/bars/{bar_type}/indicators`.

- [ ] **Step 2: Test the new endpoint with curl**

Start server: `NAUTILUS_STORE_PATH=/Users/mordrax/code/nautilus_automatron/backtest_catalog .venv/bin/python -m uvicorn server.main:app --port 8003`

Run: `curl -s "http://localhost:8003/api/bars/XAUUSD.IBCFD-5-MINUTE-MID-EXTERNAL/indicators?ids=RSI_14" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} indicators, first has {len(d[0][\"datetime\"])} points')"`

Expected: `1 indicators, first has 4673 points` (or similar bar count)

- [ ] **Step 3: Verify old endpoint returns 404**

Run: `curl -s "http://localhost:8003/api/runs/some-run-id/bars/XAUUSD.IBCFD-5-MINUTE-MID-EXTERNAL/indicators?ids=RSI_14" -w "%{http_code}"`

Expected: `404` or `{"detail":"Not Found"}`

- [ ] **Step 4: TypeScript compiles cleanly**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/client && bunx tsc --noEmit`

Expected: No errors.
