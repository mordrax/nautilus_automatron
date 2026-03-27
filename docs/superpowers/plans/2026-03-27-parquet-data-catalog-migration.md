# ParquetDataCatalog Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace custom `reader.py` file-reading with NautilusTrader's `ParquetDataCatalog` for accessing backtest results, keeping all API responses identical.

**Architecture:** Bottom-up refactor: create new catalog access layer → update transforms/metrics to accept Nautilus objects → prune reader.py → rewire all routes → verify via type checking and existing e2e tests.

**Tech Stack:** Python 3.14, FastAPI, NautilusTrader (ParquetDataCatalog, Cython event/data objects), PyArrow (retained only for `list_catalog_entries`)

**Spec:** `docs/superpowers/specs/2026-03-27-parquet-data-catalog-migration-design.md`

---

### Task 1: Create `catalog_reader.py`

**Files:**
- Create: `packages/server/server/store/catalog_reader.py`

- [ ] **Step 1: Create the catalog reader module**

```python
"""Functions for reading backtest data via NautilusTrader's ParquetDataCatalog.

Provides typed filter functions over read_backtest() results, which returns
a mixed list of all data types from a backtest run.
"""

from nautilus_trader.model.data import Bar
from nautilus_trader.model.events.account import AccountState
from nautilus_trader.model.events.order import OrderFilled
from nautilus_trader.model.events.position import PositionClosed, PositionOpened
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def read_backtest_data(catalog: ParquetDataCatalog, run_id: str) -> list:
    """Read all data from a backtest run. Returns a mixed list of Nautilus objects."""
    return catalog.read_backtest(run_id)


def get_fills(data: list) -> list[OrderFilled]:
    """Filter backtest data to only OrderFilled events."""
    return [d for d in data if isinstance(d, OrderFilled)]


def get_positions_closed(data: list) -> list[PositionClosed]:
    """Filter backtest data to only PositionClosed events."""
    return [d for d in data if isinstance(d, PositionClosed)]


def get_positions_opened(data: list) -> list[PositionOpened]:
    """Filter backtest data to only PositionOpened events."""
    return [d for d in data if isinstance(d, PositionOpened)]


def get_account_states(data: list) -> list[AccountState]:
    """Filter backtest data to only AccountState events."""
    return [d for d in data if isinstance(d, AccountState)]


def get_bars(data: list, bar_type: str | None = None) -> list[Bar]:
    """Filter backtest data to only Bar objects, optionally by bar_type."""
    bars = [d for d in data if isinstance(d, Bar)]
    if bar_type:
        bars = [b for b in bars if str(b.bar_type) == bar_type]
    return bars


def list_bar_types_from_data(data: list) -> list[str]:
    """Extract sorted unique bar type strings from backtest data."""
    return sorted({str(b.bar_type) for b in data if isinstance(b, Bar)})
```

- [ ] **Step 2: Verify the module imports correctly**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.store.catalog_reader import read_backtest_data, get_fills, get_positions_closed, get_positions_opened, get_account_states, get_bars, list_bar_types_from_data; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/server/server/store/catalog_reader.py
git commit -m "feat: add catalog_reader module for ParquetDataCatalog access"
```

---

### Task 2: Update `transforms.py` — fills and positions

**Files:**
- Modify: `packages/server/server/store/transforms.py`

This task changes `fills_table_to_dicts`, `positions_closed_to_dicts`, and `_extract_strategy_name` from Arrow table input to Nautilus object input.

- [ ] **Step 1: Replace `fills_table_to_dicts` with `fills_to_dicts`**

Replace the entire `fills_table_to_dicts` function (lines 17-36) with:

```python
def fills_to_dicts(fills: list) -> list[dict]:
    """Convert OrderFilled objects to list of dicts."""
    return [
        {
            "client_order_id": str(f.client_order_id),
            "venue_order_id": str(f.venue_order_id),
            "trade_id": str(f.trade_id),
            "position_id": str(f.position_id) if f.position_id else None,
            "instrument_id": str(f.instrument_id),
            "order_side": str(f.order_side),
            "order_type": str(f.order_type),
            "last_qty": float(f.last_qty),
            "last_px": float(f.last_px),
            "currency": str(f.currency),
            "commission": str(f.commission),
            "ts_event": _ns_to_iso(f.ts_event),
        }
        for f in fills
    ]
