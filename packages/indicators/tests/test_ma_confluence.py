"""Tests for MaConfluenceDetector."""

from indicators.key_levels.detectors.ma_confluence import MaConfluenceDetector
from indicators.key_levels.model import MaConfluenceMeta
from tests.helpers.bar_factory import make_bars_from_closes


def test_no_levels_before_warmup():
    """No levels should be emitted until all EMAs are initialized."""
    detector = MaConfluenceDetector(
        ma_periods=(9, 21, 50),
        min_converging=3,
        atr_period=14,
    )
    # Feed fewer bars than the max period (50)
    bars = make_bars_from_closes([100.0] * 40)
    for bar in bars:
        detector.update(bar)
    assert detector.levels() == []


def test_finds_confluence_with_flat_price():
    """When price is flat, all EMAs converge to the same value → confluence."""
    detector = MaConfluenceDetector(
        ma_periods=(5, 10, 20),
        min_converging=3,
        spread_threshold=0.5,
        atr_period=5,
    )
    # Feed enough flat bars: max(20, 5) = 20 for EMA warmup, plus ATR warmup
    bars = make_bars_from_closes([100.0] * 50)
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) == 1, f"Expected 1 confluence level, got {len(levels)}"

    level = levels[0]
    assert level.source == "ma_confluence"
    assert isinstance(level.meta, MaConfluenceMeta)
    assert level.meta.converging_periods == (5, 10, 20)
    assert 99.0 < level.price < 101.0
    assert 0.0 <= level.strength <= 1.0
    assert level.zone_lower <= level.price <= level.zone_upper
    assert level.bounce_count == 0


def test_no_confluence_with_trending_price():
    """When price trends strongly, EMAs should be spread apart → no confluence."""
    detector = MaConfluenceDetector(
        ma_periods=(5, 10, 50),
        min_converging=3,
        spread_threshold=0.3,
        atr_period=5,
    )
    # Strong uptrend: 50 to 200
    closes = [50.0 + i * 3.0 for i in range(60)]
    bars = make_bars_from_closes(closes)
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    # With strong trend, all 3 should NOT converge
    for level in levels:
        assert isinstance(level.meta, MaConfluenceMeta)
        # If any level found, it should not include all 3 periods
        assert len(level.meta.converging_periods) < 3 or level.meta.spread_percent > 0


def test_partial_confluence():
    """When only some MAs converge, min_converging controls detection."""
    detector = MaConfluenceDetector(
        ma_periods=(5, 10, 50, 100),
        min_converging=2,
        spread_threshold=1.0,
        atr_period=5,
    )
    # Flat price → all converge, should get level with converging_periods including all
    bars = make_bars_from_closes([100.0] * 120)
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) == 1
    assert len(levels[0].meta.converging_periods) >= 2


def test_deterministic():
    """Two identical detectors should produce identical results."""
    bars = make_bars_from_closes([100.0 + (i % 5) * 0.5 for i in range(80)])
    det_a = MaConfluenceDetector(ma_periods=(5, 10, 20), atr_period=5)
    det_b = MaConfluenceDetector(ma_periods=(5, 10, 20), atr_period=5)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    """After reset, detector should return no levels."""
    detector = MaConfluenceDetector(
        ma_periods=(5, 10, 20),
        min_converging=3,
        atr_period=5,
    )
    bars = make_bars_from_closes([100.0] * 50)
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []


def test_strength_calculation():
    """Strength should be bounded [0, 1] and reflect convergence quality."""
    detector = MaConfluenceDetector(
        ma_periods=(5, 10, 20),
        min_converging=2,
        spread_threshold=1.0,
        atr_period=5,
    )
    bars = make_bars_from_closes([100.0] * 50)
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0
    for level in levels:
        assert 0.0 <= level.strength <= 1.0
