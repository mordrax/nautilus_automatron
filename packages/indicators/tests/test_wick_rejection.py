"""Tests for WickRejectionDetector."""

from indicators.key_levels.detectors.wick_rejection import WickRejectionDetector
from indicators.key_levels.model import WickRejectionMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_warmup_bars(count: int = 14) -> list:
    """Create normal bars around 100 for ATR warmup (no significant wicks)."""
    bars = []
    for i in range(count):
        # Small body, small wicks — should not trigger rejections
        open_ = 100.0 + (i % 3) * 0.5
        close = open_ + 0.5
        high = max(open_, close) + 0.3
        low = min(open_, close) - 0.3
        bars.append(make_bar(open_, high, low, close, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def _make_lower_wick_bar(price_level: float, bar_index: int) -> object:
    """Create a bar with a long lower wick near price_level (support rejection).

    Body is small near the top, long lower wick reaches down to price_level.
    """
    open_ = price_level + 8.0
    close = price_level + 9.0  # small body of 1.0
    high = close + 0.5        # tiny upper wick
    low = price_level          # long lower wick = open_ - low = 8.0, ratio = 8.0
    return make_bar(open_, high, low, close, ts_ns=_BASE_TS + bar_index * _1H_NS)


def _make_upper_wick_bar(price_level: float, bar_index: int) -> object:
    """Create a bar with a long upper wick near price_level (resistance rejection).

    Body is small near the bottom, long upper wick reaches up to price_level.
    """
    close = price_level - 8.0
    open_ = price_level - 9.0  # small body of 1.0
    low = open_ - 0.5         # tiny lower wick
    high = price_level          # long upper wick = high - close = 8.0, ratio = 8.0
    return make_bar(open_, high, low, close, ts_ns=_BASE_TS + bar_index * _1H_NS)


def _make_normal_bar(bar_index: int) -> object:
    """A normal bar around 100 with no significant wicks."""
    return make_bar(99.5, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + bar_index * _1H_NS)


def _make_test_bars():
    """Create warmup bars followed by wick rejection bars near 90 and 110."""
    bars = _make_warmup_bars(14)
    idx = 14

    # 3 lower wick rejections near 90 (support)
    for i in range(3):
        bars.append(_make_lower_wick_bar(90.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    # 3 upper wick rejections near 110 (resistance)
    for i in range(3):
        bars.append(_make_upper_wick_bar(110.0 + i * 0.2, idx))
        idx += 1
        bars.append(_make_normal_bar(idx))
        idx += 1

    return bars


def test_no_levels_before_atr_ready():
    detector = WickRejectionDetector(atr_period=14, min_rejections=2)
    # Feed only a few bars — ATR won't be ready
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_wick_rejection_zones():
    detector = WickRejectionDetector(
        min_wick_ratio=2.0,
        zone_atr_multiple=2.0,
        atr_period=14,
        min_rejections=2,
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0, "Expected at least one wick rejection level"

    for level in levels:
        assert level.source == "wick_rejection"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, WickRejectionMeta)
        assert level.meta.rejection_count >= 2
        assert level.meta.avg_wick_ratio > 0.0

    # Check that levels are near expected price zones
    prices = [level.price for level in levels]
    has_support = any(85 < p < 95 for p in prices)
    has_resistance = any(105 < p < 115 for p in prices)
    assert has_support, f"Expected support level near 90, got prices={prices}"
    assert has_resistance, f"Expected resistance level near 110, got prices={prices}"


def test_deterministic():
    bars = _make_test_bars()
    det_a = WickRejectionDetector(min_wick_ratio=2.0, atr_period=14, min_rejections=2)
    det_b = WickRejectionDetector(min_wick_ratio=2.0, atr_period=14, min_rejections=2)
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
    )
    bars = _make_test_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