```

- [ ] **Step 2: Replace `positions_closed_to_dicts`**

Replace the entire `positions_closed_to_dicts` function (lines 39-61) with:

```python
def positions_closed_to_dicts(positions: list) -> list[dict]:
    """Convert PositionClosed objects to list of dicts."""
    return [
        {
            "position_id": str(p.position_id),
            "instrument_id": str(p.instrument_id),
            "strategy_id": str(p.strategy_id),
            "entry": str(p.entry),
            "side": str(p.side),
            "quantity": float(p.quantity),
            "peak_qty": float(p.peak_qty),
            "avg_px_open": p.avg_px_open,
            "avg_px_close": p.avg_px_close,
            "realized_return": _safe_float(p.realized_return),
            "realized_pnl": float(p.realized_pnl),
            "currency": str(p.currency),
            "ts_opened": _ns_to_iso(p.ts_opened),
            "ts_closed": _ns_to_iso(p.ts_closed),
            "duration_ns": int(p.duration_ns),
        }
        for p in positions
    ]
```

- [ ] **Step 3: Replace `_extract_strategy_name`**

Replace the `_extract_strategy_name` function (lines 194-204) with:

```python
def _extract_strategy_name(config: dict, positions_opened: list) -> str:
    """Extract strategy name from position data, falling back to config."""
    strategy_name = config.get("strategy_name")
    if strategy_name:
        return strategy_name

    if positions_opened and len(positions_opened) > 0:
        return str(positions_opened[0].strategy_id)

    strategies = config.get("strategies", [])
    if strategies:
        return strategies[0].get("strategy_path", "Unknown")

    return "Unknown"
```

Note: The `strategy_name` check comes first (added by card #99 for compatibility).

- [ ] **Step 4: Update `run_summary` signature**

Replace the `run_summary` function (lines 164-191) with:

```python
def run_summary(
    run_id: str,
    config: dict,
    positions_count: int,
    fills_count: int,
    positions_opened: list | None = None,
    positions_closed: list | None = None,
) -> dict:
    """Build a run summary dict from config and counts."""
    from server.store.metrics import compute_run_metrics, empty_metrics

    strategy_name = _extract_strategy_name(config, positions_opened or [])

    summary = {
        "run_id": run_id,
        "trader_id": config.get("trader_id", "Unknown"),
        "strategy": strategy_name,
        "total_positions": positions_count,
        "total_fills": fills_count,
    }

    if positions_closed and len(positions_closed) > 0:
        metrics = compute_run_metrics(positions_closed)
    else:
        metrics = empty_metrics()

    summary.update(metrics)
    return summary
```

- [ ] **Step 5: Remove the `import pyarrow as pa` line**

Remove line 9 (`import pyarrow as pa`) since it's no longer used by any function in this file.

- [ ] **Step 6: Verify the module still loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.store.transforms import fills_to_dicts, positions_closed_to_dicts, run_summary, account_states_to_dicts, bars_to_ohlc; print('OK')"`

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add packages/server/server/store/transforms.py
git commit -m "refactor: update fills/positions/summary transforms to accept Nautilus objects"
```

---

### Task 3: Update `transforms.py` — account states

**Files:**
- Modify: `packages/server/server/store/transforms.py`

- [ ] **Step 1: Replace `account_states_to_dicts`**

Replace the `account_states_to_dicts` function with:

```python
def account_states_to_dicts(states: list) -> list[dict]:
    """Convert AccountState objects to list of dicts, skipping states with no balance."""
    results = []
    for s in states:
        if not s.balances:
            continue
        b = s.balances[0]
        total = _safe_float(float(b.total))
        if total is None:
            continue
        results.append({
            "ts_event": _ns_to_iso(s.ts_event),
            "balance_total": total,
            "balance_free": _safe_float(float(b.free)),
            "balance_locked": _safe_float(float(b.locked)),
            "currency": str(b.currency),
        })
    return results
