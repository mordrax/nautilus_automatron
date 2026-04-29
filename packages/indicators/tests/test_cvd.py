"""Tests for CvdDetector."""

from indicators.key_levels.detectors.cvd import CvdDetector, _estimate_buy_volume
from indicators.key_levels.model import CvdMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_cvd_bars():
    """Create bars with clear bullish/bearish volume patterns and price swings.

    Pattern: strong buying to 115, then strong selling to 90, then buying again.
    swing_period=3 requires 3 bars on each side of a fractal.
    """
    data = []

    # Strong buying phase (close > open, big volume) up to 115
    for p in [100, 102, 105, 108, 112, 115, 112, 108, 105]:
        # Bullish bars: close above open
        o = float(p) - 1.0
        c = float(p)
        h = c + 1.5
        lo = o - 1.5
        data.append((o, h, lo, c, 500.0))

    # Strong selling phase (close < open) down to 90
    for p in [102, 99, 96, 93, 90, 93, 96, 99]:
        # Bearish bars: close below open
        o = float(p) + 1.0
        c = float(p)
        h = o + 1.5
        lo = c - 1.5
        data.append((o, h, lo, c, 500.0))

    # Buying again
    for p in [102, 105, 108, 112, 108, 105, 102]:
        o = float(p) - 1.0
        c = float(p)
        h = c + 1.5
        lo = o - 1.5
        data.append((o, h, lo, c, 500.0))

    return [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(data)
    ]


def test_buy_volume_bullish_bar():
    """Bullish bar (close > open) should have buy_vol > 50% of volume."""
    buy = _estimate_buy_volume(100.0, 105.0, 95.0, 104.0, 1000.0)
    assert buy > 500.0  # More than half


def test_buy_volume_bearish_bar():
    """Bearish bar (close < open) should have buy_vol < 50% of volume."""
    # close=97 is near low=95, so buy volume should be small
    buy = _estimate_buy_volume(104.0, 105.0, 95.0, 97.0, 1000.0)
    assert buy < 500.0  # Less than half


def test_buy_volume_doji():
    """Doji (close == open) should split 50/50."""
    buy = _estimate_buy_volume(100.0, 105.0, 95.0, 100.0, 1000.0)
    assert buy == 500.0


def test_buy_volume_zero_range():
    """Zero range bar should split 50/50."""
    buy = _estimate_buy_volume(100.0, 100.0, 100.0, 100.0, 1000.0)
    assert buy == 500.0


def test_no_levels_before_warmup():
    detector = CvdDetector(swing_period=3, atr_period=14)
    bar = make_bar(99.0, 101.5, 98.5, 100.0, volume=500.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_cvd_levels():
    detector = CvdDetector(swing_period=3, atr_period=14)
    bars = _make_cvd_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0, "Expected at least one CVD level"

    for level in levels:
        assert level.source == "cvd"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, CvdMeta)
        assert level.meta.divergence in ("bullish", "bearish", "none")


def test_deterministic():
    bars = _make_cvd_bars()
    det_a = CvdDetector(swing_period=3, atr_period=14)
    det_b = CvdDetector(swing_period=3, atr_period=14)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = CvdDetector(swing_period=3, atr_period=14)
    bars = _make_cvd_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
