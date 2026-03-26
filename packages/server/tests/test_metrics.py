"""Tests for metrics computation module."""

import math

import pyarrow as pa

from server.store.metrics import (
    _empty_metrics,
    _expectancy,
    _run_span_weeks,
    _sharpe_ratio,
    compute_run_metrics,
)

# Timestamp helpers
_1H_NS = 3_600_000_000_000
_1D_NS = 86_400_000_000_000
_BASE_TS = 1_704_067_200_000_000_000  # 2024-01-01 00:00:00 UTC


def _make_positions_table(
    realized_pnl: list[float],
    ts_opened: list[int] | None = None,
    ts_closed: list[int] | None = None,
    duration_ns: list[int] | None = None,
) -> pa.Table:
    """Build a minimal Arrow positions_closed table for testing."""
    n = len(realized_pnl)

    if ts_opened is None:
        ts_opened = [_BASE_TS + i * _1D_NS for i in range(n)]
    if ts_closed is None:
        ts_closed = [_BASE_TS + i * _1D_NS + _1H_NS for i in range(n)]
    if duration_ns is None:
        duration_ns = [_1H_NS] * n

    return pa.table(
        {
            "realized_pnl": pa.array(realized_pnl, type=pa.float64()),
            "realized_return": pa.array([0.01] * n, type=pa.float64()),
            "ts_opened": pa.array(ts_opened, type=pa.uint64()),
            "ts_closed": pa.array(ts_closed, type=pa.uint64()),
            "duration_ns": pa.array(duration_ns, type=pa.uint64()),
            "position_id": pa.array([f"P-{i}" for i in range(n)], type=pa.string()),
        }
    )


# ---------------------------------------------------------------------------
# _empty_metrics
# ---------------------------------------------------------------------------


def test_empty_metrics_all_none():
    result = _empty_metrics()
    for key, value in result.items():
        assert value is None, f"Expected None for key '{key}', got {value!r}"


def test_empty_metrics_has_all_keys():
    result = _empty_metrics()
    expected_keys = {
        "total_pnl",
        "win_rate",
        "expectancy",
        "sharpe_ratio",
        "avg_win",
        "avg_loss",
        "win_loss_ratio",
        "wins",
        "losses",
        "avg_hold_hours",
        "pnl_per_week",
        "trades_per_week",
    }
    assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# compute_run_metrics — empty table
# ---------------------------------------------------------------------------


def test_empty_table_returns_all_none():
    empty = pa.table(
        {
            "realized_pnl": pa.array([], type=pa.float64()),
            "realized_return": pa.array([], type=pa.float64()),
            "ts_opened": pa.array([], type=pa.uint64()),
            "ts_closed": pa.array([], type=pa.uint64()),
            "duration_ns": pa.array([], type=pa.uint64()),
            "position_id": pa.array([], type=pa.string()),
        }
    )
    result = compute_run_metrics(empty)
    for key, value in result.items():
        assert value is None, f"Expected None for key '{key}', got {value!r}"


# ---------------------------------------------------------------------------
# total_pnl
# ---------------------------------------------------------------------------


def test_total_pnl_sum():
    table = _make_positions_table([100.0, -50.0, 200.0])
    result = compute_run_metrics(table)
    assert result["total_pnl"] == 250.0


def test_total_pnl_rounded_to_2_decimals():
    table = _make_positions_table([100.123, 50.456])
    result = compute_run_metrics(table)
    assert result["total_pnl"] == round(100.123 + 50.456, 2)


# ---------------------------------------------------------------------------
# wins and losses counts
# ---------------------------------------------------------------------------


def test_wins_count():
    table = _make_positions_table([100.0, 200.0, -50.0, -10.0, 0.0])
    result = compute_run_metrics(table)
    assert result["wins"] == 2  # pnl > 0


def test_losses_count():
    table = _make_positions_table([100.0, 200.0, -50.0, -10.0, 0.0])
    result = compute_run_metrics(table)
    assert result["losses"] == 3  # pnl <= 0


# ---------------------------------------------------------------------------
# win_rate
# ---------------------------------------------------------------------------


def test_win_rate():
    table = _make_positions_table([100.0, -50.0, 200.0, -30.0])
    result = compute_run_metrics(table)
    # 2 wins, 4 total
    assert result["win_rate"] == round(2 / 4, 4)


def test_win_rate_rounded_to_4_decimals():
    table = _make_positions_table([100.0, 50.0, -10.0])
    result = compute_run_metrics(table)
    assert result["win_rate"] == round(2 / 3, 4)