```

- [ ] **Step 2: Verify the module still loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.store.transforms import account_states_to_dicts; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/server/server/store/transforms.py
git commit -m "refactor: update account_states_to_dicts to accept Nautilus AccountState objects"
```

---

### Task 4: Update `metrics.py`

**Files:**
- Modify: `packages/server/server/store/metrics.py`

`compute_run_metrics` currently takes `pa.Table` and reads columns. It needs to accept `list[PositionClosed]` and read object attributes.

- [ ] **Step 1: Replace `compute_run_metrics`**

Replace the `compute_run_metrics` function (lines 79-156) with:

```python
def compute_run_metrics(positions_closed: list) -> dict:
    """Compute trade metrics from a list of PositionClosed objects.

    Returns a dict with all metric keys. Returns empty_metrics() for empty lists.
    """
    if not positions_closed:
        return empty_metrics()

    pnl_col: list[float] = [float(p.realized_pnl) for p in positions_closed]
    ts_opened_col: list[int] = [p.ts_opened for p in positions_closed]
    ts_closed_col: list[int] = [p.ts_closed for p in positions_closed]
    duration_col: list[int] = [p.duration_ns for p in positions_closed]

    total_positions = len(pnl_col)

    # --- total_pnl ---
    total_pnl = round(sum(pnl_col), 2)

    # --- wins / losses ---
    winning_pnls = [p for p in pnl_col if p > 0]
    losing_pnls = [p for p in pnl_col if p <= 0]
    wins = len(winning_pnls)
    losses = len(losing_pnls)

    # --- win_rate ---
    win_rate = round(wins / total_positions, 4)

    # --- avg_win ---
    avg_win: float | None = (
        round(sum(winning_pnls) / wins, 2) if wins > 0 else None
    )

    # --- avg_loss ---
    avg_loss: float | None = (
        round(sum(losing_pnls) / losses, 2) if losses > 0 else None
    )

    # --- win_loss_ratio ---
    win_loss_ratio: float | None = None
    if avg_win is not None and avg_loss is not None and avg_loss != 0:
        win_loss_ratio = round(abs(avg_win / avg_loss), 2)

    # --- expectancy ---
    expectancy: float | None = None
    if avg_win is not None and avg_loss is not None:
        expectancy = _expectancy(win_rate, avg_win, avg_loss)

    # --- avg_hold_hours ---
    mean_ns = sum(duration_col) / len(duration_col)
    avg_hold_hours = round(mean_ns / 3_600_000_000_000, 1)

    # --- sharpe_ratio ---
    sharpe_ratio = _sharpe_ratio(pnl_col, ts_closed_col)

    # --- run span in weeks ---
    span_weeks = _run_span_weeks(ts_opened_col, ts_closed_col)

    # --- pnl_per_week / trades_per_week ---
    pnl_per_week: float | None = None
    trades_per_week: float | None = None
    if span_weeks > 0:
        pnl_per_week = round(total_pnl / span_weeks, 2)
        trades_per_week = round(total_positions / span_weeks, 2)

    return {
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "expectancy": expectancy,
        "sharpe_ratio": sharpe_ratio,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "wins": wins,
        "losses": losses,
        "avg_hold_hours": avg_hold_hours,
        "pnl_per_week": pnl_per_week,
        "trades_per_week": trades_per_week,
    }
```

- [ ] **Step 2: Remove the `import pyarrow as pa` line**

Remove line 10 (`import pyarrow as pa`) since it's no longer used.

