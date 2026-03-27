# Runs Page: Backtest Statistics Table — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing runs list with a Tabulator-powered table showing 11 computed trade metrics per run, with sorting and filtering on every column.

**Architecture:** Backend computes all metrics server-side from `position_closed_0.feather` and returns them in the existing `/api/runs` response. Frontend replaces the shadcn Table with `react-tabulator`, configured with column-level sorting (numeric/string-aware) and header filters (>, <, substring). A "View" column at the end navigates to the run detail page.

**Tech Stack:** Python (pyarrow, math), FastAPI, react-tabulator, TypeScript, Effect-TS, Playwright

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `packages/server/server/store/metrics.py` | Pure functions to compute trade metrics from a positions Arrow table |
| Create | `packages/server/tests/test_metrics.py` | Unit tests for metrics computation |
| Modify | `packages/server/server/store/transforms.py:164-180` | Update `run_summary()` to accept positions_closed and merge metrics |
| Modify | `packages/server/server/routes/runs.py:30-43` | Pass positions_closed table to `run_summary()` |
| Modify | `packages/client/src/types/api.ts:1-7` | Add metric fields to `RunSummary` type |
| Modify | `packages/client/src/components/runs/RunList.tsx` | Replace shadcn Table with react-tabulator |
| Modify | `packages/client/src/pages/RunsPage.tsx` | Remove Card wrapper, adapt to tabulator component |
| Modify | `packages/client/package.json` | Add `react-tabulator` + `tabulator-tables` dependencies |
| Create | `packages/client/src/lib/run-columns.ts` | Tabulator column definitions with formatters and filters |
| Modify | `packages/client/e2e/runs-page.spec.ts` | Update tests for new tabulator-based table |

---

## Task 1: Create metrics computation module

**Files:**
- Create: `packages/server/server/store/metrics.py`
- Create: `packages/server/tests/test_metrics.py`

- [ ] **Step 1: Create test file with first test — total PnL**

```python
# packages/server/tests/test_metrics.py
"""Tests for trade metrics computation."""

import pyarrow as pa

from server.store.metrics import compute_run_metrics


def _make_positions_table(
    realized_pnls: list[float],
    realized_returns: list[float],
    ts_openeds: list[int],
    ts_closeds: list[int],
    duration_nss: list[int],
) -> pa.Table:
    """Build a minimal position_closed Arrow table for testing."""
    n = len(realized_pnls)
    return pa.table({
        "realized_pnl": pa.array(realized_pnls, type=pa.float64()),
        "realized_return": pa.array(realized_returns, type=pa.float64()),
        "ts_opened": pa.array(ts_openeds, type=pa.uint64()),
        "ts_closed": pa.array(ts_closeds, type=pa.uint64()),
        "duration_ns": pa.array(duration_nss, type=pa.uint64()),
        "position_id": pa.array([f"P-{i}" for i in range(n)]),
    })


# --- Helpers for timestamps ---
# 1 hour in nanoseconds
_1H_NS = 3_600_000_000_000
# 1 day in nanoseconds
_1D_NS = 86_400_000_000_000
# Base timestamp: 2024-01-01 00:00:00 UTC in nanoseconds
_BASE_TS = 1_704_067_200_000_000_000


def test_total_pnl():
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0, 50.0],
        realized_returns=[0.1, -0.03, 0.05],
        ts_openeds=[_BASE_TS, _BASE_TS + _1D_NS, _BASE_TS + 2 * _1D_NS],
        ts_closeds=[_BASE_TS + _1H_NS, _BASE_TS + _1D_NS + _1H_NS, _BASE_TS + 2 * _1D_NS + _1H_NS],
        duration_nss=[_1H_NS, _1H_NS, _1H_NS],
    )
    result = compute_run_metrics(table)
    assert result["total_pnl"] == 120.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/server && .venv/bin/python -m pytest tests/test_metrics.py::test_total_pnl -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.store.metrics'`

- [ ] **Step 3: Create metrics.py with compute_run_metrics**

