"""Tests for FibonacciRetracementDetector — lifecycle-tracked Fib fans."""

from __future__ import annotations

from indicators.key_levels.detectors.fibonacci import (
    RETRACEMENT_RATIOS,
    FibonacciRetracementDetector,
)
from indicators.key_levels.model import FibonacciMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_uptrend_bars(
    swing_period: int = 5,
    atr_period: int = 14,
) -> list:
    """Build bars that produce a swing low at 90 then a swing high at 110."""
    bars = []
    ts = _BASE_TS

    def _add(o: float, h: float, lo: float, c: float) -> None:
        nonlocal ts
        bars.append(make_bar(o, h, lo, c, ts_ns=ts))
        ts += _1H_NS

    # Warmup oscillating around 100.
    for i in range(atr_period):
        base = 100.0 + (i % 2) * 0.5
        _add(base, base + 1.0, base - 1.0, base)

    # Descend to swing low at 90.
    for i in range(swing_period):
        price = 98.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)
    _add(91.0, 91.5, 90.0, 91.0)
    for i in range(swing_period):
        price = 93.0 + i * 2.0
        _add(price, price + 0.5, price - 1.0, price)

    # Ascend to swing high at 110.
    for i in range(swing_period):
        price = 103.0 + i * 1.5
        _add(price, price + 0.5, price - 1.0, price)
    _add(109.0, 110.0, 108.5, 109.0)
    for i in range(swing_period):
        price = 108.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    return bars


def test_no_levels_initially() -> None:
    det = FibonacciRetracementDetector(swing_period=5, atr_period=14)
    for i in range(10):
        bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS)
        det.update(bar)
    assert det.levels() == []


def test_emits_full_fan_after_swings() -> None:
    det = FibonacciRetracementDetector(
        swing_period=5,
        min_swing_atr_multiple=0.5,
        atr_period=14,
    )
    for bar in _make_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    levels = det.levels()
    # 5 retracement ratios -> 5 levels (single fan).
    assert len(levels) == len(RETRACEMENT_RATIOS)
    ratios = {lvl.meta.ratio for lvl in levels}
    assert ratios == set(RETRACEMENT_RATIOS)


def test_source_and_meta_types() -> None:
    det = FibonacciRetracementDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in _make_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "fib_retracement"
        assert isinstance(lvl.meta, FibonacciMeta)
        assert lvl.meta.direction == "retracement"
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)


def test_active_levels_have_no_end_ts() -> None:
    det = FibonacciRetracementDetector(
        swing_period=5,
        min_swing_atr_multiple=0.5,
        atr_period=14,
        break_atr_multiple=100.0,
        break_consecutive_bars=100,
        max_idle_bars=10_000,
    )
    for bar in _make_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_break_path_finalizes_level() -> None:
    """A sustained close beyond the fan (a high-side level) should break it."""
    bars = _make_uptrend_bars(swing_period=5, atr_period=14)
    idx = len(bars)
    # In an uptrend, the fan sits between 90 and 110, with side="low" — break
    # via a sharp drop below 80.
    for p in [80.0, 70.0, 60.0]:
        ts = _BASE_TS + idx * _1H_NS
        bars.append(make_bar(p + 5.0, p + 6.0, p - 1.0, p, ts_ns=ts))
        idx += 1
    det = FibonacciRetracementDetector(
        swing_period=5,
        min_swing_atr_multiple=0.5,
        atr_period=14,
        break_atr_multiple=0.5,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected at least one Fib level to break and finalize"


def test_deterministic() -> None:
    bars = _make_uptrend_bars(swing_period=5, atr_period=14)
    a = FibonacciRetracementDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    b = FibonacciRetracementDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state() -> None:
    det = FibonacciRetracementDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in _make_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []


def test_levels_in_data_range() -> None:
    det = FibonacciRetracementDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    bars = _make_uptrend_bars(swing_period=5, atr_period=14)
    for bar in bars:
        det.update(bar)
    first = bars[0].ts_event
    last = bars[-1].ts_event
    for lv in det.levels():
        assert first <= lv.start_ts <= last
        if lv.end_ts is not None:
            assert lv.start_ts <= lv.end_ts <= last
