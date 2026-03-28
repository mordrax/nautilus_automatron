"""Tests for PsychologicalLevelDetector."""

from indicators.key_levels.detectors.psychological import PsychologicalLevelDetector
from indicators.key_levels.model import PsychologicalMeta
from tests.helpers.bar_factory import make_bars_from_closes, _BASE_TS, _1H_NS


GOLD_TIERS = {"major": 100.0, "minor": 50.0, "micro": 25.0}


def _warmup_and_feed(detector, closes, start_idx=0):
    """Feed bars from closes into the detector."""
    bars = make_bars_from_closes(
        closes, start_ts=_BASE_TS + start_idx * _1H_NS
    )
    for bar in bars:
        detector.update(bar)
    return bars


def test_generates_round_levels_around_price():
    """Levels should be generated at round numbers around the current price."""
    det = PsychologicalLevelDetector(tier_steps=GOLD_TIERS, range_levels=3)

    # Feed bars around 2037.5
    closes = [2037.5] * 15  # enough for ATR warmup
    _warmup_and_feed(det, closes)

    levels = det.levels()
    assert len(levels) > 0

    # Check major levels: step=100, base=floor(2037.5/100)*100=2000
    major_levels = [
        lv for lv in levels if isinstance(lv.meta, PsychologicalMeta) and lv.meta.tier == "major"
    ]
    major_prices = sorted(lv.price for lv in major_levels)
    # range_levels=3, so: 1700, 1800, 1900, 2000, 2100, 2200, 2300
    assert major_prices == [1700.0, 1800.0, 1900.0, 2000.0, 2100.0, 2200.0, 2300.0]

    # Check minor levels: step=50, base=floor(2037.5/50)*50=2000
    minor_levels = [
        lv for lv in levels if isinstance(lv.meta, PsychologicalMeta) and lv.meta.tier == "minor"
    ]
    minor_prices = sorted(lv.price for lv in minor_levels)
    assert 2000.0 in minor_prices
    assert 2050.0 in minor_prices
    assert 1950.0 in minor_prices

    # Check micro levels: step=25, base=floor(2037.5/25)*25=2025
    micro_levels = [
        lv for lv in levels if isinstance(lv.meta, PsychologicalMeta) and lv.meta.tier == "micro"
    ]
    micro_prices = sorted(lv.price for lv in micro_levels)
    assert 2025.0 in micro_prices
    assert 2050.0 in micro_prices
    assert 2000.0 in micro_prices


def test_tier_based_strength_ordering():
    """Major levels should have higher base strength than minor, which is higher than micro."""
    det = PsychologicalLevelDetector(tier_steps=GOLD_TIERS, range_levels=2)

    closes = [2000.0] * 15
    _warmup_and_feed(det, closes)

    levels = det.levels()

    major = [lv for lv in levels if lv.meta.tier == "major"]
    minor = [lv for lv in levels if lv.meta.tier == "minor"]
    micro = [lv for lv in levels if lv.meta.tier == "micro"]

    assert len(major) > 0
    assert len(minor) > 0
    assert len(micro) > 0

    # Base strengths (no bounces yet): major=0.7, minor=0.4, micro=0.2
    # All levels at same bounce count (0), so just compare base strengths
    assert major[0].strength > minor[0].strength > micro[0].strength
    assert major[0].strength == 0.7
    assert minor[0].strength == 0.4
    assert micro[0].strength == 0.2


def test_levels_update_as_price_moves():
    """Levels should shift when price moves to a new region."""
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0}, range_levels=2
    )

    # Start around 2000
    closes_a = [2000.0] * 15
    _warmup_and_feed(det, closes_a)

    levels_a = det.levels()
    prices_a = sorted(lv.price for lv in levels_a)
    # base=2000, levels: 1800, 1900, 2000, 2100, 2200
    assert prices_a == [1800.0, 1900.0, 2000.0, 2100.0, 2200.0]

    # Move price to 2550
    closes_b = [2550.0] * 5
    bars_b = make_bars_from_closes(
        closes_b, start_ts=_BASE_TS + 15 * _1H_NS
    )
    for bar in bars_b:
        det.update(bar)

    levels_b = det.levels()
    prices_b = sorted(lv.price for lv in levels_b)
    # base=floor(2550/100)*100=2500, levels: 2300, 2400, 2500, 2600, 2700
    assert prices_b == [2300.0, 2400.0, 2500.0, 2600.0, 2700.0]


