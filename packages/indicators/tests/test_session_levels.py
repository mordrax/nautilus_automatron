"""Tests for SessionLevelDetector — Asian/London/NY session H/L
(lifecycle-tracked)."""

from indicators.key_levels.detectors.session_levels import SessionLevelDetector
from indicators.key_levels.model import SessionLevelMeta
from tests.helpers.bar_factory import make_bar

_HOUR_NS = 3_600_000_000_000
# 2024-01-01 00:00 UTC
_DAY_TS = 1_704_067_200_000_000_000


def _multi_session_bars(days: int = 2) -> list:
    """24 hourly bars per day, two days. Session highs/lows differ per day."""
    bars = []
    for d in range(days):
        for h in range(24):
            ts = _DAY_TS + d * 24 * _HOUR_NS + h * _HOUR_NS
            # Vary price within session windows so each session has a distinct
            # H/L.
            base = 100.0 + d
            spike = 0.0
            if 0 <= h < 8:  # asian
                spike = 1.0 if h == 4 else 0.0
            elif 7 <= h < 16:  # london
                spike = 2.0 if h == 11 else 0.0
            elif 12 <= h < 21:  # new_york
                spike = 3.0 if h == 17 else 0.0
            o = base + spike
            c = base + spike + 0.2
            hi = max(o, c) + 0.3
            lo = min(o, c) - 0.3
            bars.append(make_bar(o, hi, lo, c, ts_ns=ts))
    return bars


def test_no_levels_until_session_ends():
    det = SessionLevelDetector(atr_period=5)
    # First bar at midnight — asian session starts.
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_DAY_TS)
    det.update(bar)
    assert det.levels() == []


def test_emits_levels_at_session_end():
    det = SessionLevelDetector(atr_period=5)
    for bar in _multi_session_bars(days=1):
        det.update(bar)
    levels = det.levels()
    # At least: end of asian (hour 8 onward) + end of london (16+) — two
    # sessions × 2 levels = 4. NY may still be active by hour 23.
    assert len(levels) >= 4
    sessions = {lv.meta.session for lv in levels}
    assert "asian" in sessions
    assert "london" in sessions


def test_meta_has_side_and_touch_count():
    det = SessionLevelDetector(atr_period=5)
    for bar in _multi_session_bars(days=1):
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "session_level"
        assert isinstance(lvl.meta, SessionLevelMeta)
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)
        assert lvl.meta.role in ("high", "low")
        assert isinstance(lvl.meta.session_date_iso, str)


def test_two_days_emit_more_levels():
    det = SessionLevelDetector(atr_period=5)
    for bar in _multi_session_bars(days=2):
        det.update(bar)
    levels = det.levels()
    # Two days × 3 sessions × 2 (high/low) = 12 in steady state. The very last
    # NY session may still be active.
    assert len(levels) >= 8


def test_break_finalizes_level():
    """A massive crash after sessions form should break low-side levels."""
    det = SessionLevelDetector(
        atr_period=5,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    bars = _multi_session_bars(days=1)
    last_ts = bars[-1].ts_event + _HOUR_NS
    for i in range(5):
        ts = last_ts + i * _HOUR_NS
        bars.append(make_bar(50.0 - i * 5, 51.0 - i * 5,
                             40.0 - i * 5, 40.0 - i * 5, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected at least one level to break"


def test_deterministic():
    bars = _multi_session_bars(days=1)
    a = SessionLevelDetector(atr_period=5)
    b = SessionLevelDetector(atr_period=5)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = SessionLevelDetector(atr_period=5)
    for bar in _multi_session_bars(days=1):
        det.update(bar)
    det.reset()
    assert det.levels() == []