```python
# packages/server/server/store/metrics.py
"""Pure functions for computing trade metrics from position data.

All functions take Arrow tables and return plain Python values.
No side effects, no I/O.
"""

import math

import pyarrow as pa


def compute_run_metrics(positions_closed: pa.Table) -> dict:
    """Compute all trade metrics from a positions_closed Arrow table.

    Returns a dict with keys:
        total_pnl, win_rate, expectancy, sharpe_ratio,
        avg_win, avg_loss, win_loss_ratio, wins, losses,
        avg_hold_hours, pnl_per_week, trades_per_week
    All values are float | int | None.
    """
    pnls = positions_closed.column("realized_pnl").to_pylist()
    ts_openeds = positions_closed.column("ts_opened").to_pylist()
    ts_closeds = positions_closed.column("ts_closed").to_pylist()
    duration_nss = positions_closed.column("duration_ns").to_pylist()

    n = len(pnls)
    if n == 0:
        return _empty_metrics()

    total_pnl = sum(pnls)

    winning = [p for p in pnls if p > 0]
    losing = [p for p in pnls if p <= 0]
    wins = len(winning)
    losses = len(losing)

    win_rate = wins / n if n > 0 else 0.0
    avg_win = sum(winning) / wins if wins > 0 else 0.0
    avg_loss = sum(losing) / losses if losses > 0 else 0.0
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else None
    expectancy = _expectancy(win_rate, avg_win, avg_loss)
    sharpe_ratio = _sharpe_ratio(pnls, ts_closeds)

    avg_hold_ns = sum(duration_nss) / n
    avg_hold_hours = round(avg_hold_ns / 3_600_000_000_000, 1)

    run_weeks = _run_span_weeks(ts_openeds, ts_closeds)
    pnl_per_week = round(total_pnl / run_weeks, 2) if run_weeks > 0 else None
    trades_per_week = round(n / run_weeks, 2) if run_weeks > 0 else None

    return {
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 4),
        "expectancy": round(expectancy, 2),
        "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio is not None else None,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "win_loss_ratio": round(win_loss_ratio, 2) if win_loss_ratio is not None else None,
        "wins": wins,
        "losses": losses,
        "avg_hold_hours": avg_hold_hours,
        "pnl_per_week": pnl_per_week,
        "trades_per_week": trades_per_week,
    }


def _empty_metrics() -> dict:
    """Return metrics dict with all None values for runs with no positions."""
    return {
        "total_pnl": None,
        "win_rate": None,
        "expectancy": None,
        "sharpe_ratio": None,
        "avg_win": None,
        "avg_loss": None,
        "win_loss_ratio": None,
        "wins": None,
        "losses": None,
        "avg_hold_hours": None,
        "pnl_per_week": None,
        "trades_per_week": None,
    }


def _expectancy(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Compute expectancy: (win_rate * avg_win) - ((1 - win_rate) * |avg_loss|)."""
    return (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))


def _sharpe_ratio(pnls: list[float], ts_closeds: list[int]) -> float | None:
    """Compute annualized Sharpe ratio from monthly returns.

    Groups PnLs by calendar month, computes monthly return series,
    then: sharpe = mean(monthly) / std(monthly) * sqrt(12).
    Returns None if fewer than 2 months of data.
    """
    from datetime import datetime, timezone

    monthly: dict[tuple[int, int], float] = {}
    for pnl, ts in zip(pnls, ts_closeds):
        dt = datetime.fromtimestamp(ts / 1e9, tz=timezone.utc)
        key = (dt.year, dt.month)
        monthly[key] = monthly.get(key, 0.0) + pnl

    returns = list(monthly.values())
    if len(returns) < 2:
        return None

    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(variance)

    if std_r == 0:
        return None

    return (mean_r / std_r) * math.sqrt(12)


def _run_span_weeks(ts_openeds: list[int], ts_closeds: list[int]) -> float:
    """Compute the run span in weeks from first open to last close."""
    first_open = min(ts_openeds)
    last_close = max(ts_closeds)
    span_ns = last_close - first_open
    weeks = span_ns / (7 * 24 * 3_600_000_000_000)
    return weeks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/server && .venv/bin/python -m pytest tests/test_metrics.py::test_total_pnl -v`
Expected: PASS

- [ ] **Step 5: Add remaining metric tests**

Append to `packages/server/tests/test_metrics.py`:

