"""Tests for WickRejectionDetector — lifecycle-tracked levels."""

import math

import pytest

from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from indicators.key_levels.model import WickRejectionMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_warmup_bars(count: int = 14) -> list:
    """Normal bars around 100 for ATR warmup (no significant wicks)."""
    bars = []
    for i in range(count):
        open_ = 100.0 + (i % 3) * 0.5
        close = open_ + 0.5
        high = max(open_, close) + 0.3
        low = min(open_, close) - 0.3
        bars.append(make_bar(open_, high, low, close, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def _make_lower_wick_bar(price_level: float, bar_index: int):
    """Bar with a long lower wick reaching down to `price_level`."""
    open_ = price_level + 8.0
    close = price_level + 9.0  # body of 1.0 near the top
    high = close + 0.5         # tiny upper wick
    low = price_level          # long lower wick = 8.0 → ratio 8.0
    return make_bar(open_, high, low, close, ts_ns=_BASE_TS + bar_index * _1H_NS)


def _make_upper_wick_bar(price_level: float, bar_index: int):
    """Bar with a long upper wick reaching up to `price_level`."""
    close = price_level - 8.0
    open_ = price_level - 9.0  # body of 1.0 near the bottom
    low = open_ - 0.5          # tiny lower wick
    high = price_level         # long upper wick = 8.0 → ratio 8.0
    return make_bar(open_, high, low, close, ts_ns=_BASE_TS + bar_index * _1H_NS)


def _make_normal_bar(bar_index: int):
    """Bar around 100 with no significant wicks."""
    return make_bar(99.5, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + bar_index * _1H_NS)


def _make_test_bars():
    """Warmup, then 3 lower-wick rejections near 90 and 3 upper-wick near 110."""
    bars = _make_warmup_bars(14)
    idx = 14

    for i in range(3):
        bars.append(_make_lower_wick_bar(90.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    for i in range(3):
        bars.append(_make_upper_wick_bar(110.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    return bars


# -- Sanity --


def test_no_levels_before_atr_ready():
    detector = WickRejectionDetector(atr_period=14, min_rejections=2)
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_wick_rejection_zones():
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=2,
        # Don't end levels via break/age-out for this test.
        break_atr_multiple=20.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0, "Expected at least one wick rejection level"

    for level in levels:
        assert level.source == "wick_rejection"
        assert 0.0 <= level.strength <= 1.0
        assert isinstance(level.meta, WickRejectionMeta)
        assert level.meta.rejection_count >= 2
        assert level.meta.avg_wick_ratio > 0.0
        assert level.meta.side in ("high", "low")
        if level.zone_lower is not None and level.zone_upper is not None:
            assert level.zone_lower <= level.price <= level.zone_upper

    sides = {level.meta.side for level in levels}
    assert "high" in sides, f"Expected 'high' side, got sides={sides}"
    assert "low" in sides, f"Expected 'low' side, got sides={sides}"

    for level in levels:
        if level.meta.side == "high":
            assert 105 < level.price < 115
        else:
            assert 85 < level.price < 95


def test_min_rejections_filtering():
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=3,
        break_atr_multiple=20.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    for level in levels:
        assert level.bounce_count >= 3


def test_deterministic():
    bars = _make_test_bars()
    det_a = WickRejectionDetector(
        min_wick_ratio=2.0, zone_atr_multiple=2.0, atr_period=14, min_rejections=2,
    )
    det_b = WickRejectionDetector(
        min_wick_ratio=2.0, zone_atr_multiple=2.0, atr_period=14, min_rejections=2,
    )
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=2,
        break_atr_multiple=20.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0
    detector.reset()
    assert detector.levels() == []


# -- Lifecycle: start_ts / end_ts --


def test_levels_carry_start_ts_in_data_range():
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=2,
        break_atr_multiple=20.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    assert levels
    first_ts = bars[0].ts_event
    last_ts = bars[-1].ts_event
    for level in levels:
        assert first_ts <= level.start_ts <= last_ts
        if level.end_ts is not None:
            assert level.start_ts <= level.end_ts <= last_ts


def test_active_levels_have_no_end_ts():
    """A level that is never broken or aged out keeps end_ts == None."""
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=2,
        break_atr_multiple=20.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    assert levels
    assert any(level.end_ts is None for level in levels)


def test_break_path_finalizes_level():
    """A run of bars closing far beyond a level should set end_ts."""
    bars = _make_warmup_bars(14)
    idx = 14

    # Form a high-side wick-rejection level at ~110.
    for i in range(3):
        bars.append(_make_upper_wick_bar(110.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    # Sharp rally with closes far above 110 — should break the high-side level.
    rally = [
        (115.0, 130.0, 114.0, 128.0),
        (128.0, 135.0, 127.0, 133.0),
        (133.0, 140.0, 132.0, 138.0),
    ]
    for o, h, lo, c in rally:
        bars.append(make_bar(o, h, lo, c, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=5,
        min_rejections=2,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        detector.update(bar)

    high_levels = [lvl for lvl in detector.levels() if lvl.meta.side == "high"]
    assert high_levels
    finalized = [lvl for lvl in high_levels if lvl.end_ts is not None]
    assert finalized, "expected the high-side level to be broken and finalized"
    for lvl in finalized:
        assert lvl.end_ts > lvl.start_ts


def test_aged_out_path_finalizes_level():
    """A long stretch with no touches expires the level."""
    bars = _make_warmup_bars(14)
    idx = 14

    # Form a low-side wick-rejection level at ~90.
    for i in range(3):
        bars.append(_make_lower_wick_bar(90.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    # Drift far above 90 (no touches) for many bars — must age out.
    for _ in range(60):
        bars.append(make_bar(120.0, 122.0, 118.0, 121.0,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=5,
        min_rejections=2,
        break_atr_multiple=20.0,         # don't trigger break
        break_consecutive_bars=10,
        max_idle_bars=10,                 # short idle threshold
    )
    for bar in bars:
        detector.update(bar)

    low_levels = [lvl for lvl in detector.levels() if lvl.meta.side == "low"]
    assert low_levels
    aged_out = [lvl for lvl in low_levels if lvl.end_ts is not None]
    assert aged_out, "expected the low-side level to age out"


# -- bounce_count vs touch_count --


def test_touch_count_increments_separately_from_bounce_count():
    """Bar-level touches grow touch_count without changing bounce_count."""
    bars = _make_warmup_bars(14)
    idx = 14

    # Form a high-side level at ~110 from 2 upper-wick rejections.
    for i in range(2):
        bars.append(_make_upper_wick_bar(110.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    # Many bars that simply revisit the band around 110 with no rejection-class
    # wick — these should add touches but not bounces.
    for _ in range(8):
        bars.append(make_bar(108.5, 110.0, 107.5, 109.0,
                             ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=5,
        min_rejections=2,
        break_atr_multiple=20.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    for bar in bars:
        detector.update(bar)

    high_levels = [lvl for lvl in detector.levels() if lvl.meta.side == "high"]
    assert high_levels
    lvl = max(high_levels, key=lambda x: x.meta.touch_count)
    assert lvl.meta.touch_count > 0
    # touch_count is a separate counter — it can exceed bounce_count.
    assert lvl.meta.touch_count >= lvl.bounce_count - 1


# -- Strength decay shape --


def test_strength_decay_shape():
    """Strength decays exponentially as bounce_count grows past min_rejections."""
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=2,
        strength_decay_k=3.0,
    )
    expected = {
        2: 1.0,
        5: math.exp(-3.0 / 3.0),
        10: math.exp(-8.0 / 3.0),
    }

    from indicators.key_levels.detectors.wick_rejection import _TrackedLevel

    detector._tracked.clear()
    detector._tracked.extend([
        _TrackedLevel(
            id=i,
            side="high",
            centroid=100.0,
            members=[100.0] * count,
            member_ts=[_BASE_TS] * count,
            member_ratios=[2.0] * count,
            start_ts=_BASE_TS,
            end_ts=None,
            bounce_count=count,
            touch_count=0,
            last_touch_ts=_BASE_TS,
        )
        for i, count in enumerate(expected)
    ])

    levels = detector.levels()
    by_count = {lvl.bounce_count: lvl.strength for lvl in levels}
    assert by_count[2] == pytest.approx(expected[2], abs=1e-6)
    assert by_count[5] == pytest.approx(expected[5], abs=1e-2)
    assert by_count[10] == pytest.approx(expected[10], abs=1e-2)
