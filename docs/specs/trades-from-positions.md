# Spec — Trades from Positions + fix `compute_run_metrics` test/impl mismatch

**Trello:** https://trello.com/c/Ty1ZvebC
**Branch:** `fix/trades-from-positions`

## Goal

Two related fixes in `packages/server`:

1. **Trades from Positions** — `GET /api/runs/{id}/trades` returns one row per closed `Position`, so the trade `#` column counts 1..N across all round-trips. Today the endpoint collapses every round-trip into a single fabricated trade under NETTING OMS because the existing transform groups fills by `position_id` and Nautilus reuses one `position_id` across every round-trip.
2. **`compute_run_metrics` test fixture mismatch** — the 20 currently-failing tests in `tests/test_metrics.py` are fixed by aligning the test helper to the same data shape the production path uses (`list[PositionClosed]`). The impl is unchanged.

## Background and root cause

### Trades bug

- `packages/server/server/store/transforms.py:60` `fills_to_trades` groups fills by `position_id`, takes the first fill as entry and the last fill as exit.
- Under NautilusTrader's **NETTING OMS** (the default for CFDs, FX, futures-as-net), every round-trip on the same instrument reuses the same `position_id`. Nautilus does NOT mint a new `position_id` when net quantity returns to zero and re-opens.
- Result: regardless of how many round-trips occurred, the transform produces exactly one "trade" record from the first BUY to the last SELL with a fabricated PnL ignoring every intermediate cycle.
- Observed on:
  - `fbaf897e-db90-4c15-9445-97ee39c67408` (BBBStrategy, 238 closed positions, 476 fills) → 1 trade displayed.
  - `e4599dab-fd51-4758-9564-c2061bc2104e` (EMACross, 204 closed positions, 408 fills) → 1 trade displayed.
- `total_positions` and `total_fills` on `/api/runs/{id}` are correct — only `/trades` is broken.
- Secondary bug discovered in the existing transform: `direction` is computed by comparing the order-side string against `"BUY"`, but `str(OrderSide.BUY)` returns `"1"`. So `direction` was always `"Short"` in production.

### Definition of "trade"

NautilusTrader has no first-class "round-trip Trade" entity. The term is overloaded:

- `TradeTick` — market data, not relevant
- `OrderFilled.trade_id` — venue execution id (per fill)
- `Position` — the actual round-trip concept. Under NETTING OMS, a Position exists while net quantity ≠ 0; when net qty returns to 0, the Position is closed and recorded. Nautilus's own analytics (`PortfolioAnalyzer`, `generate_positions_report()`) use **closed Positions** as the trade unit.

We adopt this definition: **one closed `Position` = one trade**. Multiple round-trips that share a `position_id` (NETTING) are still distinct trades, because the catalog stores one `PositionClosed` row per round-trip.

### Metrics bug

- `packages/server/server/store/metrics.py:85` iterates `positions_closed` and reads attributes: `[float(p.realized_pnl) for p in positions_closed]`.
- Production passes `list[PositionClosed]` from `read_backtest()` — works.
- `tests/test_metrics.py::_make_positions_table` builds a `pyarrow.Table` — iterating it yields `ChunkedArray` columns, which don't have a `realized_pnl` attribute. All 20 tests using the helper fail with the same `AttributeError`.

## Design

### 1. New `positions_to_trades` transform

Add to `packages/server/server/store/transforms.py`:

```python
from nautilus_trader.model.enums import OrderSide

def positions_to_trades(positions_closed: list) -> list[dict]:
    """Convert closed Positions into trade rows for the UI table.

    Each closed Position is one trade. Under NETTING OMS multiple closed
    Positions can share a position_id; each is still its own trade.
    """
    sorted_positions = sorted(positions_closed, key=lambda p: p.ts_opened)
    return [
        {
            "relative_id": idx + 1,
            "position_id": str(p.position_id),
            "instrument_id": str(p.instrument_id),
            "direction": "Long" if p.entry == OrderSide.BUY else "Short",
            "entry_datetime": _ns_to_iso(p.ts_opened),
            "entry_price": float(p.avg_px_open),
            "exit_datetime": _ns_to_iso(p.ts_closed),
            "exit_price": float(p.avg_px_close),
            "quantity": float(p.peak_qty),
            "pnl": round(float(p.realized_pnl), 2),
            "currency": str(p.currency),
        }
        for idx, p in enumerate(sorted_positions)
    ]
```

