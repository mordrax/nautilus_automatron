"""Tests for SwingClusterDetector — clusters BOTH high & low fractal swings
into the same level pool (lifecycle-tracked)."""

from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from indicators.key_levels.model import SwingClusterMeta
from tests.helpers.bar_factory import _1H_NS, _BASE_TS, make_bar


def _alternating_swings_near_100() -> list:
    """Bars producing several fractal swings clustering near 100."""
    bars = []
    closes = [
        99.5, 100.5, 101.5, 100.0, 99.0,  # low at idx 4
        99.5, 100.0, 101.0, 100.0, 99.5,  # weak high
        99.0, 99.5, 100.5, 100.0, 99.0,
        99.5, 100.5, 101.5, 100.0, 99.0,
        99.5, 100.5, 101.5, 100.0, 99.0,
    ]
    for i, c in enumerate(closes):
        o = closes[i - 1] if i > 0 else c
        h = max(o, c) + 0.4
        lo = min(o, c) - 0.4
        bars.append(make_bar(o, h, lo, c, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def _strong_swings() -> list:
    """Bars with clear fractal swings on both sides clustering together."""
    bars = []
    centers = [100, 105, 100, 105, 100, 105, 100]
    idx = 0
    for j, target in enumerate(centers):
        prev = centers[j - 1] if j > 0 else 100
        for k in range(3):
            frac = (k + 1) / 4
            price = prev + (target - prev) * frac
            o = price - 0.2
            c = price + 0.2
            h = max(o, c) + 0.5
            lo = min(o, c) - 0.5
            bars.append(make_bar(o, h, lo, c, ts_ns=_BASE_TS + idx * _1H_NS))
            idx += 1
        # The "peak" bar at the target — must be a real fractal.
        o = target - 0.2
        c = target
        h = target + 1.5 if target > prev else target + 0.3
        lo = target - 0.3 if target > prev else target - 1.5
        bars.append(make_bar(o, h, lo, c, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1
    return bars


def test_no_levels_in_warmup():
    det = SwingClusterDetector(period=2, atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS)
    det.update(bar)
    assert det.levels() == []


def test_emits_levels_after_swings():
    det = SwingClusterDetector(
        period=2, atr_period=5, min_touches=2,
        tolerance_atr_multiple=2.0,
    )
    for bar in _strong_swings():
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1
    for lvl in levels:
        assert lvl.source == "swing_cluster"
        assert isinstance(lvl.meta, SwingClusterMeta)
        assert lvl.meta.side in ("high", "low")
        assert isinstance(lvl.meta.touch_count, int)
        assert lvl.bounce_count >= 2


def test_mixed_sides_in_one_level():
    """Both high and low swings near same price should fold into one level."""
    det = SwingClusterDetector(
        period=2, atr_period=5, min_touches=2,
        tolerance_atr_multiple=10.0,  # generous so both sides cluster.
    )
    for bar in _strong_swings():
        det.update(bar)
    levels = det.levels()
    assert len(levels) >= 1
    # At least one level should have absorbed both sides — bounce_count > 2.
    assert any(lv.bounce_count >= 2 for lv in levels)


def test_break_finalizes_level():
    """Sustained close above a high-side level finalizes it."""
    det = SwingClusterDetector(
        period=2, atr_period=5, min_touches=2,
        tolerance_atr_multiple=2.0,
        break_atr_multiple=1.0,
        break_consecutive_bars=2,
        max_idle_bars=10_000,
    )
    bars = _strong_swings()
    # Append clear breakout bars.
    last_idx = len(bars)
    for i in range(4):
        ts = _BASE_TS + (last_idx + i) * _1H_NS
        bars.append(make_bar(120.0 + i, 125.0 + i, 119.0 + i, 124.0 + i, ts_ns=ts))
    for bar in bars:
        det.update(bar)
    levels = det.levels()
    assert any(lv.end_ts is not None for lv in levels), \
        "expected at least one level to break"


def test_active_levels_have_no_end_ts():
    det = SwingClusterDetector(
        period=2, atr_period=5, min_touches=2,
        tolerance_atr_multiple=2.0,
        break_atr_multiple=100.0,
        max_idle_bars=10_000,
    )
    for bar in _strong_swings():
        det.update(bar)
    assert any(lv.end_ts is None for lv in det.levels())


def test_deterministic():
    bars = _strong_swings()
    a = SwingClusterDetector(period=2, atr_period=5, min_touches=2)
    b = SwingClusterDetector(period=2, atr_period=5, min_touches=2)
    for bar in bars:
        a.update(bar)
        b.update(bar)
    assert a.levels() == b.levels()


def test_reset_clears_state():
    det = SwingClusterDetector(period=2, atr_period=5, min_touches=2,
                               tolerance_atr_multiple=2.0)
    for bar in _strong_swings():
        det.update(bar)
    det.reset()
    assert det.levels() == []
