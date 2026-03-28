"""Tests for OrderBlockDetector."""

from indicators.key_levels.detectors.order_blocks import OrderBlockDetector
from indicators.key_levels.model import OrderBlockMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_warmup_bars(count: int = 14) -> list:
    """Create normal bars around 100 for ATR warmup."""
    bars = []
    for i in range(count):
        open_ = 100.0 + (i % 3) * 0.5
        close = open_ + 0.5
        high = max(open_, close) + 0.3
        low = min(open_, close) - 0.3
        bars.append(make_bar(open_, high, low, close, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def test_no_levels_before_warmup():
    detector = OrderBlockDetector(atr_period=14)
    bar = make_bar(100.0, 101.0, 99.0, 100.5)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_bullish_order_block():
    """A bearish candle followed by a large bullish impulsive move should produce a bullish OB."""
    detector = OrderBlockDetector(
        atr_period=5,
        displacement_threshold=2.0,
        max_age_bars=200,
    )
    # Warmup bars with ATR around 2.0
    warmup = []
    for i in range(5):
        warmup.append(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    for bar in warmup:
        detector.update(bar)

    idx = 5
    # Bearish candle (opposing candle for bullish OB)
    bearish = make_bar(100.0, 100.5, 98.5, 99.0, ts_ns=_BASE_TS + idx * _1H_NS)
    detector.update(bearish)
    idx += 1

    # Small neutral bar
    neutral = make_bar(99.0, 99.5, 98.5, 99.2, ts_ns=_BASE_TS + idx * _1H_NS)
    detector.update(neutral)
    idx += 1

    # Large bullish impulsive move (body > 2 * ATR ~2.0 = 4.0)
    impulsive = make_bar(99.5, 106.0, 99.5, 106.0, ts_ns=_BASE_TS + idx * _1H_NS)
    detector.update(impulsive)

    levels = detector.levels()
    assert len(levels) >= 1, f"Expected at least 1 order block level, got {len(levels)}"

    ob_level = levels[0]
    assert ob_level.source == "order_block"
    assert isinstance(ob_level.meta, OrderBlockMeta)
    assert ob_level.meta.side == "bullish"
    assert ob_level.meta.displacement_atr_multiple > 2.0
    assert 0.0 < ob_level.strength <= 1.0


def test_finds_bearish_order_block():
    """A bullish candle followed by a large bearish impulsive move should produce a bearish OB."""
    detector = OrderBlockDetector(
        atr_period=5,
        displacement_threshold=2.0,
        max_age_bars=200,
    )
    warmup = []
    for i in range(5):
        warmup.append(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    for bar in warmup:
        detector.update(bar)

    idx = 5
    # Bullish candle (opposing for bearish OB)
    bullish = make_bar(100.0, 101.5, 99.5, 101.0, ts_ns=_BASE_TS + idx * _1H_NS)
    detector.update(bullish)
    idx += 1

    neutral = make_bar(101.0, 101.5, 100.5, 100.8, ts_ns=_BASE_TS + idx * _1H_NS)
    detector.update(neutral)
    idx += 1

    # Large bearish impulsive move
    impulsive = make_bar(100.5, 100.5, 94.0, 94.0, ts_ns=_BASE_TS + idx * _1H_NS)
    detector.update(impulsive)

    levels = detector.levels()
    assert len(levels) >= 1
    ob_level = levels[0]
    assert ob_level.source == "order_block"
    assert isinstance(ob_level.meta, OrderBlockMeta)
    assert ob_level.meta.side == "bearish"


def test_age_expiry():
    """Order blocks should expire after max_age_bars."""
    detector = OrderBlockDetector(
        atr_period=5,
        displacement_threshold=2.0,
        max_age_bars=10,
    )
    warmup = []
    for i in range(5):
        warmup.append(make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
    for bar in warmup:
        detector.update(bar)

    idx = 5
    # Create a bullish OB
    detector.update(make_bar(100.0, 100.5, 98.5, 99.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1
    detector.update(make_bar(99.5, 106.0, 99.5, 106.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    assert len(detector.levels()) >= 1

    # Feed enough bars to expire the OB
    for i in range(15):
        detector.update(make_bar(105.0, 106.0, 104.0, 105.0, ts_ns=_BASE_TS + (idx + i) * _1H_NS))

    assert len(detector.levels()) == 0, "Order block should have expired"


def test_deterministic():
    detector_a = OrderBlockDetector(atr_period=5, displacement_threshold=2.0)
    detector_b = OrderBlockDetector(atr_period=5, displacement_threshold=2.0)

    bars = _make_warmup_bars(5)
    bars.append(make_bar(100.0, 100.5, 98.5, 99.0, ts_ns=_BASE_TS + 5 * _1H_NS))
    bars.append(make_bar(99.5, 106.0, 99.5, 106.0, ts_ns=_BASE_TS + 6 * _1H_NS))

    for bar in bars:
        detector_a.update(bar)
        detector_b.update(bar)

    assert detector_a.levels() == detector_b.levels()


def test_reset():
    detector = OrderBlockDetector(atr_period=5, displacement_threshold=2.0)

    bars = _make_warmup_bars(5)
    bars.append(make_bar(100.0, 100.5, 98.5, 99.0, ts_ns=_BASE_TS + 5 * _1H_NS))
    bars.append(make_bar(99.5, 106.0, 99.5, 106.0, ts_ns=_BASE_TS + 6 * _1H_NS))

    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) >= 1

    detector.reset()
    assert detector.levels() == []