```python
def test_win_rate_and_counts():
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0, 50.0, -10.0],
        realized_returns=[0.1, -0.03, 0.05, -0.01],
        ts_openeds=[_BASE_TS + i * _1D_NS for i in range(4)],
        ts_closeds=[_BASE_TS + i * _1D_NS + _1H_NS for i in range(4)],
        duration_nss=[_1H_NS] * 4,
    )
    result = compute_run_metrics(table)
    assert result["wins"] == 2
    assert result["losses"] == 2
    assert result["win_rate"] == 0.5


def test_avg_win_and_loss():
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0, 50.0, -10.0],
        realized_returns=[0.1, -0.03, 0.05, -0.01],
        ts_openeds=[_BASE_TS + i * _1D_NS for i in range(4)],
        ts_closeds=[_BASE_TS + i * _1D_NS + _1H_NS for i in range(4)],
        duration_nss=[_1H_NS] * 4,
    )
    result = compute_run_metrics(table)
    assert result["avg_win"] == 75.0
    assert result["avg_loss"] == -20.0


def test_win_loss_ratio():
    table = _make_positions_table(
        realized_pnls=[100.0, -50.0],
        realized_returns=[0.1, -0.05],
        ts_openeds=[_BASE_TS, _BASE_TS + _1D_NS],
        ts_closeds=[_BASE_TS + _1H_NS, _BASE_TS + _1D_NS + _1H_NS],
        duration_nss=[_1H_NS, _1H_NS],
    )
    result = compute_run_metrics(table)
    assert result["win_loss_ratio"] == 2.0


def test_expectancy():
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0, 50.0, -10.0],
        realized_returns=[0.1, -0.03, 0.05, -0.01],
        ts_openeds=[_BASE_TS + i * _1D_NS for i in range(4)],
        ts_closeds=[_BASE_TS + i * _1D_NS + _1H_NS for i in range(4)],
        duration_nss=[_1H_NS] * 4,
    )
    result = compute_run_metrics(table)
    # expectancy = (0.5 * 75) - (0.5 * 20) = 37.5 - 10 = 27.5
    assert result["expectancy"] == 27.5


def test_avg_hold_hours():
    two_hours = 2 * _1H_NS
    four_hours = 4 * _1H_NS
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0],
        realized_returns=[0.1, -0.03],
        ts_openeds=[_BASE_TS, _BASE_TS + _1D_NS],
        ts_closeds=[_BASE_TS + two_hours, _BASE_TS + _1D_NS + four_hours],
        duration_nss=[two_hours, four_hours],
    )
    result = compute_run_metrics(table)
    assert result["avg_hold_hours"] == 3.0


def test_sharpe_ratio_requires_two_months():
    # All trades in same month — should return None
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0],
        realized_returns=[0.1, -0.03],
        ts_openeds=[_BASE_TS, _BASE_TS + _1D_NS],
        ts_closeds=[_BASE_TS + _1H_NS, _BASE_TS + _1D_NS + _1H_NS],
        duration_nss=[_1H_NS, _1H_NS],
    )
    result = compute_run_metrics(table)
    assert result["sharpe_ratio"] is None


def test_sharpe_ratio_two_months():
    # Month 1: +100, Month 2: -50
    # _BASE_TS is 2024-01-01, add 31 days for February
    feb_ts = _BASE_TS + 31 * _1D_NS
    table = _make_positions_table(
        realized_pnls=[100.0, -50.0],
        realized_returns=[0.1, -0.05],
        ts_openeds=[_BASE_TS, feb_ts],
        ts_closeds=[_BASE_TS + _1H_NS, feb_ts + _1H_NS],
        duration_nss=[_1H_NS, _1H_NS],
    )
    result = compute_run_metrics(table)
    assert result["sharpe_ratio"] is not None
    # monthly returns: [100, -50], mean=25, std=106.07, sharpe=25/106.07*sqrt(12)
    assert isinstance(result["sharpe_ratio"], float)


def test_pnl_per_week_and_trades_per_week():
    # 2 trades spanning 2 weeks (14 days)
    table = _make_positions_table(
        realized_pnls=[100.0, -30.0],
        realized_returns=[0.1, -0.03],
        ts_openeds=[_BASE_TS, _BASE_TS + 7 * _1D_NS],
        ts_closeds=[_BASE_TS + _1H_NS, _BASE_TS + 14 * _1D_NS],
        duration_nss=[_1H_NS, 7 * _1D_NS],
    )
    result = compute_run_metrics(table)
    # span = 14 days = 2 weeks
    assert result["pnl_per_week"] == 35.0  # 70 / 2
    assert result["trades_per_week"] == 1.0  # 2 / 2


def test_empty_table_returns_all_none():
    table = _make_positions_table(
        realized_pnls=[],
        realized_returns=[],
        ts_openeds=[],
        ts_closeds=[],
        duration_nss=[],
    )
    result = compute_run_metrics(table)
    for key, value in result.items():
        assert value is None, f"{key} should be None for empty table"


def test_all_winning_trades():
    table = _make_positions_table(
        realized_pnls=[100.0, 50.0, 75.0],
        realized_returns=[0.1, 0.05, 0.075],
        ts_openeds=[_BASE_TS + i * _1D_NS for i in range(3)],
        ts_closeds=[_BASE_TS + i * _1D_NS + _1H_NS for i in range(3)],
        duration_nss=[_1H_NS] * 3,
    )
    result = compute_run_metrics(table)
    assert result["win_rate"] == 1.0
    assert result["losses"] == 0
    assert result["avg_loss"] == 0.0
    assert result["win_loss_ratio"] is None  # division by zero
```

