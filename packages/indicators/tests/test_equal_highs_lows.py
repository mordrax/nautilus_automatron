"""Tests for EqualHighsLowsDetector."""


from indicators.key_levels.detectors.equal_highs_lows import EqualHighsLowsDetector
from indicators.key_levels.model import EqualHighsLowsMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_equal_highs_lows_bars():
    """Create bars with 3 swing highs near 110 and 3 swing lows near 90.

    Pattern: rise to ~110, drop to ~90, repeat three times.
    With period=2, we need 2 bars on each side of the swing point
    that are strictly lower (for highs) or higher (for lows).
    """
    data = [
        # --- First swing high at 110 ---
        (100.0, 102.0, 98.0, 101.0, 100.0),
        (101.0, 106.0, 100.0, 105.0, 100.0),
        (105.0, 110.0, 104.0, 108.0, 100.0),   # bar 2 - swing high 110
        (108.0, 108.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 95.0, 96.0, 100.0),
        # --- First swing low at 90 ---
        (96.0, 97.0, 92.0, 93.0, 100.0),
        (93.0, 94.0, 90.0, 91.0, 100.0),        # bar 6 - swing low 90
        (91.0, 96.0, 91.0, 95.0, 100.0),
        (95.0, 100.0, 94.0, 99.0, 100.0),
        # --- Second swing high near 110 ---
        (99.0, 104.0, 98.0, 103.0, 100.0),
        (103.0, 109.0, 102.0, 107.0, 100.0),    # bar 10 - swing high 109
        (107.0, 107.0, 99.0, 101.0, 100.0),
        (101.0, 102.0, 95.0, 97.0, 100.0),
        # --- Second swing low near 90 ---
        (97.0, 98.0, 93.0, 94.0, 100.0),
        (94.0, 95.0, 91.0, 92.0, 100.0),        # bar 14 - swing low 91
        (92.0, 97.0, 91.0, 96.0, 100.0),
        (96.0, 100.0, 95.0, 99.0, 100.0),
        # --- Third swing high near 110 ---
        (99.0, 104.0, 98.0, 103.0, 100.0),
        (103.0, 110.0, 102.0, 108.0, 100.0),    # bar 18 - swing high 110
        (108.0, 108.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 95.0, 96.0, 100.0),
        # --- Third swing low near 90 ---
        (96.0, 97.0, 92.0, 93.0, 100.0),
        (93.0, 94.0, 90.0, 91.0, 100.0),        # bar 22 - swing low 90
        (91.0, 96.0, 91.0, 95.0, 100.0),
        (95.0, 100.0, 94.0, 99.0, 100.0),
    ]
    return [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(data)
    ]


def test_no_levels_before_warmup():
    detector = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, atr_period=14)
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_equal_highs_and_lows():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.5, atr_period=14, min_touches=2,
    )
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    assert len(levels) > 0

    # All levels should have the correct source
    for level in levels:
        assert level.source == "equal_highs_lows"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, EqualHighsLowsMeta)

    # Check we have both high and low sides
    sides = {level.meta.side for level in levels}
    assert "high" in sides, f"Expected 'high' side in levels, got sides={sides}"
    assert "low" in sides, f"Expected 'low' side in levels, got sides={sides}"

    # Check high-side levels are near 110 and low-side levels are near 90
    for level in levels:
        if level.meta.side == "high":
            assert 105 < level.price < 115, f"High level price {level.price} not near 110"
        else:
            assert 85 < level.price < 95, f"Low level price {level.price} not near 90"


def test_min_touches_filtering():
    detector = EqualHighsLowsDetector(
        period=2, tolerance_atr_multiple=0.5, atr_period=14, min_touches=3,
    )
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)

    levels = detector.levels()
    for level in levels:
        assert level.bounce_count >= 3


def test_deterministic():
    bars = _make_equal_highs_lows_bars()
    det_a = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, atr_period=14)
    det_b = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, atr_period=14)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = EqualHighsLowsDetector(period=2, tolerance_atr_multiple=0.5, atr_period=14)
    bars = _make_equal_highs_lows_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0
    detector.reset()
    assert detector.levels() == []