Delete `fills_to_trades` — dead after this change.

### 2. Wire the trades route to the new transform

In `packages/server/server/routes/fills.py`, change `get_trades` to source from `get_positions_closed(data)` (already exists in `catalog_reader.py`) and call `positions_to_trades`. The handler stays a thin pure function — only its data source and transform reference change.

### 3. Metrics test fixture

In `packages/server/tests/test_metrics.py`:

- Rename `_make_positions_table` → `_make_positions_list`. Returns `list[SimpleNamespace]` (from `types.SimpleNamespace`) with attributes `realized_pnl`, `realized_return`, `ts_opened`, `ts_closed`, `duration_ns`, `position_id`.
- Update all 20 currently-failing tests to call the new helper. `compute_run_metrics` and `metrics.py` are not modified.
- Rename `test_empty_table_returns_all_none` → `test_empty_list_returns_all_none` (passes `[]`).

The impl (`metrics.py`) is unchanged because the production path already passes objects with the right attributes.

### 4. New trades unit tests

In `packages/server/tests/test_transforms.py` (extend if exists, create otherwise), all using `SimpleNamespace` fixtures duck-typing `PositionClosed`:

- `test_positions_to_trades_one_per_closed_position` — 3 positions sharing one `position_id` (NETTING-OMS regression) produce 3 trades with the right relative_ids.
- `test_positions_to_trades_unique_position_ids` — 3 positions with unique `position_id`s (HEDGING-OMS) produce 3 trades.
- `test_positions_to_trades_sorted_by_ts_opened` — unsorted input is sorted by `ts_opened` ascending in the output.
- `test_positions_to_trades_direction` — entry=BUY → "Long"; entry=SELL → "Short". Catches the latent direction bug in the deleted transform.
- `test_positions_to_trades_empty` — `[]` → `[]`.

### 5. Live-run validation

After implementation, hit:

- `GET /api/runs/fbaf897e-db90-4c15-9445-97ee39c67408/trades` → expect 238 rows; spot-check 3 random rows against the matching `/positions` row for `pnl`, `ts_opened`, `avg_px_open`.
- `GET /api/runs/e4599dab-fd51-4758-9564-c2061bc2104e/trades` → expect 204 rows; same spot-check.

## Files touched

| File | Change |
|---|---|
| `packages/server/server/store/transforms.py` | Add `positions_to_trades`; delete `fills_to_trades` |
| `packages/server/server/routes/fills.py` | `get_trades` switches data source to `get_positions_closed`, calls `positions_to_trades` |
| `packages/server/tests/test_transforms.py` | Add 5 unit tests for `positions_to_trades` |
| `packages/server/tests/test_metrics.py` | Replace `_make_positions_table` helper; update 20 tests + 1 empty-case test |

No client-side changes: `packages/client/src/components/trades/TradeTable.tsx` continues to render with no edits required because the JSON shape is preserved.

## Out of scope

- Per-trade fills drilldown (could be added later via `position_id` + `ts_opened` range).
- Showing currently-open positions as in-flight trades.
- Lot-level (FIFO/LIFO) accounting within a single round-trip — Nautilus does not expose this, and weighted `avg_px_open` / `avg_px_close` is what its own reports use.
- Migrating `compute_run_metrics` to `pa.Table` — separate Refactoring card if ever wanted.

## Acceptance criteria

Tracked on the Trello card; mirrored here:

- [ ] `GET /api/runs/{id}/trades` returns `len(trades) == total_positions`.
- [ ] Each trade exposes the same JSON keys `TradeTable.tsx` already consumes.
- [ ] Run `fbaf897e-…` returns 238 trades; run `e4599dab-…` returns 204 trades.
- [ ] Trade `#` column counts 1..N (ordered by `ts_opened` ascending).
- [ ] Unit test: multiple closed positions sharing one `position_id` → N trades (NETTING-OMS).
- [ ] Unit test: HEDGING-OMS (unique `position_id` per round-trip) → one trade per position.
- [ ] Open positions at backtest end are excluded (source = `get_positions_closed`).
- [ ] `TradeTable.tsx` unchanged.
- [ ] All 20 currently-failing `tests/test_metrics.py` tests pass.
- [ ] Full `packages/server` test suite green on `fix/trades-from-positions`.