# ---------------------------------------------------------------------------
# avg_win and avg_loss
# ---------------------------------------------------------------------------


def test_avg_win():
    table = _make_positions_table([100.0, 200.0, -50.0])
    result = compute_run_metrics(table)
    assert result["avg_win"] == round((100.0 + 200.0) / 2, 2)


def test_avg_loss():
    table = _make_positions_table([100.0, -50.0, -30.0])
    result = compute_run_metrics(table)
    assert result["avg_loss"] == round((-50.0 + -30.0) / 2, 2)


def test_avg_loss_includes_zero_pnl():
    # pnl <= 0 are losses, so 0.0 counts
    table = _make_positions_table([100.0, -50.0, 0.0])
    result = compute_run_metrics(table)
    assert result["avg_loss"] == round((-50.0 + 0.0) / 2, 2)


# ---------------------------------------------------------------------------
# win_loss_ratio
# ---------------------------------------------------------------------------


def test_win_loss_ratio():
    table = _make_positions_table([100.0, -50.0])
    result = compute_run_metrics(table)
    avg_win = 100.0
    avg_loss = -50.0
    expected = round(abs(avg_win / avg_loss), 2)
    assert result["win_loss_ratio"] == expected


def test_win_loss_ratio_none_when_avg_loss_zero():
    # All wins → avg_loss is 0 (or no losses), win_loss_ratio must be None
    table = _make_positions_table([100.0, 200.0, 50.0])
    result = compute_run_metrics(table)
    assert result["win_loss_ratio"] is None


# ---------------------------------------------------------------------------
# expectancy
# ---------------------------------------------------------------------------


def test_expectancy_calculation():
    table = _make_positions_table([100.0, 200.0, -50.0, -30.0])
    result = compute_run_metrics(table)

    win_rate = 2 / 4
    avg_win = (100.0 + 200.0) / 2  # 150
    avg_loss = (-50.0 + -30.0) / 2  # -40
    expected = round((win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss)), 2)
    assert result["expectancy"] == expected


def test_expectancy_helper_function():
    result = _expectancy(0.5, 150.0, -40.0)
    expected = round((0.5 * 150.0) - (0.5 * abs(-40.0)), 2)
    assert result == expected


# ---------------------------------------------------------------------------
# avg_hold_hours
# ---------------------------------------------------------------------------


def test_avg_hold_hours():
    durations = [2 * _1H_NS, 4 * _1H_NS, 6 * _1H_NS]
    table = _make_positions_table([100.0, -50.0, 200.0], duration_ns=durations)
    result = compute_run_metrics(table)
    expected = round(4.0, 1)  # mean of 2, 4, 6 hours
    assert result["avg_hold_hours"] == expected


def test_avg_hold_hours_rounded_to_1():
    durations = [1 * _1H_NS, 2 * _1H_NS]
    table = _make_positions_table([100.0, -50.0], duration_ns=durations)
    result = compute_run_metrics(table)
    assert result["avg_hold_hours"] == round(1.5, 1)


# ---------------------------------------------------------------------------
# pnl_per_week and trades_per_week
# ---------------------------------------------------------------------------


def test_pnl_per_week():
    # Two trades: first opens at BASE, second closes at BASE + 14 days + 1H
    ts_opened = [_BASE_TS, _BASE_TS + 14 * _1D_NS]
    ts_closed = [_BASE_TS + _1H_NS, _BASE_TS + 14 * _1D_NS + _1H_NS]
    table = _make_positions_table(
        [100.0, 200.0],
        ts_opened=ts_opened,
        ts_closed=ts_closed,
    )
    result = compute_run_metrics(table)
    # span = max(ts_closed) - min(ts_opened) = 14 days + 1H
    span_ns = (14 * _1D_NS + _1H_NS)
    span_weeks = span_ns / (7 * _1D_NS)
    expected = round(300.0 / span_weeks, 2)
    assert result["pnl_per_week"] == expected


def test_trades_per_week():
    ts_opened = [_BASE_TS, _BASE_TS + 14 * _1D_NS]
    ts_closed = [_BASE_TS + _1H_NS, _BASE_TS + 14 * _1D_NS + _1H_NS]
    table = _make_positions_table(
        [100.0, 200.0],
        ts_opened=ts_opened,
        ts_closed=ts_closed,
    )
    result = compute_run_metrics(table)
    # span = max(ts_closed) - min(ts_opened) = 14 days + 1H
    span_ns = 14 * _1D_NS + _1H_NS
    span_weeks = span_ns / (7 * _1D_NS)
    expected = round(2 / span_weeks, 2)
    assert result["trades_per_week"] == expected


