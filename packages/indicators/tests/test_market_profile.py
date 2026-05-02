"""Tests for MarketProfileDetector — TPO POC/VAH/VAL (lifecycle-tracked)."""

from indicators.key_levels.detectors.market_profile import MarketProfileDetector
from indicators.key_levels.model import MarketProfileMeta
from tests.helpers.bar_factory import make_bar

_MIN_NS = 60_000_000_000
_DAY_TS = 1_704_067_200_000_000_000


def _intraday_bars(days: int = 2) -> list:
    """30-minute bars over `days` days, prices oscillating around 100."""
    bars = []
    bars_per_day = 48
    for d in range(days):
        for s in range(bars_per_day):
            ts = _DAY_TS + d * 24 * 60 * _MIN_NS + s * 30 * _MIN_NS
            center = 100.0 + d + (s % 5 - 2) * 0.4
            o = center
            c = center + 0.2
            hi = max(o, c) + 0.5
            lo = min(o, c) - 0.5
            bars.append(make_bar(o, hi, lo, c, ts_ns=ts))
    return bars


def test_no_levels_during_first_day():
    det = MarketProfileDetector(slice_minutes=30, atr_period=5)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_DAY_TS)
    det.update(bar)
    assert det.levels() == []


def test_emits_levels_after_session_rolls():
    det = MarketProfileDetector(slice_minutes=30, atr_period=5)
    for bar in _intraday_bars(days=2):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 3  # 1 finalized session × 3 (poc/vah/val)
    roles = {lv.meta.role for lv in levels}
    assert "poc" in roles
    assert "vah" in roles
    assert "val" in roles


def test_meta_has_side_and_touch_count():
    det = MarketProfileDetector(slice_minutes=30, atr_period=5)
    for bar in _intraday_bars(days=2):
        det.update(bar)
    for lvl in det.levels():
        assert lvl.source == "market_profile_tpo"
        assert isinstance(lvl.meta, MarketProfileMeta)
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)
        assert lvl.meta.role in ("poc", "vah", "val")
        assert lvl.meta.tpo_count > 0
        assert lvl.meta.total_tpo_periods > 0


def test_two_sessions_emit_two_sets():
    det = MarketProfileDetector(
        slice_minutes=30, atr_period=5,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _intraday_bars(days=3):
        det.update(bar)
    levels = det.levels()
    # 2 finalized sessions × 3 = 6
    assert len(levels) >= 6


def test_break_finalizes_level():
    det = MarketProfileDetector(
        slice_minutes=30, atr_period=5,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    bars = _intraday_bars(days=2)
    last_ts = bars[-1].ts_event + _MIN_NS
    for i in range(8):
        ts = last_ts + i * 30 * _MIN_NS
        bars.append(make_bar(50.0 - i, 51.0 - i, 40.0 - i, 40.0 - i, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized


def test_deterministic():
    bars = _intraday_bars(days=2)
    a = MarketProfileDetector(slice_minutes=30, atr_period=5)
    b = MarketProfileDetector(slice_minutes=30, atr_period=5)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = MarketProfileDetector(slice_minutes=30, atr_period=5)
    for bar in _intraday_bars(days=2):
        det.update(bar)
    det.reset()
    assert det.levels() == []
