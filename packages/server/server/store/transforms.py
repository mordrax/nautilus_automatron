"""Pure functions for transforming NautilusTrader objects into API-ready dicts.

All functions take deserialized Nautilus objects or lists of dicts and return
plain Python structures suitable for JSON serialization.
"""

from datetime import datetime, timezone


def _ns_to_iso(ns: int) -> str:
    """Convert nanosecond timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


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
