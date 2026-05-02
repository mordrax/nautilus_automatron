"""Tests for VolumeDistributionDetector — context-aware POC levels."""

from indicators.key_levels.detectors.volume_distribution import (
    VolumeDistributionDetector,
)
from indicators.key_levels.model import VolumeDistributionMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_swing_bars(swing_count: int = 4, period: int = 5) -> list:
    """Build OHLCV bars with `swing_count` alternating fractal swings.

    Each swing is a peak/trough confirmed by `period` bars on each side.
    Volume is held constant at 100 for the histogram math.
    """
    bars: list = []
    centers = [100.0, 110.0, 95.0, 115.0, 90.0, 120.0, 88.0, 122.0]
    centers = centers[:swing_count]

    idx = 0
    base = 100.0
    # Each segment: ramp up to center, hold one bar, ramp down.
    for c_i, target in enumerate(centers):
        going_up = target > base
        # `period` ramp bars
        for j in range(period):
            frac = (j + 1) / (period + 1)
            price = base + (target - base) * frac
            o = price - 0.3
            cl = price + 0.3
            h = max(o, cl) + 0.5
            lo = min(o, cl) - 0.5
            bars.append(make_bar(o, h, lo, cl,
                                 volume=100.0, ts_ns=_BASE_TS + idx * _1H_NS))
            idx += 1
        # Center fractal bar
        if going_up:
            bars.append(make_bar(target - 0.3, target + 1.0, target - 0.5, target,
                                 volume=120.0, ts_ns=_BASE_TS + idx * _1H_NS))
        else:
            bars.append(make_bar(target + 0.3, target + 0.5, target - 1.0, target,
                                 volume=120.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
        base = target

    # Trailing bars so last fractal can confirm.
    final = base
    for j in range(period):
        price = final + (-1 if centers[-1] > centers[-2] else 1) * (j + 1) * 0.5
        o = price - 0.3
        cl = price + 0.3
        h = max(o, cl) + 0.5
        lo = min(o, cl) - 0.5
        bars.append(make_bar(o, h, lo, cl,
                             volume=100.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    return bars


def test_no_levels_before_atr_ready():
    det = VolumeDistributionDetector(swing_period=5, atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_levels_emit_after_two_swings():
    det = VolumeDistributionDetector(
        swing_period=5,
        min_context_bars=4,
        atr_period=10,
    )
    for bar in _make_swing_bars(swing_count=4, period=5):
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1


def test_source_and_meta_types():
    det = VolumeDistributionDetector(
        swing_period=5, min_context_bars=4, atr_period=10,
    )
    for bar in _make_swing_bars(swing_count=4, period=5):
        det.update(bar)
    for level in det.levels():
        assert level.source == "volume_distribution"
        assert isinstance(level.meta, VolumeDistributionMeta)
        assert level.meta.context in ("consolidation", "peak", "trough", "range")
        assert level.meta.context_bar_count > 0
        assert 0.0 <= level.meta.volume_concentration <= 1.0
        assert level.meta.side in ("high", "low")
        assert isinstance(level.meta.touch_count, int)


def test_active_levels_have_no_end_ts():
    det = VolumeDistributionDetector(
        swing_period=5, min_context_bars=4, atr_period=10,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _make_swing_bars(swing_count=4, period=5):
        det.update(bar)
    assert any(lv.end_ts is None for lv in det.levels())


def test_break_finalizes_level():
    bars = _make_swing_bars(swing_count=4, period=5)
    last_ts = bars[-1].ts_event
    # Append a sustained crash below all levels.
    for i in range(5):
        ts = last_ts + (i + 1) * _1H_NS
        bars.append(make_bar(50, 52, 40, 41, volume=100.0, ts_ns=ts))
    det = VolumeDistributionDetector(
        swing_period=5, min_context_bars=4, atr_period=10,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        det.update(bar)
    finalized = [lv for lv in det.levels() if lv.end_ts is not None]
    assert finalized, "expected at least one level to break and finalize"


def test_deterministic():
    bars = _make_swing_bars(swing_count=4, period=5)
    a = VolumeDistributionDetector(
        swing_period=5, min_context_bars=4, atr_period=10,
    )
    b = VolumeDistributionDetector(
        swing_period=5, min_context_bars=4, atr_period=10,
    )
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = VolumeDistributionDetector(
        swing_period=5, min_context_bars=4, atr_period=10,
    )
    for bar in _make_swing_bars(swing_count=4, period=5):
        det.update(bar)
    assert len(det.levels()) > 0
    det.reset()
    assert det.levels() == []
