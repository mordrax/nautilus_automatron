"""Tests for VolumeDistributionDetector."""

from indicators.key_levels.detectors.volume_distribution import VolumeDistributionDetector
from indicators.key_levels.model import VolumeDistributionMeta
from tests.helpers.bar_factory import make_bar, make_bars_from_ohlcv


def _make_structural_bars():
    """Create bars with clear swing structure and volume concentration.

    Pattern: swing high at ~115, swing low at ~90, with consolidation
    between swings that has concentrated volume.
    """
    data = []

    # Uptrend to swing high around 115 (swing_period=3 so need 3 bars each side)
    for p in [100, 102, 105, 108, 112, 115, 112, 108, 105]:
        data.append((float(p), float(p + 1.5), float(p - 1.5), float(p), 100.0))

    # Consolidation range 103-107 with high volume (at least 10 bars)
    for i in range(15):
        base = 104.0 + (i % 4) * 0.8
        data.append((base, base + 1.0, base - 1.0, base + 0.3, 500.0))

    # Downtrend to swing low around 90
    for p in [102, 99, 96, 93, 90, 93, 96, 99]:
        data.append((float(p), float(p + 1.5), float(p - 1.5), float(p), 100.0))

    # Another consolidation with volume
    for i in range(12):
        base = 98.0 + (i % 3) * 0.5
        data.append((base, base + 1.0, base - 1.0, base + 0.2, 400.0))

    return make_bars_from_ohlcv(data)


def test_no_levels_before_warmup():
    detector = VolumeDistributionDetector(swing_period=3, min_context_bars=10, atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.5, volume=100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_volume_distribution_levels():
    detector = VolumeDistributionDetector(
        swing_period=3,
        min_context_bars=5,
        bin_count=20,
        atr_period=14,
    )
    bars = _make_structural_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0, "Expected at least one volume distribution level"

    for level in levels:
        assert level.source == "volume_distribution"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, VolumeDistributionMeta)
        assert level.meta.context_bar_count >= 1
        assert 0.0 <= level.meta.volume_concentration <= 1.0


def test_deterministic():
    bars = _make_structural_bars()
    det_a = VolumeDistributionDetector(swing_period=3, min_context_bars=5, atr_period=14)
    det_b = VolumeDistributionDetector(swing_period=3, min_context_bars=5, atr_period=14)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = VolumeDistributionDetector(swing_period=3, min_context_bars=5, atr_period=14)
    bars = _make_structural_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