def test_deterministic():
    """Two detectors fed the same data should produce identical levels."""
    closes = [2037.5 + i * 2.0 for i in range(20)]

    det_a = PsychologicalLevelDetector(tier_steps=GOLD_TIERS, range_levels=3)
    det_b = PsychologicalLevelDetector(tier_steps=GOLD_TIERS, range_levels=3)

    bars = make_bars_from_closes(closes)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)

    assert det_a.levels() == det_b.levels()


def test_reset_clears_state():
    """After reset, detector should have no levels and no bounce history."""
    det = PsychologicalLevelDetector(tier_steps=GOLD_TIERS, range_levels=2)

    closes = [2000.0] * 15
    _warmup_and_feed(det, closes)
    assert len(det.levels()) > 0

    det.reset()
    assert det.levels() == []


def test_source_and_meta():
    """All levels should have correct source and meta type."""
    det = PsychologicalLevelDetector(tier_steps=GOLD_TIERS, range_levels=1)

    closes = [2037.5] * 15
    _warmup_and_feed(det, closes)

    for lv in det.levels():
        assert lv.source == "psychological"
        assert isinstance(lv.meta, PsychologicalMeta)
        assert lv.meta.tier in ("major", "minor", "micro")
        assert lv.meta.round_value == lv.price


def test_bounce_counting_increases_strength():
    """Bouncing at a level should increase its strength."""
    det = PsychologicalLevelDetector(
        tier_steps={"major": 100.0}, range_levels=2, atr_period=5
    )

    # Warmup ATR with bars near 2000
    closes = [2000.0] * 6
    _warmup_and_feed(det, closes)

    # Get baseline strength of the 2000 level
    levels = det.levels()
    level_2000 = [lv for lv in levels if lv.price == 2000.0]
    assert len(level_2000) == 1
    baseline_strength = level_2000[0].strength
    assert baseline_strength == 0.7  # major base

    # Now bounce: move away from 2000 then back, repeatedly
    idx = 6
    bounce_closes = []
    for _ in range(3):
        # Move away from 2000
        bounce_closes.extend([2050.0, 2060.0, 2070.0])
        # Come back to 2000
        bounce_closes.extend([2010.0, 2000.0, 1990.0])

    bars = make_bars_from_closes(bounce_closes, start_ts=_BASE_TS + idx * _1H_NS)
    for bar in bars:
        det.update(bar)

    # After bounces, 2000 level should have higher strength
    levels = det.levels()
    level_2000 = [lv for lv in levels if lv.price == 2000.0]
    assert len(level_2000) == 1
    assert level_2000[0].strength >= baseline_strength
    assert level_2000[0].bounce_count >= 1


def test_eurusd_tiers():
    """Verify correct level generation for forex-scale tier steps."""
    det = PsychologicalLevelDetector(
        tier_steps={"major": 0.01, "minor": 0.005}, range_levels=2
    )

    closes = [1.0525] * 15
    _warmup_and_feed(det, closes)

    levels = det.levels()
    major_prices = sorted(lv.price for lv in levels if lv.meta.tier == "major")
    # base=floor(1.0525/0.01)*0.01 = 1.05
    # levels: 1.03, 1.04, 1.05, 1.06, 1.07
    for p in [1.03, 1.04, 1.05, 1.06, 1.07]:
        assert any(abs(mp - p) < 1e-9 for mp in major_prices), (
            f"Expected {p} in major prices, got {major_prices}"
        )
