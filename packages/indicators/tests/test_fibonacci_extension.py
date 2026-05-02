"""Tests for FibonacciExtensionDetector — lifecycle-tracked Fib fans."""

from __future__ import annotations

from indicators.key_levels.detectors.fibonacci import (
    EXTENSION_RATIOS,
    FibonacciExtensionDetector,
)
from indicators.key_levels.model import FibonacciMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_abc_uptrend_bars(
    swing_period: int = 5,
    atr_period: int = 14,
) -> list:
    """Build bars that produce A=90(low), B=110(high), C=95(low)."""
    bars = []
    ts = _BASE_TS

    def _add(o: float, h: float, lo: float, c: float) -> None:
        nonlocal ts
        bars.append(make_bar(o, h, lo, c, ts_ns=ts))
        ts += _1H_NS

    for i in range(atr_period):
        base = 100.0 + (i % 2) * 0.5
        _add(base, base + 1.0, base - 1.0, base)

    for i in range(swing_period):
        price = 98.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)
    _add(91.0, 91.5, 90.0, 91.0)
    for i in range(swing_period):
        price = 93.0 + i * 2.0
        _add(price, price + 0.5, price - 1.0, price)

    for i in range(swing_period):
        price = 103.0 + i * 1.5
        _add(price, price + 0.5, price - 1.0, price)
    _add(109.0, 110.0, 108.5, 109.0)
    for i in range(swing_period):
        price = 108.0 - i * 1.5
        _add(price, price + 0.5, price - 1.0, price)

    for i in range(swing_period):
        price = 101.0 - i * 1.0
        _add(price, price + 0.5, price - 0.5, price)
    _add(96.0, 96.5, 95.0, 96.0)
    for i in range(swing_period):
        price = 97.0 + i * 1.5
        _add(price, price + 0.5, price - 0.5, price)

    return bars


def test_no_levels_initially() -> None:
    det = FibonacciExtensionDetector(swing_period=5, atr_period=14)
    for i in range(10):
        bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS)
        det.update(bar)
    assert det.levels() == []


def test_emits_full_fan_after_abc() -> None:
    det = FibonacciExtensionDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in _make_abc_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    levels = det.levels()
    assert len(levels) == len(EXTENSION_RATIOS)
    ratios = {lvl.meta.ratio for lvl in levels}
    assert ratios == set(EXTENSION_RATIOS)


def test_source_and_meta_types() -> None:
    det = FibonacciExtensionDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in _make_abc_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "fib_extension"
        assert isinstance(lvl.meta, FibonacciMeta)
        assert lvl.meta.direction == "extension"
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)


def test_active_levels_have_no_end_ts() -> None:
    det = FibonacciExtensionDetector(
        swing_period=5,
        min_swing_atr_multiple=0.5,
        atr_period=14,
        break_atr_multiple=100.0,
        break_consecutive_bars=100,
        max_idle_bars=10_000,
    )
    for bar in _make_abc_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is None for lv in levels)


def test_break_path_finalizes_level() -> None:
    """Sustained close beyond extension levels finalizes them."""
    bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
    idx = len(bars)
    # Extensions in uptrend project upward beyond C; rally past them.
    for p in [120.0, 130.0, 145.0, 160.0]:
        ts = _BASE_TS + idx * _1H_NS
        bars.append(make_bar(p - 5.0, p + 1.0, p - 6.0, p, ts_ns=ts))
        idx += 1
    det = FibonacciExtensionDetector(
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
    assert finalized, "expected at least one extension level to break"


def test_deterministic() -> None:
    bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
    a = FibonacciExtensionDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    b = FibonacciExtensionDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state() -> None:
    det = FibonacciExtensionDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    for bar in _make_abc_uptrend_bars(swing_period=5, atr_period=14):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []


def test_levels_in_data_range() -> None:
    det = FibonacciExtensionDetector(
        swing_period=5, min_swing_atr_multiple=0.5, atr_period=14,
    )
    bars = _make_abc_uptrend_bars(swing_period=5, atr_period=14)
    for bar in bars:
        det.update(bar)
    first = bars[0].ts_event
    last = bars[-1].ts_event
    for lv in det.levels():
        assert first <= lv.start_ts <= last
        if lv.end_ts is not None:
            assert lv.start_ts <= lv.end_ts <= last