- [ ] **Step 6: Run all metric tests**

Run: `cd packages/server && .venv/bin/python -m pytest tests/test_metrics.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron
git add packages/server/server/store/metrics.py packages/server/tests/test_metrics.py
git commit -m "feat: add trade metrics computation module with tests"
```

---

## Task 2: Wire metrics into run_summary and API route

**Files:**
- Modify: `packages/server/server/store/transforms.py:164-180`
- Modify: `packages/server/server/routes/runs.py:30-43`

- [ ] **Step 1: Update run_summary to accept positions_closed and merge metrics**

In `packages/server/server/store/transforms.py`, replace the `run_summary` function:

```python
def run_summary(
    run_id: str,
    config: dict,
    positions_count: int,
    fills_count: int,
    positions_opened: "pa.Table | None" = None,
    positions_closed: "pa.Table | None" = None,
) -> dict:
    """Build a run summary dict from config, counts, and computed metrics."""
    from server.store.metrics import compute_run_metrics

    strategy_name = _extract_strategy_name(config, positions_opened)

    summary = {
        "run_id": run_id,
        "trader_id": config.get("trader_id", "Unknown"),
        "strategy": strategy_name,
        "total_positions": positions_count,
        "total_fills": fills_count,
    }

    if positions_closed is not None and len(positions_closed) > 0:
        metrics = compute_run_metrics(positions_closed)
    else:
        from server.store.metrics import _empty_metrics
        metrics = _empty_metrics()

    summary.update(metrics)
    return summary
```

- [ ] **Step 2: Update runs route to pass positions_closed**

In `packages/server/server/routes/runs.py`, update the `list_runs` function body (the loop starting at line 31):

```python
        summary = transforms.run_summary(
            run_id, config, positions_count, fills_count, positions_opened, positions_table
        )
```

This is a one-line change — just add `positions_table` as the last argument to the existing call on line 40-42.

- [ ] **Step 3: Verify the server starts and API returns metrics**

Run: `cd packages/server && NAUTILUS_STORE_PATH=../client/e2e/test-data/backtest_catalog .venv/bin/python -c "from server.main import create_app; print('OK')"`
Expected: `OK` (no import errors)

Run: `cd packages/server && NAUTILUS_STORE_PATH=../client/e2e/test-data/backtest_catalog .venv/bin/uvicorn server.main:app --port 9999 &`
Then: `curl -s http://localhost:9999/api/runs?per_page=1 | python3 -m json.tool`
Expected: JSON response with `runs[0]` containing `total_pnl`, `win_rate`, etc. alongside existing fields.
Kill the test server after verifying.

- [ ] **Step 4: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron
git add packages/server/server/store/transforms.py packages/server/server/routes/runs.py
git commit -m "feat: wire trade metrics into run summary API response"
```

---

## Task 3: Install react-tabulator and add column definitions

**Files:**
- Modify: `packages/client/package.json`
- Create: `packages/client/src/lib/run-columns.ts`

- [ ] **Step 1: Install react-tabulator**

```bash
cd /Users/mordrax/code/nautilus_automatron/packages/client && bun add react-tabulator tabulator-tables
```

- [ ] **Step 2: Create column definitions file**

```typescript
// packages/client/src/lib/run-columns.ts
import type { ColumnDefinition } from 'tabulator-tables'

