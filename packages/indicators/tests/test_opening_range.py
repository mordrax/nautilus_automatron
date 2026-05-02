"""Tests for OpeningRangeDetector — first N minutes high/low
(lifecycle-tracked)."""

from indicators.key_levels.detectors.opening_range import OpeningRangeDetector
from indicators.key_levels.model import OpeningRangeMeta
from tests.helpers.bar_factory import make_bar

_MIN_NS = 60_000_000_000
_DAY_TS = 1_704_067_200_000_000_000  # 2024-01-01 00:00 UTC


def _intraday_bars(open_hour: int = 9, range_minutes: int = 30) -> list:
    """Generate 1-minute bars across a full trading day starting at midnight."""
    bars = []
    for m in range(24 * 60):
        ts = _DAY_TS + m * _MIN_NS
        base = 100.0
        bar_minute = m
        # Make the opening-range window distinct.
        if open_hour * 60 <= bar_minute < (open_hour * 60 + range_minutes):
            spike = 2.0 if bar_minute == open_hour * 60 + 5 else 0.0
        else:
            spike = 0.0
        o = base + spike
        c = base + spike + 0.1
        hi = max(o, c) + 0.2
        lo = min(o, c) - 0.2
        bars.append(make_bar(o, hi, lo, c, ts_ns=ts))
    return bars


def test_no_levels_during_warmup():
    det = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
    )
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_DAY_TS)
    det.update(bar)
    assert det.levels() == []


def test_locks_levels_after_range():
    det = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
    )
    for bar in _intraday_bars():
        det.update(bar)
    levels = det.levels()
    assert len(levels) == 2
    roles = {lv.meta.role for lv in levels}
    assert roles == {"high", "low"}


def test_meta_has_side_and_touch_count():
    det = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
    )
    for bar in _intraday_bars():
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "opening_range"
        assert isinstance(lvl.meta, OpeningRangeMeta)
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)
        assert lvl.meta.range_minutes == 30


def test_new_day_finalizes_levels():
    det = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    # Two consecutive days.
    bars = _intraday_bars()
    day2_start = _DAY_TS + 24 * 60 * _MIN_NS
    for m in range(24 * 60):
        ts = day2_start + m * _MIN_NS
        base = 105.0
        o = base
        c = base + 0.1
        bars.append(make_bar(o, c + 0.2, o - 0.2, c, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    finalized = [lv for lv in levels if lv.end_ts is not None]
    assert len(finalized) >= 2  # day 1's set


def test_break_finalizes_level():
    det = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    bars = _intraday_bars()
    last_ts = bars[-1].ts_event + _MIN_NS
    for i in range(5):
        ts = last_ts + i * _MIN_NS
        bars.append(make_bar(80.0 - i, 81.0 - i, 75.0 - i, 75.0 - i, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized


def test_deterministic():
    bars = _intraday_bars()
    a = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
    )
    b = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
    )
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = OpeningRangeDetector(
        range_minutes=30, market_open_hour_utc=9, atr_period=5,
    )
    for bar in _intraday_bars():
        det.update(bar)
    det.reset()
    assert det.levels() == []
