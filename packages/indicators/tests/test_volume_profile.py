"""Tests for VolumeProfileDetector — period-based POC/VAH/VAL levels."""

from indicators.key_levels.detectors.volume_profile import VolumeProfileDetector
from indicators.key_levels.model import VolumeProfileMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _stable_period_bars(count: int = 50, base: float = 100.0) -> list:
    """Bars oscillating tightly around `base` with consistent volume."""
    bars = []
    for i in range(count):
        center = base + (i % 5 - 2) * 0.5
        open_ = center
        close = center + 0.3
        high = max(open_, close) + 0.7
        low = min(open_, close) - 0.7
        bars.append(make_bar(open_, high, low, close,
                             volume=100.0, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def test_no_levels_before_period_closes():
    det = VolumeProfileDetector(lookback_bars=50, atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_levels_emitted_after_period():
    det = VolumeProfileDetector(lookback_bars=20, atr_period=14)
    for bar in _stable_period_bars(20):
        det.update(bar)
    levels = det.levels()
    assert len(levels) == 3
    node_types = {lv.meta.node_type for lv in levels}
    assert node_types == {"poc", "va_high", "va_low"}


def test_source_and_meta_types():
    det = VolumeProfileDetector(lookback_bars=20, atr_period=14)
    for bar in _stable_period_bars(20):
        det.update(bar)
    for level in det.levels():
        assert level.source == "volume_profile"
        assert isinstance(level.meta, VolumeProfileMeta)
        assert level.meta.bin_volume > 0
        assert 0.0 <= level.meta.volume_concentration <= 1.0
        assert level.meta.side in ("high", "low")
        assert isinstance(level.meta.touch_count, int)


def test_period_close_finalizes_previous_levels():
    """When a second period closes, the first period's levels are finalized."""
    bars = _stable_period_bars(40)  # exactly 2 periods of 20
    det = VolumeProfileDetector(
        lookback_bars=20, atr_period=14,
        # Avoid in-period break/age-out interference.
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    # First period's 3 levels should be finalized; second period's still active.
    finalized = [lv for lv in levels if lv.end_ts is not None]
    active = [lv for lv in levels if lv.end_ts is None]
    assert len(finalized) >= 3
    assert len(active) >= 3


def test_break_finalizes_level():
    """A run of bars closing far below a low-side level finalizes it."""
    warmup = _stable_period_bars(20)
    crash = []
    for i in range(5):
        ts = _BASE_TS + (20 + i) * _1H_NS
        # Falling closes well below the period's POC/VAL.
        crash.append(make_bar(80.0 - i * 5, 81.0 - i * 5,
                              70.0 - i * 5, 70.0 - i * 5, volume=100.0, ts_ns=ts))
    det = VolumeProfileDetector(
        lookback_bars=20, atr_period=14,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in warmup + crash:
        det.update(bar)
    levels = det.levels()
    finalized = [lv for lv in levels if lv.end_ts is not None]
    assert finalized, "expected at least one level to break and finalize"


def test_active_levels_have_no_end_ts():
    det = VolumeProfileDetector(
        lookback_bars=20, atr_period=14,
        break_atr_multiple=100.0, max_idle_bars=10_000,
    )
    for bar in _stable_period_bars(20):
        det.update(bar)
    assert any(lv.end_ts is None for lv in det.levels())


def test_deterministic():
    bars = _stable_period_bars(20)
    a = VolumeProfileDetector(lookback_bars=20, atr_period=14)
    b = VolumeProfileDetector(lookback_bars=20, atr_period=14)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = VolumeProfileDetector(lookback_bars=20, atr_period=14)
    for bar in _stable_period_bars(20):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []
