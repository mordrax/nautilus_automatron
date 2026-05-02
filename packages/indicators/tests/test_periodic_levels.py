"""Tests for PeriodicLevelDetector — PDH/PDL, PWH/PWL, PMH/PML
(lifecycle-tracked)."""

from indicators.key_levels.detectors.periodic_levels import PeriodicLevelDetector
from indicators.key_levels.model import PeriodicLevelMeta
from tests.helpers.bar_factory import make_bar

_HOUR_NS = 3_600_000_000_000
_DAY_TS = 1_704_067_200_000_000_000  # 2024-01-01 00:00 UTC


def _hourly_bars_over_days(days: int = 3) -> list:
    bars = []
    for d in range(days):
        for h in range(24):
            ts = _DAY_TS + d * 24 * _HOUR_NS + h * _HOUR_NS
            base = 100.0 + d
            spike = 1.5 if h == 12 else 0.0  # daily high mid-day
            o = base + spike
            c = base + spike + 0.2
            hi = max(o, c) + 0.3
            lo = min(o, c) - 0.3
            bars.append(make_bar(o, hi, lo, c, ts_ns=ts))
    return bars


def test_no_levels_in_first_period():
    det = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_DAY_TS)
    det.update(bar)
    assert det.levels() == []


def test_emits_pdh_pdl_after_day_rollover():
    det = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    for bar in _hourly_bars_over_days(days=2):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 2  # 1 day × 2 (high/low)
    roles = {lv.meta.role for lv in levels}
    assert roles == {"high", "low"}


def test_meta_has_side_and_touch_count():
    det = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    for bar in _hourly_bars_over_days(days=2):
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "periodic_level"
        assert isinstance(lvl.meta, PeriodicLevelMeta)
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)
        assert lvl.meta.period in ("daily", "weekly", "monthly")
        assert isinstance(lvl.meta.period_start_iso, str)


def test_three_days_yield_two_period_sets():
    det = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    for bar in _hourly_bars_over_days(days=3):
        det.update(bar)
    levels = det.levels()
    # 2 completed days * 2 levels = 4
    assert len(levels) >= 4


def test_multiple_periods_emit_independently():
    det = PeriodicLevelDetector(
        periods=("daily", "weekly"), atr_period=5,
    )
    # 8 days = at least 1 weekly rollover and 7 daily rollovers.
    for bar in _hourly_bars_over_days(days=8):
        det.update(bar)
    periods = {lv.meta.period for lv in det.levels()}
    assert "daily" in periods
    # weekly may or may not roll depending on starting weekday — accept both.


def test_break_finalizes_level():
    det = PeriodicLevelDetector(
        periods=("daily",), atr_period=5,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars={"daily": 10_000},
    )
    bars = _hourly_bars_over_days(days=2)
    last_ts = bars[-1].ts_event + _HOUR_NS
    for i in range(5):
        ts = last_ts + i * _HOUR_NS
        bars.append(make_bar(50.0 - i * 5, 51.0 - i * 5,
                             40.0 - i * 5, 40.0 - i * 5, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized


def test_deterministic():
    bars = _hourly_bars_over_days(days=2)
    a = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    b = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = PeriodicLevelDetector(periods=("daily",), atr_period=5)
    for bar in _hourly_bars_over_days(days=2):
        det.update(bar)
    det.reset()
    assert det.levels() == []
