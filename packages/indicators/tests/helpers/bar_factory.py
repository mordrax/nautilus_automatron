"""Test utility for creating NautilusTrader Bar objects from raw floats.

NautilusTrader Bar objects require BarType, Price, and Quantity wrapper types.
This factory abstracts that away so tests can work with plain numbers.
"""

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.objects import Price, Quantity

# Default bar type used across all tests — a 1-minute bid bar on a simulated venue.
DEFAULT_BAR_TYPE = BarType.from_str("TEST.SIM-1-MINUTE-BID-EXTERNAL")

# 1 hour in nanoseconds — used to space bars apart in time.
_1H_NS = 3_600_000_000_000

# Base timestamp: 2024-01-01 00:00:00 UTC in nanoseconds.
_BASE_TS = 1_704_067_200_000_000_000


def make_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
    ts_ns: int = _BASE_TS,
    bar_type: BarType = DEFAULT_BAR_TYPE,
) -> Bar:
    """Create a NautilusTrader Bar from raw floats."""
    return Bar(
        bar_type=bar_type,
        open=Price.from_str(f"{open_:.5f}"),
        high=Price.from_str(f"{high:.5f}"),
        low=Price.from_str(f"{low:.5f}"),
        close=Price.from_str(f"{close:.5f}"),
        volume=Quantity.from_str(f"{volume:.2f}"),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


def make_bars_from_ohlcv(
    data: list[tuple[float, float, float, float, float]],
    start_ts: int = _BASE_TS,
    interval_ns: int = _1H_NS,
    bar_type: BarType = DEFAULT_BAR_TYPE,
) -> list[Bar]:
    """Create a list of Bars from OHLCV tuples."""
    return [
        make_bar(o, h, lo, c, v, ts_ns=start_ts + i * interval_ns, bar_type=bar_type)
        for i, (o, h, lo, c, v) in enumerate(data)
    ]


def make_bars_from_closes(
    closes: list[float],
    spread: float = 0.5,
    volume: float = 100.0,
    start_ts: int = _BASE_TS,
    interval_ns: int = _1H_NS,
    bar_type: BarType = DEFAULT_BAR_TYPE,
) -> list[Bar]:
    """Create Bars from a list of close prices with synthetic OHLV."""
    bars: list[Bar] = []
    for i, close in enumerate(closes):
        open_ = closes[i - 1] if i > 0 else close
        high = max(open_, close) + spread
        low = min(open_, close) - spread
        bars.append(
            make_bar(
                open_=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                ts_ns=start_ts + i * interval_ns,
                bar_type=bar_type,
            )
        )
    return bars
