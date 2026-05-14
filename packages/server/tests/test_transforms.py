"""Unit tests for pure transform functions."""

from types import SimpleNamespace

from nautilus_trader.model.enums import OrderSide

from server.store.transforms import positions_to_trades

_BASE_TS = 1_704_067_200_000_000_000  # 2024-01-01 00:00:00 UTC
_1H_NS = 3_600_000_000_000
_1D_NS = 86_400_000_000_000


def _mk_pos(
    *,
    position_id="P-0",
    ts_opened=_BASE_TS,
    ts_closed=_BASE_TS + _1H_NS,
    entry=OrderSide.BUY,
    avg_px_open=100.0,
    avg_px_close=110.0,
    peak_qty=1.0,
    realized_pnl=10.0,
    currency="USD",
    instrument_id="XAUUSD.IBCFD",
):
    return SimpleNamespace(
        position_id=position_id,
        instrument_id=instrument_id,
        entry=entry,
        ts_opened=ts_opened,
        ts_closed=ts_closed,
        avg_px_open=avg_px_open,
        avg_px_close=avg_px_close,
        peak_qty=peak_qty,
        realized_pnl=realized_pnl,
        currency=currency,
    )


def test_positions_to_trades_one_per_closed_position():
    """Three positions sharing one position_id (NETTING-OMS) produce 3 trade rows."""
    positions = [
        _mk_pos(position_id="P-NETTING", ts_opened=_BASE_TS, realized_pnl=10.0),
        _mk_pos(position_id="P-NETTING", ts_opened=_BASE_TS + _1D_NS, realized_pnl=20.0),
        _mk_pos(position_id="P-NETTING", ts_opened=_BASE_TS + 2 * _1D_NS, realized_pnl=30.0),
    ]
    trades = positions_to_trades(positions)
    assert len(trades) == 3
    assert [t["relative_id"] for t in trades] == [1, 2, 3]
    assert [t["pnl"] for t in trades] == [10.0, 20.0, 30.0]


def test_positions_to_trades_unique_position_ids():
    """Three positions with unique position_ids (HEDGING-OMS) produce 3 trade rows."""
    positions = [
        _mk_pos(position_id="P-0", ts_opened=_BASE_TS),
        _mk_pos(position_id="P-1", ts_opened=_BASE_TS + _1D_NS),
        _mk_pos(position_id="P-2", ts_opened=_BASE_TS + 2 * _1D_NS),
    ]
    trades = positions_to_trades(positions)
    assert len(trades) == 3
    assert {t["position_id"] for t in trades} == {"P-0", "P-1", "P-2"}
    assert [t["relative_id"] for t in trades] == [1, 2, 3]


def test_positions_to_trades_sorted_by_ts_opened():
    """Input in order [T+2, T, T+1] produces output sorted ascending with correct relative_ids."""
    positions = [
        _mk_pos(ts_opened=_BASE_TS + 2 * _1D_NS, realized_pnl=30.0),
        _mk_pos(ts_opened=_BASE_TS, realized_pnl=10.0),
        _mk_pos(ts_opened=_BASE_TS + _1D_NS, realized_pnl=20.0),
    ]
    trades = positions_to_trades(positions)
    assert [t["pnl"] for t in trades] == [10.0, 20.0, 30.0]
    assert [t["relative_id"] for t in trades] == [1, 2, 3]


def test_positions_to_trades_direction():
    """entry=OrderSide.BUY → 'Long'; entry=OrderSide.SELL → 'Short'."""
    positions = [
        _mk_pos(position_id="P-buy", ts_opened=_BASE_TS, entry=OrderSide.BUY),
        _mk_pos(position_id="P-sell", ts_opened=_BASE_TS + _1D_NS, entry=OrderSide.SELL),
    ]
    trades = positions_to_trades(positions)
    assert trades[0]["direction"] == "Long"
    assert trades[1]["direction"] == "Short"


def test_positions_to_trades_empty():
    """Empty input returns empty output."""
    assert positions_to_trades([]) == []
