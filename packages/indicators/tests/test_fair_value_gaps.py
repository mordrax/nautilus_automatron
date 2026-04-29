"""Tests for FairValueGapDetector."""

from indicators.key_levels.detectors.fair_value_gaps import FairValueGapDetector
from indicators.key_levels.model import FairValueGapMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_warmup_bars(count: int = 5) -> list:
    """Create normal bars for ATR warmup."""
    bars = []
    for i in range(count):
        open_ = 100.0 + (i % 3) * 0.5
        close = open_ + 0.5
        high = max(open_, close) + 0.3
        low = min(open_, close) - 0.3
        bars.append(make_bar(open_, high, low, close, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def test_no_levels_before_warmup():
    detector = FairValueGapDetector(atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.5)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_bullish_fvg():
    """Bullish FVG: bar[2].low > bar[0].high (gap up)."""
    detector = FairValueGapDetector(
        atr_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    # ATR warmup: bars with TR ~2.0
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    # bar[i-2]: high=101.0
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # bar[i-1]: middle bar (the gap candle)
    detector.update(make_bar(101.0, 104.0, 100.5, 103.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # bar[i]: low=103.0 > bar[i-2].high=101.0 => bullish FVG gap=[101.0, 103.0]
    detector.update(make_bar(103.5, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + idx * _1H_NS))

    levels = detector.levels()
    assert len(levels) >= 1, f"Expected at least 1 FVG level, got {len(levels)}"

    fvg = levels[0]
    assert fvg.source == "fair_value_gap"
    assert isinstance(fvg.meta, FairValueGapMeta)
    assert fvg.meta.side == "bullish"
    assert fvg.meta.gap_size > 0
    assert 0.0 < fvg.strength <= 1.0


def test_finds_bearish_fvg():
    """Bearish FVG: bar[2].high < bar[0].low (gap down)."""
    detector = FairValueGapDetector(
        atr_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    # bar[i-2]: low=99.0
    detector.update(make_bar(100.0, 101.0, 99.0, 99.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # middle bar: gap down
    detector.update(make_bar(99.0, 99.5, 96.0, 96.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # bar[i]: high=97.0 < bar[i-2].low=99.0 => bearish FVG gap=[97.0, 99.0]
    detector.update(make_bar(96.5, 97.0, 95.0, 95.5, ts_ns=_BASE_TS + idx * _1H_NS))

    levels = detector.levels()
    assert len(levels) >= 1
    fvg = levels[0]
    assert fvg.source == "fair_value_gap"
    assert isinstance(fvg.meta, FairValueGapMeta)
    assert fvg.meta.side == "bearish"


def test_fill_tracking():
    """FVG should track fill as price revisits the gap zone."""
    detector = FairValueGapDetector(
        atr_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    # Create bullish FVG: gap=[101.0, 103.0]
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    detector.update(make_bar(101.0, 104.0, 100.5, 103.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    detector.update(make_bar(103.5, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    initial_levels = detector.levels()
    assert len(initial_levels) >= 1
    initial_fill = initial_levels[0].meta.fill_percentage

    # Price drops into the gap zone
    detector.update(make_bar(104.0, 104.5, 101.5, 102.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    filled_levels = detector.levels()
    if len(filled_levels) >= 1:
        assert filled_levels[0].meta.fill_percentage >= initial_fill


def test_expire_on_full_fill():
    """FVG should be removed when fully filled."""
    detector = FairValueGapDetector(
        atr_period=3,
        min_gap_atr_multiple=0.1,
        max_age_bars=200,
    )
    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))

    idx = 3
    # Create bullish FVG: gap=[101.0, 103.0]
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    detector.update(make_bar(101.0, 104.0, 100.5, 103.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    detector.update(make_bar(103.5, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Price drops through the entire gap (low < gap lower = 101.0)
    detector.update(make_bar(103.0, 103.5, 100.0, 100.5, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # After full fill, FVG should be expired
    assert len(detector.levels()) == 0, "Fully filled FVG should be expired"


def test_deterministic():
    detector_a = FairValueGapDetector(atr_period=3, min_gap_atr_multiple=0.1)
    detector_b = FairValueGapDetector(atr_period=3, min_gap_atr_multiple=0.1)

    bars = []
    for i in range(3):
        bars.append(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    bars.append(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + 3 * _1H_NS))
    bars.append(make_bar(101.0, 104.0, 100.5, 103.5, ts_ns=_BASE_TS + 4 * _1H_NS))
    bars.append(make_bar(103.5, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + 5 * _1H_NS))

    for bar in bars:
        detector_a.update(bar)
        detector_b.update(bar)

    assert detector_a.levels() == detector_b.levels()


def test_reset():
    detector = FairValueGapDetector(atr_period=3, min_gap_atr_multiple=0.1)

    for i in range(3):
        detector.update(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    detector.update(make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + 3 * _1H_NS))
    detector.update(make_bar(101.0, 104.0, 100.5, 103.5, ts_ns=_BASE_TS + 4 * _1H_NS))
    detector.update(make_bar(103.5, 105.0, 103.0, 104.5, ts_ns=_BASE_TS + 5 * _1H_NS))

    assert len(detector.levels()) >= 1
    detector.reset()
    assert detector.levels() == []
