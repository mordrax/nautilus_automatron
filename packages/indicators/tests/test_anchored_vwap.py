"""Tests for AnchoredVwapDetector."""

from indicators.key_levels.detectors.anchored_vwap import AnchoredVwapDetector
from indicators.key_levels.model import AnchoredVwapMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_swing_bars():
    """Create bars with clear swing structure for anchor detection.

    Pattern: uptrend to 115, downtrend to 90, uptrend to 112.
    swing_period=3 requires 3 bars on each side of a fractal.
    """
    data = []
    # Uptrend to swing high around 115
    for p in [100, 102, 105, 108, 112, 115, 112, 108, 105]:
        data.append((float(p), float(p + 1.5), float(p - 1.5), float(p), 200.0))

    # Downtrend to swing low around 90
    for p in [102, 99, 96, 93, 90, 93, 96, 99]:
        data.append((float(p), float(p + 1.5), float(p - 1.5), float(p), 200.0))

    # Uptrend again
    for p in [102, 105, 108, 112, 108, 105, 102]:
        data.append((float(p), float(p + 1.5), float(p - 1.5), float(p), 200.0))

    return [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(data)
    ]


def test_no_levels_before_warmup():
    detector = AnchoredVwapDetector(swing_period=3, max_anchors=5, atr_period=14)
    bar = make_bar(100.0, 101.5, 98.5, 100.0, volume=200.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_anchored_vwap_levels():
    detector = AnchoredVwapDetector(swing_period=3, max_anchors=5, atr_period=14)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0, "Expected at least one anchored VWAP level"

    for level in levels:
        assert level.source == "anchored_vwap"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, AnchoredVwapMeta)
        assert level.meta.cumulative_volume > 0
        assert level.meta.anchor_type in ("swing_high", "swing_low")


def test_vwap_is_weighted_average():
    """VWAP should be between the min and max typical prices."""
    detector = AnchoredVwapDetector(swing_period=3, max_anchors=5, atr_period=14)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    for level in levels:
        # VWAP price should be in a reasonable range
        assert 80.0 < level.price < 120.0, f"VWAP {level.price} out of expected range"


def test_max_anchors_respected():
    detector = AnchoredVwapDetector(swing_period=3, max_anchors=2, atr_period=14)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) <= 2, f"Expected at most 2 levels, got {len(levels)}"


def test_deterministic():
    bars = _make_swing_bars()
    det_a = AnchoredVwapDetector(swing_period=3, max_anchors=5, atr_period=14)
    det_b = AnchoredVwapDetector(swing_period=3, max_anchors=5, atr_period=14)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = AnchoredVwapDetector(swing_period=3, max_anchors=5, atr_period=14)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