- [ ] **Step 3: Verify the module still loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.store.metrics import compute_run_metrics, empty_metrics; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/server/server/store/metrics.py
git commit -m "refactor: update compute_run_metrics to accept PositionClosed objects"
```

---

### Task 5: Update `reader.py` — remove replaced functions, update `list_catalog_entries`

**Files:**
- Modify: `packages/server/server/store/reader.py`

- [ ] **Step 1: Remove replaced functions**

Remove these functions entirely:
- `list_run_ids` (lines 20-28)
- `read_fills` (lines 52-56)
- `read_positions_opened` (lines 59-62)
- `read_positions_closed` (lines 66-70)
- `read_account_states` (lines 73-77)
- `list_bar_types` (lines 80-85)
- `read_bars_raw` (lines 88-107)

Keep these functions:
- `read_run_config` (lines 31-37)
- `_read_ipc_stream` (lines 40-49) — still used by `list_catalog_entries`
- `list_catalog_entries` (lines 110-168)

Also remove `import pyarrow.compute as pc` if `list_catalog_entries` still needs it (it does — keep it). Remove `import pyarrow as pa` only if `_read_ipc_stream` no longer needs it (it does — keep it).

- [ ] **Step 2: Update `list_catalog_entries` to accept a catalog parameter**

Replace the function signature and the first loop line:

```python
def list_catalog_entries(
    store_path: Path,
    catalog: "ParquetDataCatalog | None" = None,
) -> list[dict]:
    """Scan all runs to build a deduplicated catalog of available instrument data.

    For each unique bar_type directory across all runs, reads all feather files
    to extract instrument ID, total bar count, and date range.
    Returns one entry per unique bar_type.
    """
    if catalog is not None:
        run_ids = catalog.list_backtest_runs()
    else:
        # Fallback: scan directories directly
        backtest_dir = store_path / "backtest"
        if not backtest_dir.exists():
            run_ids = []
        else:
            run_ids = sorted(
                [d.name for d in backtest_dir.iterdir() if d.is_dir()],
                reverse=True,
            )

    seen: dict[str, dict] = {}

    for run_id in run_ids:
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

- [ ] **Step 3: The final `reader.py` should contain only these functions**

Verify the file has exactly:
- `read_run_config(store_path, run_id)` — unchanged
- `_read_ipc_stream(path)` — unchanged, internal helper
- `list_catalog_entries(store_path, catalog=None)` — updated signature

And imports: `json`, `Path`, `pa`, `pc`.