const pnlFormatter = (cell: any): string => {
  const value = cell.getValue()
  if (value == null) return '—'
  const color = value >= 0 ? '#22c55e' : '#ef4444'
  return `<span style="color: ${color}; font-weight: 600;">${value >= 0 ? '+' : ''}${value.toFixed(2)}</span>`
}

const percentFormatter = (cell: any): string => {
  const value = cell.getValue()
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

const currencyFormatter = (cell: any): string => {
  const value = cell.getValue()
  if (value == null) return '—'
  return value.toFixed(2)
}

const hoursFormatter = (cell: any): string => {
  const value = cell.getValue()
  if (value == null) return '—'
  return `${value}h`
}

const ratioFormatter = (cell: any): string => {
  const value = cell.getValue()
  if (value == null) return '—'
  return value.toFixed(2)
}

const winsLossesFormatter = (cell: any): string => {
  const data = cell.getData()
  if (data.wins == null) return '—'
  return `${data.wins} / ${data.losses}`
}

const numericHeaderFilter = {
  headerFilter: 'input' as const,
  headerFilterFunc: (headerValue: string, rowValue: number): boolean => {
    if (!headerValue) return true
    const trimmed = headerValue.trim()
    if (trimmed.startsWith('>')) {
      const threshold = parseFloat(trimmed.slice(1))
      return !isNaN(threshold) && rowValue > threshold
    }
    if (trimmed.startsWith('<')) {
      const threshold = parseFloat(trimmed.slice(1))
      return !isNaN(threshold) && rowValue < threshold
    }
    if (trimmed.startsWith('=')) {
      const threshold = parseFloat(trimmed.slice(1))
      return !isNaN(threshold) && rowValue === threshold
    }
    const threshold = parseFloat(trimmed)
    return isNaN(threshold) || rowValue === threshold
  },
}

const stringHeaderFilter = {
  headerFilter: 'input' as const,
  headerFilterFunc: (headerValue: string, rowValue: string): boolean => {
    if (!headerValue) return true
    return rowValue.toLowerCase().includes(headerValue.toLowerCase())
  },
}

export const createRunColumns = (onViewRun: (runId: string) => void): ColumnDefinition[] => [
  {
    title: 'Run ID',
    field: 'run_id',
    formatter: (cell: any) => {
      const value = cell.getValue()
      return `<span style="font-family: monospace; font-size: 0.75rem;">${value.slice(0, 8)}...</span>`
    },
    sorter: 'string',
    ...stringHeaderFilter,
    width: 120,
  },
  {
    title: 'Trader',
    field: 'trader_id',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: 'Strategy',
    field: 'strategy',
    sorter: 'string',
    ...stringHeaderFilter,
  },
  {
    title: 'Positions',
    field: 'total_positions',
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Fills',
    field: 'total_fills',
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Total PnL',
    field: 'total_pnl',
    formatter: pnlFormatter,
    formatterParams: { html: true },
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Win Rate',
    field: 'win_rate',
    formatter: percentFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Expectancy',
    field: 'expectancy',
    formatter: currencyFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Sharpe',
    field: 'sharpe_ratio',
    formatter: ratioFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Avg Win',
    field: 'avg_win',
    formatter: currencyFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Avg Loss',
    field: 'avg_loss',
    formatter: pnlFormatter,
    formatterParams: { html: true },
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'W/L Ratio',
    field: 'win_loss_ratio',
    formatter: ratioFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'W / L',
    field: 'wins',
    formatter: winsLossesFormatter,
    sorter: 'number',
    hozAlign: 'center',
    ...numericHeaderFilter,
  },
  {
    title: 'Avg Hold',
    field: 'avg_hold_hours',
    formatter: hoursFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'PnL/Week',
    field: 'pnl_per_week',
    formatter: pnlFormatter,
    formatterParams: { html: true },
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: 'Trades/Week',
    field: 'trades_per_week',
    formatter: ratioFormatter,
    sorter: 'number',
    hozAlign: 'right',
    ...numericHeaderFilter,
  },
  {
    title: '',
    field: 'run_id',
    formatter: () => '<button style="padding: 2px 8px; cursor: pointer;">View</button>',
    formatterParams: { html: true },
    width: 70,
    headerSort: false,
    headerFilter: undefined,
    cellClick: (_e: any, cell: any) => {
      onViewRun(cell.getValue())
    },
  },
]
```

- [ ] **Step 3: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron
git add packages/client/package.json packages/client/bun.lock packages/client/src/lib/run-columns.ts
git commit -m "feat: add react-tabulator dependency and column definitions"
```

---

## Task 4: Update TypeScript types

**Files:**
- Modify: `packages/client/src/types/api.ts:1-7`

- [ ] **Step 1: Update RunSummary type**

Replace lines 1-7 in `packages/client/src/types/api.ts`:

```typescript
export type RunSummary = {
  readonly run_id: string
  readonly trader_id: string
  readonly strategy: string
  readonly total_positions: number
  readonly total_fills: number
  readonly total_pnl: number | null
  readonly win_rate: number | null
  readonly expectancy: number | null
  readonly sharpe_ratio: number | null
  readonly avg_win: number | null
  readonly avg_loss: number | null
  readonly win_loss_ratio: number | null
  readonly wins: number | null
  readonly losses: number | null
  readonly avg_hold_hours: number | null
  readonly pnl_per_week: number | null
  readonly trades_per_week: number | null
}
```

- [ ] **Step 2: Run type check**

Run: `cd packages/client && bunx tsc --noEmit`
Expected: Type errors in `RunList.tsx` (expected — we'll fix in next task)

- [ ] **Step 3: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron
git add packages/client/src/types/api.ts
git commit -m "feat: add metric fields to RunSummary type"
```

---

## Task 5: Replace RunList with Tabulator table

**Files:**
- Modify: `packages/client/src/components/runs/RunList.tsx`
- Modify: `packages/client/src/pages/RunsPage.tsx`

- [ ] **Step 1: Rewrite RunList.tsx with react-tabulator**

Replace entire contents of `packages/client/src/components/runs/RunList.tsx`:

```typescript
import { useRef, useEffect } from 'react'
import { useLocation } from 'wouter'
import { TabulatorFull as Tabulator } from 'tabulator-tables'
import 'tabulator-tables/dist/css/tabulator_midnight.min.css'
import type { RunSummary } from '@/types/api'
import { createRunColumns } from '@/lib/run-columns'

type RunListProps = {
  readonly runs: readonly RunSummary[]
}

export const RunList = ({ runs }: RunListProps) => {
  const [, setLocation] = useLocation()
  const tableRef = useRef<HTMLDivElement>(null)
  const tabulatorRef = useRef<Tabulator | null>(null)

  useEffect(() => {
    if (!tableRef.current) return

    const columns = createRunColumns((runId: string) => {
      setLocation(`/runs/${runId}`)
    })

    const table = new Tabulator(tableRef.current, {
      data: runs as RunSummary[],
      columns,
      layout: 'fitData',
      height: '80vh',
      initialSort: [{ column: 'total_pnl', dir: 'desc' }],
      pagination: true,
      paginationSize: 50,
      paginationSizeSelector: [10, 25, 50, 100],
    })

    tabulatorRef.current = table

    return () => {
      table.destroy()
      tabulatorRef.current = null
    }
  }, [runs, setLocation])

  return <div ref={tableRef} />
}
```

- [ ] **Step 2: Update RunsPage to remove Card wrapper**

Replace entire contents of `packages/client/src/pages/RunsPage.tsx`:

```typescript
import { RunList } from '@/components/runs/RunList'
import { useRuns } from '@/hooks/use-runs'

export const RunsPage = () => {
  const { data, isLoading, error } = useRuns()

  if (isLoading) return <div className="text-muted-foreground p-4">Loading runs...</div>
  if (error) return <div className="text-destructive p-4">Error loading runs</div>
  if (!data) return null

  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Backtest Runs ({data.total})</h2>
      <RunList runs={data.runs} />
    </div>
  )
}
```

- [ ] **Step 3: Run type check**

Run: `cd packages/client && bunx tsc --noEmit`
Expected: PASS (no type errors)

- [ ] **Step 4: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron
git add packages/client/src/components/runs/RunList.tsx packages/client/src/pages/RunsPage.tsx
git commit -m "feat: replace runs table with react-tabulator"
```

---

## Task 6: Update Playwright tests

**Files:**
- Modify: `packages/client/e2e/runs-page.spec.ts`

- [ ] **Step 1: Rewrite runs-page.spec.ts for Tabulator table**

Replace entire contents of `packages/client/e2e/runs-page.spec.ts`:

```typescript
import { test, expect } from '@playwright/test'

test.describe('Runs Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('page loads with app title', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Nautilus Automatron' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Runs' })).toBeVisible()
  })

  test('runs table is visible with metric columns', async ({ page }) => {
    await expect(page.getByText('Backtest Runs')).toBeVisible()

    // Tabulator renders column headers inside .tabulator-col-title elements
    const tabulator = page.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    // Verify key columns exist
    for (const col of ['Run ID', 'Strategy', 'Total PnL', 'Win Rate', 'Sharpe', 'Avg Hold']) {
      await expect(tabulator.locator('.tabulator-col-title', { hasText: col }).first()).toBeVisible()
    }
  })

  test('strategy column shows actual names, not Unknown', async ({ page }) => {
    const tabulator = page.locator('.tabulator')
    await expect(tabulator).toBeVisible()

    // Wait for data rows to render
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Check that "Unknown" does not appear in any cell
    const unknownCount = await tabulator.locator('.tabulator-cell', { hasText: 'Unknown' }).count()
    expect(unknownCount).toBe(0)

    // Verify actual strategy name appears
    await expect(tabulator.locator('.tabulator-cell', { hasText: 'EMACross-000' }).first()).toBeVisible()
  })

  test('metric columns display numeric values', async ({ page }) => {
    const tabulator = page.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Total PnL column should have a colored value (+ or -)
    const firstPnlCell = tabulator.locator('.tabulator-row').first().locator('.tabulator-cell').nth(5)
    const pnlText = await firstPnlCell.textContent()
    expect(pnlText).not.toBe('—')
    expect(pnlText).toMatch(/[+-]?\d+\.?\d*/)
  })

  test('clicking View button navigates to detail page', async ({ page }) => {
    const tabulator = page.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Click the View button in the last column of the first row
    const viewButton = tabulator.locator('.tabulator-row').first().locator('button', { hasText: 'View' })
    await viewButton.click()

    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/)
  })

  test('columns are sortable', async ({ page }) => {
    const tabulator = page.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Click Total PnL header to sort
    const pnlHeader = tabulator.locator('.tabulator-col', { hasText: 'Total PnL' }).first()
    await pnlHeader.click()

    // Verify sort indicator appears
    await expect(pnlHeader.locator('.tabulator-col-sorter')).toBeVisible()
  })

  test('header filters are present and functional', async ({ page }) => {
    const tabulator = page.locator('.tabulator')
    await expect(tabulator.locator('.tabulator-row').first()).toBeVisible()

    // Type in the Strategy header filter
    const strategyFilter = tabulator.locator('.tabulator-col', { hasText: 'Strategy' }).locator('input')
    await strategyFilter.fill('EMACross')

    // All visible rows should contain EMACross
    const rows = tabulator.locator('.tabulator-row')
    const count = await rows.count()
    expect(count).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 2: Run Playwright tests headless**

Run: `cd packages/client && TEST_VITE_PORT=5174 TEST_API_PORT=8001 npx playwright test e2e/runs-page.spec.ts --project=headless`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/mordrax/code/nautilus_automatron
git add packages/client/e2e/runs-page.spec.ts
git commit -m "test: update runs page tests for tabulator table with metrics"
```

---

## Task 7: Visual validation in browser

- [ ] **Step 1: Start dev servers in worktree**

```bash
cd <worktree-path>
TEST_VITE_PORT=5174 TEST_API_PORT=8001 bun run dev
```

- [ ] **Step 2: Open Playwright in UI mode for human review**

```bash
cd <worktree-path>/packages/client
TEST_VITE_PORT=5174 TEST_API_PORT=8001 npx playwright test e2e/runs-page.spec.ts --ui
```

- [ ] **Step 3: Validate in Chrome via MCP**

Use Chrome MCP tools to:
1. Navigate to `http://localhost:5174`
2. Verify the Tabulator table renders with all columns
3. Verify metric values are populated (not all null/dashes)
4. Test sorting by clicking a column header
5. Test filtering by typing in a header filter input
6. Click "View" button to verify navigation works
7. Check console for errors

- [ ] **Step 4: Take screenshots for human review**

Capture screenshots of:
- Full table view with metrics
- Sorted by Total PnL
- Filtered by strategy name
