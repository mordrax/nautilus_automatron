"""Tests for PriceGapDetector."""

from indicators.key_levels.detectors.price_gaps import PriceGapDetector
from indicators.key_levels.model import PriceGapMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def test_no_levels_before_warmup():
    detector = PriceGapDetector(atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.5)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_gap_up():
    """Gap up: current bar.low > prev bar.high."""
    detector = PriceGapDetector(
        atr_period=3,
        volume_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    # Warmup bars with TR ~2.0
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    # Normal bar: high=101.0
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Gap up: low=103.0 > prev high=101.0
    detector.update(make_bar(104.0, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + idx * _1H_NS))

    levels = detector.levels()
    assert len(levels) >= 2, f"Expected at least 2 levels (upper+lower), got {len(levels)}"

    for lvl in levels:
        assert lvl.source == "price_gap"
        assert isinstance(lvl.meta, PriceGapMeta)
        assert lvl.meta.gap_size > 0
        assert 0.0 < lvl.strength <= 1.0

    # Should have upper and lower levels
    level_types = {lvl.meta.level_type for lvl in levels}
    assert "upper" in level_types
    assert "lower" in level_types


def test_finds_gap_down():
    """Gap down: current bar.high < prev bar.low."""
    detector = PriceGapDetector(
        atr_period=3,
        volume_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    # Normal bar: low=99.0
    detector.update(make_bar(100.0, 101.0, 99.0, 99.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Gap down: high=97.0 < prev low=99.0
    detector.update(make_bar(96.5, 97.0, 95.0, 95.5, ts_ns=_BASE_TS + idx * _1H_NS))

    levels = detector.levels()
    assert len(levels) >= 2
    for lvl in levels:
        assert lvl.source == "price_gap"
        assert isinstance(lvl.meta, PriceGapMeta)


def test_breakaway_gap_classification():
    """High volume gap should be classified as breakaway."""
    detector = PriceGapDetector(
        atr_period=3,
        volume_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    # Warmup with normal volume=100
    for i in range(3):
        detector.update(
            make_bar(100.0, 101.0, 99.0, 100.0, volume=100.0, ts_ns=_BASE_TS + i * _1H_NS)
        )

    idx = 3
    detector.update(
        make_bar(100.0, 101.0, 99.0, 100.5, volume=100.0, ts_ns=_BASE_TS + idx * _1H_NS)
    )
    idx += 1

    # Gap up with high volume (>1.5x avg)
    detector.update(
        make_bar(104.0, 105.0, 103.0, 104.5, volume=200.0, ts_ns=_BASE_TS + idx * _1H_NS)
    )

    levels = detector.levels()
    assert len(levels) >= 1
    assert levels[0].meta.gap_type == "breakaway"
    assert levels[0].strength == 1.0


def test_exhaustion_gap_classification():
    """Low volume gap should be classified as exhaustion."""
    detector = PriceGapDetector(
        atr_period=3,
        volume_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(
            make_bar(100.0, 101.0, 99.0, 100.0, volume=100.0, ts_ns=_BASE_TS + i * _1H_NS)
        )

    idx = 3
    detector.update(
        make_bar(100.0, 101.0, 99.0, 100.5, volume=100.0, ts_ns=_BASE_TS + idx * _1H_NS)
    )
    idx += 1

    # Gap up with low volume (<0.5x avg)
    detector.update(
        make_bar(104.0, 105.0, 103.0, 104.5, volume=30.0, ts_ns=_BASE_TS + idx * _1H_NS)
    )

    levels = detector.levels()
    assert len(levels) >= 1
    assert levels[0].meta.gap_type == "exhaustion"


def test_fill_tracking():
    """Gap should track fill percentage."""
    detector = PriceGapDetector(
        atr_period=3,
        volume_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Gap up: gap=[101.0, 103.0]
    detector.update(make_bar(104.0, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    initial_levels = detector.levels()
    assert len(initial_levels) >= 1

    # Price drops into the gap
    detector.update(make_bar(103.5, 104.0, 101.5, 102.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    filled_levels = detector.levels()
    if len(filled_levels) >= 1:
        assert filled_levels[0].meta.fill_percentage > 0


def test_expire_on_full_fill():
    """Gap should expire when fully filled."""
    detector = PriceGapDetector(
        atr_period=3,
        volume_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Gap up: gap=[101.0, 103.0]
    detector.update(make_bar(104.0, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    assert len(detector.levels()) >= 1

    # Price drops through entire gap
    detector.update(make_bar(103.0, 103.5, 100.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    assert len(detector.levels()) == 0, "Fully filled gap should be expired"


def test_deterministic():
    detector_a = PriceGapDetector(atr_period=3, min_gap_atr_multiple=0.1, volume_period=3)
    detector_b = PriceGapDetector(atr_period=3, min_gap_atr_multiple=0.1, volume_period=3)

    bars = []
    for i in range(3):
        bars.append(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    bars.append(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + 3 * _1H_NS))
    bars.append(make_bar(104.0, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + 4 * _1H_NS))

    for bar in bars:
        detector_a.update(bar)
        detector_b.update(bar)

    assert detector_a.levels() == detector_b.levels()


def test_reset():
    detector = PriceGapDetector(atr_period=3, min_gap_atr_multiple=0.1, volume_period=3)

    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + 3 * _1H_NS))
    detector.update(make_bar(104.0, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + 4 * _1H_NS))

    assert len(detector.levels()) >= 1
    detector.reset()
    assert detector.levels() == []
