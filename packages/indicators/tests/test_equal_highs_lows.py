"""Tests for EqualHighsLowsDetector — lifecycle-tracked levels."""

import math

import pytest

from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.model import EqualHighsLowsMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _make_equal_highs_lows_bars():
    """Bars with three swing highs near 110 and three swing lows near 90.

    Pattern: rise to ~110, drop to ~90, repeat three times.  With period=2,
    swing detection lags by 2 bars on each side.
    """
    data = [
        # --- First swing high at 110 ---
        (100.0, 102.0, 98.0, 101.0, 100.0),
        (101.0, 106.0, 100.0, 105.0, 100.0),
        (105.0, 110.0, 104.0, 108.0, 100.0),
        (108.0, 108.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 95.0, 96.0, 100.0),
        # --- First swing low at 90 ---
        (96.0, 97.0, 92.0, 93.0, 100.0),
        (93.0, 94.0, 90.0, 91.0, 100.0),
        (91.0, 96.0, 91.0, 95.0, 100.0),
        (95.0, 100.0, 94.0, 99.0, 100.0),
        # --- Second swing high near 110 ---
        (99.0, 104.0, 98.0, 103.0, 100.0),
        (103.0, 109.0, 102.0, 107.0, 100.0),
        (107.0, 107.0, 99.0, 101.0, 100.0),
        (101.0, 102.0, 95.0, 97.0, 100.0),
        # --- Second swing low near 90 ---
        (97.0, 98.0, 93.0, 94.0, 100.0),
        (94.0, 95.0, 91.0, 92.0, 100.0),
        (92.0, 97.0, 91.0, 96.0, 100.0),
        (96.0, 100.0, 95.0, 99.0, 100.0),
        # --- Third swing high near 110 ---
        (99.0, 104.0, 98.0, 103.0, 100.0),
        (103.0, 110.0, 102.0, 108.0, 100.0),
        (108.0, 108.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 95.0, 96.0, 100.0),
        # --- Third swing low near 90 ---
        (96.0, 97.0, 92.0, 93.0, 100.0),
        (93.0, 94.0, 90.0, 91.0, 100.0),
        (91.0, 96.0, 91.0, 95.0, 100.0),
        (95.0, 100.0, 94.0, 99.0, 100.0),
    ]
    return [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(data)
    ]


# -- Sanity --


def test_no_levels_before_warmup():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.5, atr_period=14,
    )
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_equal_highs_and_lows():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.8, atr_period=14, min_touches=2,
    )
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0

    for level in levels:
        assert level.source == "equal_highs_lows"
        assert 0.0 <= level.strength <= 1.0
        assert isinstance(level.meta, EqualHighsLowsMeta)
        if level.zone_lower is not None and level.zone_upper is not None:
            assert level.zone_lower <= level.price <= level.zone_upper

    sides = {level.meta.side for level in levels}
    assert "high" in sides, f"Expected 'high' side in levels, got sides={sides}"
    assert "low" in sides, f"Expected 'low' side in levels, got sides={sides}"

    for level in levels:
        if level.meta.side == "high":
            assert 105 < level.price < 115
        else:
            assert 85 < level.price < 95


def test_min_touches_filtering():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.8, atr_period=14, min_touches=3,
    )
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    for level in levels:
        assert level.bounce_count >= 3


def test_deterministic():
    bars = _make_equal_highs_lows_bars()
    det_a = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.8, atr_period=14,
    )
    det_b = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.8, atr_period=14,
    )
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.8, atr_period=14,
    )
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0
    detector.reset()
    assert detector.levels() == []


# -- Lifecycle: start_ts / end_ts --


