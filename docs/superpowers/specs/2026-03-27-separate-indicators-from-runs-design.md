# Separate Indicators from Runs

## Overview

Decouple indicator computation from backtest run IDs. Indicators are pure functions that operate on bar data identified by bar type (instrument + timeframe). They should never need a run ID.

**Related Trello card:** [#105 - Separate indicators from runs](https://trello.com/c/KcUbSO2S)
**Enables:** Card #106 (Instrument chart page) — needs indicators on catalog bars with no run ID.

## Key Insight

Backtest runs duplicate catalog bars. The `StreamingFeatherWriter` subscribes to `"*"` on the message bus and writes all input bars to `backtest/{run_id}/bar/`. These are exact copies of the `data/bar/` catalog data. Computing indicators from run bars vs catalog bars produces identical results.

Therefore: indicators should always read from catalog bars (`data/bar/` via `catalog.bars()`). The run ID is irrelevant.

## Design

### Backend

**New endpoint:** `GET /api/bars/{bar_type}/indicators?ids=...`

Reads bars from the catalog's `data/bar/` directory via `catalog.bars(bar_types=[bar_type])` and computes indicators. No run ID involved.

```python
@router.get("/bars/{bar_type}/indicators")
def get_indicators_for_bar_type(
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    bars = catalog.bars(bar_types=[bar_type])
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")

    indicator_ids = [i.strip() for i in ids.split(",") if i.strip()]
    results = []
    for indicator_id in indicator_ids:
        results.append(compute_indicator(indicator_id, bars))
    return results
```

**Old endpoint:** `GET /api/runs/{run_id}/bars/{bar_type}/indicators` — comment out with a note to use the new endpoint. Do not delete (preserves git history for reference).

**No changes to `store/indicators.py`** — `compute_indicator(indicator_id, bars)` already accepts `list[Bar]` and is pure.

### Frontend

**API function change:**

```typescript
// Before:
getIndicatorResult(runId: string, barType: string, ids: readonly string[])
  → /api/runs/${runId}/bars/${barType}/indicators?ids=...

// After:
getIndicatorResult(barType: string, ids: readonly string[])
  → /api/bars/${barType}/indicators?ids=...
```

**Hook change:**

```typescript
// Before:
useIndicators(runId: string, barType: string)

// After:
useIndicators(barType: string)
```

The React Query key changes from `['indicator-data', runId, barType, sortedIds]` to `['indicator-data', barType, sortedIds]`.

**RunDetailPage:** Already has `barType` available. Just drops `runId` from the `useIndicators` call.

**InstrumentPage (card #106):** Can use `useIndicators(barType)` directly — no adapter needed.

## What Changes

| File | Change |
|------|--------|
| `packages/server/server/routes/indicators.py` | Comment out old endpoint, add new bar-type-based endpoint |
| `packages/client/src/lib/api.ts` | Update `getIndicatorResult` to drop `runId` parameter |
| `packages/client/src/hooks/use-indicators.ts` | Update `useIndicators` to drop `runId` parameter |
| `packages/client/src/pages/RunDetailPage.tsx` | Update `useIndicators` call to drop `runId` |

## What Doesn't Change

- `store/indicators.py` — computation is already pure
- `store/indicators.py` registry, configs, compute function — untouched
- `CandlestickChart.tsx` — receives indicators as props, source-agnostic
- `IndicatorToggles` component — source-agnostic
