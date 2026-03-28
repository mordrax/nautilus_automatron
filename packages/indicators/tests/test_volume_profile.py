"""Tests for VolumeProfileDetector."""

from indicators.key_levels.detectors.volume_profile import VolumeProfileDetector
from indicators.key_levels.model import VolumeProfileMeta
from tests.helpers.bar_factory import make_bar, make_bars_from_ohlcv, _BASE_TS, _1H_NS


def _make_warmup_bars(count: int = 50) -> list:
    """Create bars around 100 for warmup."""
    bars = []
    for i in range(count):
        o = 100.0 + (i % 3) * 0.5
        c = o + 0.3
        h = max(o, c) + 0.5
        lo = min(o, c) - 0.5
        bars.append(make_bar(o, h, lo, c, volume=100.0, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def _make_concentrated_volume_bars():
    """Create bars with concentrated volume at specific price levels.

    Most volume occurs in the 100-102 range (high volume node).
    Less volume at 95 and 108 (low volume nodes).
    """
    bars = []
    idx = 0

    # First, warmup bars around 100 with moderate volume
    for i in range(30):
        o = 100.0 + (i % 3) * 0.3
        c = o + 0.2
        h = max(o, c) + 0.3
        lo = min(o, c) - 0.3
        bars.append(make_bar(o, h, lo, c, volume=200.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    # High-volume bars around 101 (should become POC)
    for i in range(15):
        o = 100.5 + (i % 2) * 0.5
        c = 101.0 + (i % 2) * 0.3
        h = max(o, c) + 0.3
        lo = min(o, c) - 0.3
        bars.append(make_bar(o, h, lo, c, volume=500.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    # Low-volume bars at 95 (LVN)
    for i in range(3):
        bars.append(make_bar(95.0, 95.5, 94.5, 95.2, volume=20.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    # Low-volume bars at 108 (LVN)
    for i in range(3):
        bars.append(make_bar(108.0, 108.5, 107.5, 108.2, volume=20.0, ts_ns=_BASE_TS + idx * _1H_NS))
        idx += 1

    return bars


def test_no_levels_before_warmup():
    detector = VolumeProfileDetector(lookback_bars=50)
    bar = make_bar(100.0, 101.0, 99.0, 100.5, volume=100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_poc_level():
    detector = VolumeProfileDetector(
        lookback_bars=50,
        bin_count=30,
        value_area_pct=0.7,
        atr_period=14,
    )
    bars = _make_concentrated_volume_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0, "Expected at least one volume profile level"

    # Find POC level
    poc_levels = [l for l in levels if isinstance(l.meta, VolumeProfileMeta) and l.meta.node_type == "poc"]
    assert len(poc_levels) == 1, f"Expected exactly one POC, got {len(poc_levels)}"

    poc = poc_levels[0]
    assert poc.source == "volume_profile"
    assert poc.strength == 1.0  # POC always has strength 1.0
    assert 99.0 < poc.price < 103.0, f"POC should be near 100-102, got {poc.price}"


def test_finds_value_area():
    detector = VolumeProfileDetector(
        lookback_bars=50,
        bin_count=30,
        value_area_pct=0.7,
        atr_period=14,
    )
    bars = _make_concentrated_volume_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    va_levels = [l for l in levels if isinstance(l.meta, VolumeProfileMeta) and l.meta.node_type in ("va_high", "va_low")]
    assert len(va_levels) == 2, f"Expected VA high and VA low, got {len(va_levels)}"

    va_high = [l for l in va_levels if l.meta.node_type == "va_high"][0]
    va_low = [l for l in va_levels if l.meta.node_type == "va_low"][0]
    assert va_high.price > va_low.price
    assert va_high.strength == 0.8
    assert va_low.strength == 0.8


def test_level_invariants():
    detector = VolumeProfileDetector(lookback_bars=50, bin_count=30, atr_period=14)
    bars = _make_concentrated_volume_bars()
    for bar in bars:
        detector.update(bar)

    for level in detector.levels():
        assert level.source == "volume_profile"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, VolumeProfileMeta)


def test_deterministic():
    bars = _make_concentrated_volume_bars()
    det_a = VolumeProfileDetector(lookback_bars=50, bin_count=30, atr_period=14)
    det_b = VolumeProfileDetector(lookback_bars=50, bin_count=30, atr_period=14)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = VolumeProfileDetector(lookback_bars=50, bin_count=30, atr_period=14)
    bars = _make_concentrated_volume_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