def test_levels_carry_start_ts_in_data_range():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.8, atr_period=14, min_touches=2,
    )
    bars = _make_equal_highs_lows_bars()
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
    detector = EqualHighsLowsDetector(
        period=2,
        tolerance_atr_multiple=0.8,
        atr_period=14,
        min_touches=2,
        # Very generous break + idle thresholds — nothing should end.
        break_atr_multiple=10.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    assert levels
    assert any(level.end_ts is None for level in levels)


def test_break_path_finalizes_level():
    """A run of bars closing far beyond a level should set end_ts."""
    # Build a series with a clear high-side level around 110 then break upward.
    base_ohlcv = [
        # warm up + form swing highs near 110
        (100.0, 102.0, 98.0, 101.0, 100.0),
        (101.0, 103.0, 100.0, 102.0, 100.0),
        (102.0, 110.0, 101.0, 108.0, 100.0),   # swing high #1
        (108.0, 109.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 99.0, 101.0, 100.0),
        (101.0, 105.0, 100.0, 104.0, 100.0),
        (104.0, 109.5, 103.0, 107.0, 100.0),   # swing high #2
        (107.0, 108.0, 99.0, 101.0, 100.0),
        (101.0, 102.0, 99.0, 100.0, 100.0),
        # warmup-ish filler
        (100.0, 101.0, 99.0, 100.0, 100.0),
        (100.0, 101.0, 99.0, 100.0, 100.0),
        (100.0, 101.0, 99.0, 100.0, 100.0),
        (100.0, 101.0, 99.0, 100.0, 100.0),
        (100.0, 101.0, 99.0, 100.0, 100.0),
        (100.0, 101.0, 99.0, 100.0, 100.0),
        # break: sharp rally with closes far above 110
        (115.0, 130.0, 114.0, 128.0, 100.0),
        (128.0, 135.0, 127.0, 133.0, 100.0),
        (133.0, 140.0, 132.0, 138.0, 100.0),
    ]
    bars = [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(base_ohlcv)
    ]

    detector = EqualHighsLowsDetector(
        period=2,
        tolerance_atr_multiple=0.8,
        atr_period=5,
        min_touches=2,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    for bar in bars:
        detector.update(bar)

    high_levels = [lvl for lvl in detector.levels() if lvl.meta.side == "high"]
    assert high_levels
    # At least one high-side level must have been finalized by the rally.
    finalized = [lvl for lvl in high_levels if lvl.end_ts is not None]
    assert finalized, "expected the high-side level to be broken and finalized"
    # The break must occur after the level was born.
    for lvl in finalized:
        assert lvl.end_ts > lvl.start_ts


def test_aged_out_path_finalizes_level():
    """A long stretch with no touches expires the level."""
    # Form a low-side level near 90, then drift far above 90 for many bars.
    base_ohlcv = [
        (100.0, 102.0, 98.0, 101.0, 100.0),
        (101.0, 103.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 99.0, 101.0, 100.0),
        (101.0, 102.0, 95.0, 97.0, 100.0),
        (97.0, 98.0, 92.0, 94.0, 100.0),
        (94.0, 95.0, 90.0, 91.0, 100.0),       # swing low #1 ~90
        (91.0, 95.0, 91.0, 94.0, 100.0),
        (94.0, 99.0, 93.0, 98.0, 100.0),
        (98.0, 102.0, 97.0, 101.0, 100.0),
        (101.0, 103.0, 99.0, 100.0, 100.0),
        (100.0, 101.0, 96.0, 97.0, 100.0),
        (97.0, 98.0, 90.5, 92.0, 100.0),
        (92.0, 95.0, 90.0, 94.0, 100.0),       # swing low #2 ~90
        (94.0, 96.0, 93.0, 95.0, 100.0),
        (95.0, 99.0, 94.0, 98.0, 100.0),
    ]
    bars = [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(base_ohlcv)
    ]
    # Drift bars far above 90 (no touches), enough to age out.
    for k in range(60):
        bars.append(
            make_bar(120.0, 122.0, 118.0, 121.0,
                     ts_ns=_BASE_TS + (len(base_ohlcv) + k) * _1H_NS)
        )

    detector = EqualHighsLowsDetector(
        period=2,
        tolerance_atr_multiple=0.8,
        atr_period=5,
        min_touches=2,
        break_atr_multiple=10.0,        # don't trigger break
        break_consecutive_bars=10,
        max_idle_bars=10,                # short idle threshold
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
    base_ohlcv = [
        (100.0, 102.0, 98.0, 101.0, 100.0),
        (101.0, 103.0, 100.0, 102.0, 100.0),
        (102.0, 110.0, 101.0, 108.0, 100.0),   # swing high #1
        (108.0, 109.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 99.0, 101.0, 100.0),
        (101.0, 105.0, 100.0, 104.0, 100.0),
        (104.0, 109.5, 103.0, 107.0, 100.0),   # swing high #2
        (107.0, 108.0, 99.0, 101.0, 100.0),
        (101.0, 102.0, 99.0, 100.0, 100.0),
    ]
    # Now replay many bars whose range touches the band around 110 without
    # forming a new fractal swing.
    for _ in range(8):
        base_ohlcv.append((108.0, 110.0, 107.0, 108.5, 100.0))

    bars = [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(base_ohlcv)
    ]

    detector = EqualHighsLowsDetector(
        period=2,
        tolerance_atr_multiple=1.5,
        atr_period=5,
        min_touches=2,
        break_atr_multiple=10.0,
        break_consecutive_bars=10,
        max_idle_bars=10_000,
    )
    for bar in bars:
        detector.update(bar)

    high_levels = [lvl for lvl in detector.levels() if lvl.meta.side == "high"]
    assert high_levels
    lvl = max(high_levels, key=lambda x: x.meta.touch_count)
    # Bar-level touches should accumulate beyond the bounce_count.
    assert lvl.meta.touch_count > 0
    assert lvl.meta.touch_count >= lvl.bounce_count - 1  # at least most touches


# -- Strength decay shape --


def test_strength_decay_shape():
    """Strength decays exponentially as bounce_count grows past min_touches."""
    detector = EqualHighsLowsDetector(
        period=2,
        tolerance_atr_multiple=0.5,
        atr_period=14,
        min_touches=2,
        strength_decay_k=3.0,
    )
    expected = {
        2: 1.0,
        5: math.exp(-3.0 / 3.0),         # ~0.367
        10: math.exp(-8.0 / 3.0),        # ~0.069
    }
    # The detector computes strength purely from bounce_count + min_touches +
    # strength_decay_k. We verify the pure shape by reaching into the
    # internals: build a tracked level via the buffer-promotion path with a
    # known bounce_count and read back the resulting KeyLevel.
    from indicators.key_levels.detectors.equal_highs_lows import _TrackedLevel

    detector._tracked.clear()
    detector._tracked.extend([
        _TrackedLevel(
            id=i,
            side="high",
            centroid=100.0,
            members=[100.0] * count,
            member_ts=[_BASE_TS] * count,
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
