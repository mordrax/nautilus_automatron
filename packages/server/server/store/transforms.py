"""Pure functions for transforming raw Arrow data into API-ready dicts.

All functions take Arrow tables or lists of dicts and return plain Python
structures suitable for JSON serialization.
"""

from datetime import datetime, timezone

import pyarrow as pa


def _ns_to_iso(ns: int) -> str:
    """Convert nanosecond timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


def fills_table_to_dicts(table: pa.Table) -> list[dict]:
    """Convert order_filled Arrow table to list of dicts."""
    df = table.to_pandas()
    return [
        {
            "client_order_id": row["client_order_id"],
            "venue_order_id": row["venue_order_id"],
            "trade_id": row["trade_id"],
            "position_id": row["position_id"],
            "instrument_id": row["instrument_id"],
            "order_side": row["order_side"],
            "order_type": row["order_type"],
            "last_qty": row["last_qty"],
            "last_px": row["last_px"],
            "currency": row["currency"],
            "commission": row["commission"],
            "ts_event": _ns_to_iso(row["ts_event"]),
        }
        for _, row in df.iterrows()
    ]


def positions_closed_to_dicts(table: pa.Table) -> list[dict]:
    """Convert position_closed Arrow table to list of dicts."""
    df = table.to_pandas()
    return [
        {
            "position_id": row["position_id"],
            "instrument_id": row["instrument_id"],
            "strategy_id": row["strategy_id"],
            "entry": row["entry"],
            "side": row["side"],
            "quantity": row["quantity"],
            "peak_qty": row["peak_qty"],
            "avg_px_open": row["avg_px_open"],
            "avg_px_close": row["avg_px_close"],
            "realized_return": row["realized_return"],
            "realized_pnl": row["realized_pnl"],
            "currency": row["currency"],
            "ts_opened": _ns_to_iso(row["ts_opened"]),
            "ts_closed": _ns_to_iso(row["ts_closed"]),
            "duration_ns": int(row["duration_ns"]),
        }
        for _, row in df.iterrows()
    ]


def fills_to_trades(fills: list[dict]) -> list[dict]:
    """Group fills by position_id into entry/exit trade pairs.

    Each trade has an entry fill and an exit fill, with computed P&L.
    """
    from collections import defaultdict

    by_position: dict[str, list[dict]] = defaultdict(list)
    for fill in fills:
        by_position[fill["position_id"]].append(fill)

    trades = []
    for idx, (position_id, position_fills) in enumerate(
        sorted(by_position.items())
    ):
        sorted_fills = sorted(position_fills, key=lambda f: f["ts_event"])
        if len(sorted_fills) < 2:
            continue

        entry = sorted_fills[0]
        exit_ = sorted_fills[-1]

        entry_px = float(entry["last_px"])
        exit_px = float(exit_["last_px"])
        qty = float(entry["last_qty"])

        is_long = entry["order_side"] == "BUY"
        pnl = (exit_px - entry_px) * qty if is_long else (entry_px - exit_px) * qty

        trades.append(
            {
                "relative_id": idx + 1,
                "position_id": position_id,
                "instrument_id": entry["instrument_id"],
                "direction": "Long" if is_long else "Short",
                "entry_datetime": entry["ts_event"],
                "entry_price": entry_px,
                "exit_datetime": exit_["ts_event"],
                "exit_price": exit_px,
                "quantity": qty,
                "pnl": round(pnl, 2),
                "currency": entry["currency"],
            }
        )

    return trades


def _safe_float(val: float) -> float | None:
    """Convert NaN to None for JSON safety."""
    import math
    return None if (isinstance(val, float) and math.isnan(val)) else val


def account_states_to_dicts(table: pa.Table) -> list[dict]:
    """Convert account_state Arrow table to list of dicts, skipping NaN rows."""
    df = table.to_pandas()
    results = []
    for _, row in df.iterrows():
        total = _safe_float(row["balance_total"])
        if total is None:
            continue  # Skip margin-only rows without balance data
        results.append({
            "ts_event": _ns_to_iso(row["ts_event"]),
            "balance_total": total,
            "balance_free": _safe_float(row["balance_free"]),
            "balance_locked": _safe_float(row["balance_locked"]),
            "currency": row["balance_currency"],
        })
    return results


def account_states_to_equity(states: list[dict]) -> list[dict]:
    """Convert account states to an equity curve."""
    return [
        {"timestamp": s["ts_event"], "equity": s["balance_total"]}
        for s in states
        if s["balance_total"] is not None
    ]


def bars_to_ohlc(bars: list) -> dict:
    """Convert deserialized Nautilus Bar objects to columnar OHLC dict.

    Args:
        bars: List of nautilus_trader.model.data.Bar objects

    Returns:
        Dict with keys: datetime, open, high, low, close, volume
    """
    return {
        "datetime": [_ns_to_iso(b.ts_event) for b in bars],
        "open": [float(b.open) for b in bars],
        "high": [float(b.high) for b in bars],
        "low": [float(b.low) for b in bars],
        "close": [float(b.close) for b in bars],
        "volume": [float(b.volume) for b in bars],
    }


def run_summary(
    run_id: str,
    config: dict,
    positions_count: int,
    fills_count: int,
    positions_opened: "pa.Table | None" = None,
    positions_closed: "pa.Table | None" = None,
) -> dict:
    """Build a run summary dict from config and counts."""
    from server.store.metrics import compute_run_metrics, empty_metrics

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
        metrics = empty_metrics()

    summary.update(metrics)
    return summary


def _extract_strategy_name(config: dict, positions_opened: "pa.Table | None") -> str:
    """Extract strategy name from position data, falling back to config."""
    if positions_opened is not None and len(positions_opened) > 0:
        if "strategy_id" in positions_opened.column_names:
            return positions_opened.column("strategy_id")[0].as_py()

    strategies = config.get("strategies", [])
    if strategies:
        return strategies[0].get("strategy_path", "Unknown")

    return "Unknown"
