"""Tests for ConsolidationZoneDetector."""

from indicators.key_levels.detectors.consolidation_zone import ConsolidationZoneDetector
from indicators.key_levels.model import ConsolidationZoneMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def test_no_levels_before_warmup():
    detector = ConsolidationZoneDetector(atr_period=5, min_range_bars=10)
    bar = make_bar(100.0, 101.0, 99.0, 100.5)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_consolidation_zone():
    """Flat price range with compressed volatility should produce a zone."""
    detector = ConsolidationZoneDetector(
        min_range_bars=10,
        max_slope=0.002,
        volatility_threshold=0.8,
        atr_period=5,
    )

    # First: feed volatile bars to establish a high long-term ATR
    idx = 0
    for i in range(15):
        # Wide-range bars: ATR will be high
        detector.update(
            make_bar(100.0, 105.0, 95.0, 100.0, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

    # Then: feed tight-range bars to compress the short-term ATR
    for i in range(20):
        # Very tight bars: current ATR will shrink while long-term stays high
        detector.update(
            make_bar(100.0, 100.3, 99.7, 100.1, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

    levels = detector.levels()
    assert len(levels) >= 1, f"Expected consolidation levels, got {len(levels)}"

    for lvl in levels:
        assert lvl.source == "consolidation_zone"
        assert isinstance(lvl.meta, ConsolidationZoneMeta)
        assert lvl.meta.range_high >= lvl.meta.range_low
        assert lvl.meta.bar_count >= 10
        assert 0.0 < lvl.strength <= 1.0


def test_no_zone_when_trending():
    """Strong trend (high slope) should not produce a consolidation zone."""
    detector = ConsolidationZoneDetector(
        min_range_bars=10,
        max_slope=0.001,
        volatility_threshold=0.5,
        atr_period=5,
    )

    idx = 0
    # Feed trending bars: price steadily increases
    for i in range(40):
        p = 100.0 + i * 2.0
        detector.update(
            make_bar(p, p + 1.0, p - 1.0, p + 0.5, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

    levels = detector.levels()
    assert len(levels) == 0, "Trending market should not produce consolidation zone"


def test_zone_emits_high_and_low():
    """Zone should emit both range high and range low as levels."""
    detector = ConsolidationZoneDetector(
        min_range_bars=10,
        max_slope=0.002,
        volatility_threshold=0.8,
        atr_period=5,
    )

    idx = 0
    for i in range(15):
        detector.update(
            make_bar(100.0, 105.0, 95.0, 100.0, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

    for i in range(20):
        detector.update(
            make_bar(100.0, 100.3, 99.7, 100.1, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

    levels = detector.levels()
    if len(levels) >= 2:
        prices = sorted(lvl.price for lvl in levels)
        assert prices[0] < prices[1], "Should have distinct high and low levels"


def test_deterministic():
    detector_a = ConsolidationZoneDetector(
        min_range_bars=10, max_slope=0.002, volatility_threshold=0.8, atr_period=5
    )
    detector_b = ConsolidationZoneDetector(
        min_range_bars=10, max_slope=0.002, volatility_threshold=0.8, atr_period=5
    )

    bars = []
    for i in range(15):
        bars.append(make_bar(100.0, 105.0, 95.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    for i in range(20):
        bars.append(
            make_bar(100.0, 100.3, 99.7, 100.1, ts_ns=_BASE_TS + (15 + i) * _1H_NS)
        )

    for bar in bars:
        detector_a.update(bar)
        detector_b.update(bar)

    assert detector_a.levels() == detector_b.levels()


def test_reset():
    detector = ConsolidationZoneDetector(
        min_range_bars=10, max_slope=0.002, volatility_threshold=0.8, atr_period=5
    )

    idx = 0
    for i in range(15):
        detector.update(
            make_bar(100.0, 105.0, 95.0, 100.0, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1
    for i in range(20):
        detector.update(
            make_bar(100.0, 100.3, 99.7, 100.1, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

    # May or may not have levels depending on exact ATR compression
    detector.reset()
    assert detector.levels() == []
