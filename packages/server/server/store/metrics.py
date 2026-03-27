"""Pure functions for computing trade metrics from a positions_closed Arrow table.

All functions are stateless and take Arrow tables or plain Python structures.
"""

import math
from collections import defaultdict
from datetime import datetime, timezone

import pyarrow as pa

# Nanoseconds per week
_NS_PER_WEEK = 7 * 86_400_000_000_000


def empty_metrics() -> dict:
    """Return a metrics dict with all None values (for runs with 0 positions)."""
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
    """Compute expectancy: (win_rate * avg_win) - ((1 - win_rate) * |avg_loss|).

    avg_loss is expected to be negative (or zero); abs() is applied internally.
    """
    return round((win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss)), 2)


def _run_span_weeks(ts_openeds: list[int], ts_closeds: list[int]) -> float:
    """Compute run span in weeks: from min(ts_opened) to max(ts_closed).

    Timestamps are nanoseconds since epoch.
    """
    span_ns = max(ts_closeds) - min(ts_openeds)
    return span_ns / _NS_PER_WEEK


def _sharpe_ratio(pnls: list[float], ts_closeds: list[int]) -> float | None:
    """Compute annualized Sharpe ratio from monthly grouped PnLs.

    Groups PnLs by calendar month (using ts_closed), sums per month to get
    monthly returns, then computes mean / sample_std * sqrt(12).

    Returns None if < 2 months of data or sample std == 0.
    """
    monthly: dict[tuple[int, int], float] = defaultdict(float)
    for pnl, ts_ns in zip(pnls, ts_closeds):
        dt = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
        monthly[(dt.year, dt.month)] += pnl

    returns = list(monthly.values())
    if len(returns) < 2:
        return None

    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)

    if variance == 0.0:
        return None

    std = math.sqrt(variance)
    return round((mean / std) * math.sqrt(12), 2)


def compute_run_metrics(positions_closed: pa.Table) -> dict:
    """Compute trade metrics from a positions_closed Arrow table.

    Returns a dict with all metric keys. Returns empty_metrics() for empty tables.
    """
    if len(positions_closed) == 0:
        return empty_metrics()

    pnl_col: list[float] = positions_closed.column("realized_pnl").to_pylist()
    ts_opened_col: list[int] = positions_closed.column("ts_opened").to_pylist()
    ts_closed_col: list[int] = positions_closed.column("ts_closed").to_pylist()
    duration_col: list[int] = positions_closed.column("duration_ns").to_pylist()

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