# ---------------------------------------------------------------------------
# _run_span_weeks helper
# ---------------------------------------------------------------------------


def test_run_span_weeks():
    ts_openeds = [_BASE_TS, _BASE_TS + 3 * _1D_NS]
    ts_closeds = [_BASE_TS + _1H_NS, _BASE_TS + 14 * _1D_NS]
    result = _run_span_weeks(ts_openeds, ts_closeds)
    # span = max(ts_closed) - min(ts_opened) = 14 days + 1H in weeks
    span_ns = (_BASE_TS + 14 * _1D_NS) - _BASE_TS
    expected = span_ns / (7 * _1D_NS)
    assert math.isclose(result, expected, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# _sharpe_ratio helper
# ---------------------------------------------------------------------------


def test_sharpe_ratio_none_with_single_month():
    # All trades in same month → < 2 months → None
    pnls = [100.0, -50.0, 200.0]
    ts_closeds = [
        _BASE_TS + _1D_NS,      # Jan 2024
        _BASE_TS + 2 * _1D_NS,  # Jan 2024
        _BASE_TS + 3 * _1D_NS,  # Jan 2024
    ]
    result = _sharpe_ratio(pnls, ts_closeds)
    assert result is None


def test_sharpe_ratio_none_with_zero_std():
    # Same monthly return every month → std == 0 → None
    # Two months, each with PnL 100
    _FEB_1_2024 = 1706745600000000000  # 2024-02-01 00:00:00 UTC
    pnls = [100.0, 100.0]
    ts_closeds = [
        _BASE_TS + _1D_NS,  # Jan 2024
        _FEB_1_2024 + _1D_NS,  # Feb 2024
    ]
    result = _sharpe_ratio(pnls, ts_closeds)
    assert result is None


def test_sharpe_ratio_with_two_months():
    # Jan: 100 + 200 = 300, Feb: -50 + 150 = 100
    _FEB_1_2024 = 1706745600000000000
    pnls = [100.0, 200.0, -50.0, 150.0]
    ts_closeds = [
        _BASE_TS + _1D_NS,
        _BASE_TS + 2 * _1D_NS,
        _FEB_1_2024 + _1D_NS,
        _FEB_1_2024 + 2 * _1D_NS,
    ]
    result = _sharpe_ratio(pnls, ts_closeds)
    assert result is not None

    monthly_returns = [300.0, 100.0]
    mean = sum(monthly_returns) / 2
    variance = sum((r - mean) ** 2 for r in monthly_returns) / (2 - 1)
    std = math.sqrt(variance)
    expected = round((mean / std) * math.sqrt(12), 2)
    assert result == expected


def test_sharpe_ratio_in_compute_run_metrics():
    # Same data as above: 2-month scenario
    _FEB_1_2024 = 1706745600000000000
    ts_opened = [
        _BASE_TS,
        _BASE_TS + _1D_NS,
        _FEB_1_2024,
        _FEB_1_2024 + _1D_NS,
    ]
    ts_closed = [
        _BASE_TS + _1H_NS,
        _BASE_TS + 2 * _1D_NS,
        _FEB_1_2024 + _1H_NS,
        _FEB_1_2024 + 2 * _1D_NS,
    ]
    table = _make_positions_table(
        [100.0, 200.0, -50.0, 150.0],
        ts_opened=ts_opened,
        ts_closed=ts_closed,
    )
    result = compute_run_metrics(table)
    assert result["sharpe_ratio"] is not None
    assert isinstance(result["sharpe_ratio"], float)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_all_winning_trades_no_avg_loss():
    table = _make_positions_table([100.0, 200.0, 50.0])
    result = compute_run_metrics(table)
    assert result["wins"] == 3
    assert result["losses"] == 0
    assert result["avg_loss"] is None
    assert result["win_loss_ratio"] is None
    assert result["expectancy"] is None


def test_all_losing_trades_no_avg_win():
    table = _make_positions_table([-100.0, -50.0])
    result = compute_run_metrics(table)
    assert result["wins"] == 0
    assert result["losses"] == 2
    assert result["avg_win"] is None
    assert result["win_rate"] == 0.0


def test_single_trade():
    table = _make_positions_table([100.0])
    result = compute_run_metrics(table)
    assert result["total_pnl"] == 100.0
    assert result["wins"] == 1
    assert result["losses"] == 0
    assert result["win_rate"] == 1.0