- [ ] **Step 4: Verify the module still loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.store.reader import read_run_config, list_catalog_entries; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/store/reader.py
git commit -m "refactor: remove reader functions replaced by ParquetDataCatalog"
```

---

### Task 6: Update simple routes — `fills.py`, `positions.py`, `account.py`

**Files:**
- Modify: `packages/server/server/routes/fills.py`
- Modify: `packages/server/server/routes/positions.py`
- Modify: `packages/server/server/routes/account.py`

- [ ] **Step 1: Rewrite `fills.py`**

Replace the entire file:

```python
"""Routes for order fills and computed trades."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import transforms
from server.store.catalog_reader import get_fills, read_backtest_data

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs/{run_id}/fills")
def get_fills_route(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    fills = get_fills(data)
    if not fills:
        raise HTTPException(status_code=404, detail="No fills found")
    return transforms.fills_to_dicts(fills)


@router.get("/runs/{run_id}/trades")
def get_trades(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    fills = get_fills(data)
    if not fills:
        raise HTTPException(status_code=404, detail="No fills found")
    fills_dicts = transforms.fills_to_dicts(fills)
    return transforms.fills_to_trades(fills_dicts)
```

- [ ] **Step 2: Rewrite `positions.py`**

Replace the entire file:

```python
"""Routes for position data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import transforms
from server.store.catalog_reader import get_positions_closed, read_backtest_data

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs/{run_id}/positions")
def get_positions(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    positions = get_positions_closed(data)
    if not positions:
        raise HTTPException(status_code=404, detail="No positions found")
    return transforms.positions_closed_to_dicts(positions)
```

- [ ] **Step 3: Rewrite `account.py`**

Replace the entire file:

```python
"""Routes for account state and equity curve."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import transforms
from server.store.catalog_reader import get_account_states, read_backtest_data

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs/{run_id}/account")
def get_account(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    states = get_account_states(data)
    if not states:
        raise HTTPException(status_code=404, detail="No account data found")
    return transforms.account_states_to_dicts(states)


@router.get("/runs/{run_id}/equity")
def get_equity(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    states = get_account_states(data)
    if not states:
        raise HTTPException(status_code=404, detail="No account data found")
    account_dicts = transforms.account_states_to_dicts(states)
    return transforms.account_states_to_equity(account_dicts)
```

- [ ] **Step 4: Verify all three modules load**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.routes.fills import router; from server.routes.positions import router; from server.routes.account import router; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add packages/server/server/routes/fills.py packages/server/server/routes/positions.py packages/server/server/routes/account.py
git commit -m "refactor: update fills/positions/account routes to use ParquetDataCatalog"
```

---

### Task 7: Update `bars.py` and `indicators.py` routes

**Files:**
- Modify: `packages/server/server/routes/bars.py`
- Modify: `packages/server/server/routes/indicators.py`

These routes currently import `ArrowSerializer` — that goes away entirely since `read_backtest()` handles deserialization.

- [ ] **Step 1: Rewrite `bars.py`**

Replace the entire file:

```python
"""Routes for OHLCV bar data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import transforms
from server.store.catalog_reader import get_bars, list_bar_types_from_data, read_backtest_data

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs/{run_id}/bars")
def list_bar_types(run_id: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    return list_bar_types_from_data(data)


@router.get("/runs/{run_id}/bars/{bar_type}")
def get_bars_route(run_id: str, bar_type: str, catalog: ParquetDataCatalog = Depends(_catalog)):
    data = read_backtest_data(catalog, run_id)
    bars = get_bars(data, bar_type)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No bar data for {bar_type}")
    return transforms.bars_to_ohlc(bars)
```

- [ ] **Step 2: Rewrite `indicators.py`**

Replace the entire file:

```python
"""Routes for technical indicator data."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store.catalog_reader import get_bars, read_backtest_data
from server.store.indicators import (
    IndicatorMeta,
    IndicatorResult,
    compute_indicator,
    list_available_indicators,
)

router = APIRouter()


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/indicators")
def get_available_indicators() -> list[IndicatorMeta]:
    return list_available_indicators()


@router.get("/runs/{run_id}/bars/{bar_type}/indicators")
def get_indicators(
    run_id: str,
    bar_type: str,
    ids: str = Query(..., description="Comma-separated indicator IDs"),
    catalog: ParquetDataCatalog = Depends(_catalog),
) -> list[IndicatorResult]:
    data = read_backtest_data(catalog, run_id)
    bars = get_bars(data, bar_type)
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
```

- [ ] **Step 3: Verify both modules load**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.routes.bars import router; from server.routes.indicators import router; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/server/server/routes/bars.py packages/server/server/routes/indicators.py
git commit -m "refactor: update bars/indicators routes to use ParquetDataCatalog"
```

---

### Task 8: Update `runs.py` route

**Files:**
- Modify: `packages/server/server/routes/runs.py`

This is the most complex route — `list_runs` reads multiple data types per run, and `get_run` reads config + catalog data.

- [ ] **Step 1: Rewrite `runs.py`**

Replace the entire file:

```python
"""Routes for listing and viewing backtest runs."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import reader, transforms
from server.store.catalog_reader import (
    get_fills,
    get_positions_closed,
    get_positions_opened,
    list_bar_types_from_data,
    read_backtest_data,
)

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/runs")
def list_runs(
    page: int = 1,
    per_page: int = 20,
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    run_ids = catalog.list_backtest_runs()
    total = len(run_ids)

    start = (page - 1) * per_page
    end = start + per_page
    page_ids = run_ids[start:end]

    runs = []
    for run_id in page_ids:
        config = reader.read_run_config(store_path, run_id)
        data = read_backtest_data(catalog, run_id)

        fills = get_fills(data)
        positions_closed = get_positions_closed(data)
        positions_opened = get_positions_opened(data)

        summary = transforms.run_summary(
            run_id,
            config,
            len(positions_closed),
            len(fills),
            positions_opened,
            positions_closed,
        )
        runs.append(summary)

    return {"runs": runs, "total": total, "page": page, "per_page": per_page}


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    config = reader.read_run_config(store_path, run_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    data = read_backtest_data(catalog, run_id)
    fills = get_fills(data)
    positions = get_positions_closed(data)

    return {
        "run_id": run_id,
        "config": config,
        "total_fills": len(fills),
        "total_positions": len(positions),
        "bar_types": list_bar_types_from_data(data),
    }
```

- [ ] **Step 2: Verify the module loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.routes.runs import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/server/server/routes/runs.py
git commit -m "refactor: update runs routes to use ParquetDataCatalog"
```

---

### Task 9: Update `catalog.py` route

**Files:**
- Modify: `packages/server/server/routes/catalog.py`

- [ ] **Step 1: Rewrite `catalog.py`**

Replace the entire file:

```python
"""Routes for listing available instrument data in the catalog."""

from pathlib import Path

from fastapi import APIRouter, Depends

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from server.config import get_settings
from server.store import reader, transforms

router = APIRouter()


def _store_path() -> Path:
    return Path(get_settings().store_path)


def _catalog() -> ParquetDataCatalog:
    return ParquetDataCatalog(str(Path(get_settings().store_path)))


@router.get("/catalog")
def list_catalog(
    store_path: Path = Depends(_store_path),
    catalog: ParquetDataCatalog = Depends(_catalog),
):
    entries = reader.list_catalog_entries(store_path, catalog=catalog)
    return [transforms.catalog_entry_to_dict(e) for e in entries]
```

- [ ] **Step 2: Verify the module loads**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -c "from server.routes.catalog import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/server/server/routes/catalog.py
git commit -m "refactor: update catalog route to pass ParquetDataCatalog to list_catalog_entries"
```

---

### Task 10: Verification — type check, lint, server startup

**Files:** None (verification only)

- [ ] **Step 1: Run type checking**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -m mypy server/ --ignore-missing-imports 2>&1 | head -50`

If mypy is not installed, skip this step — the import verification in previous tasks covers basic type issues.

- [ ] **Step 2: Run linting**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -m ruff check server/`

Fix any issues found.

- [ ] **Step 3: Start the server and verify it boots**

Run: `cd /Users/mordrax/code/nautilus_automatron/packages/server && .venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port 8001`

Expected: Server starts without import errors. Test with:

Run: `curl -s http://localhost:8001/api/runs | python3 -m json.tool | head -5`

Expected: JSON response (runs list, possibly empty if no event data yet).

- [ ] **Step 4: Verify catalog endpoint still works**

Run: `curl -s http://localhost:8001/api/catalog | python3 -m json.tool | head -20`

Expected: JSON array of catalog entries (these are bar data from existing runs).

- [ ] **Step 5: Verify bars endpoint still works**

Pick a known run ID and bar type from the catalog data:

Run: `curl -s http://localhost:8001/api/runs | python3 -m json.tool`

If runs exist, test bars:

Run: `curl -s "http://localhost:8001/api/runs/{run_id}/bars" | python3 -m json.tool`

- [ ] **Step 6: Commit any lint fixes**

```bash
git add -u
git commit -m "fix: lint fixes after ParquetDataCatalog migration"
```
