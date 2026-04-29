"""Tests for DarvasBoxDetector."""

from indicators.key_levels.detectors.darvas_box import DarvasBoxDetector
from indicators.key_levels.model import DarvasBoxMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_warmup_bars(count: int = 20) -> list:
    """Create bars around 100 for lookback warmup."""
    bars = []
    for i in range(count):
        open_ = 100.0 + (i % 3) * 0.5
        close = open_ + 0.3
        high = max(open_, close) + 0.2
        low = min(open_, close) - 0.2
        bars.append(make_bar(open_, high, low, close, ts_ns=_BASE_TS + i * _1H_NS))
    return bars


def test_no_levels_before_warmup():
    detector = DarvasBoxDetector(lookback_period=20, confirmation_bars=3)
    bar = make_bar(100.0, 101.0, 99.0, 100.5)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_darvas_box():
    """New high followed by consolidation should produce a confirmed box."""
    detector = DarvasBoxDetector(
        lookback_period=5,
        confirmation_bars=3,
        max_boxes=10,
    )
    # 5 warmup bars under 105
    for i in range(5):
        detector.update(
            make_bar(100.0, 104.0, 99.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        )

    idx = 5
    # New high at 110
    detector.update(make_bar(105.0, 110.0, 104.0, 109.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # 3 confirmation bars that don't exceed 110
    for i in range(3):
        detector.update(
            make_bar(108.0, 109.0, 106.0, 107.0, ts_ns=_BASE_TS + (idx + i) * _1H_NS)
        )
    idx += 3

    levels = detector.levels()
    assert len(levels) >= 2, f"Expected at least 2 levels (top+bottom), got {len(levels)}"

    for lvl in levels:
        assert lvl.source == "darvas_box"
        assert isinstance(lvl.meta, DarvasBoxMeta)
        assert lvl.meta.confirmed is True
        assert lvl.meta.box_top == 110.0
        assert lvl.meta.bars_in_box >= 3
        assert 0.0 < lvl.strength <= 1.0


def test_box_top_and_bottom_emitted():
    """Both box top and box bottom should be emitted as levels."""
    detector = DarvasBoxDetector(
        lookback_period=5,
        confirmation_bars=3,
        max_boxes=10,
    )
    for i in range(5):
        detector.update(
            make_bar(100.0, 104.0, 99.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        )

    idx = 5
    detector.update(make_bar(105.0, 110.0, 104.0, 109.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    for i in range(3):
        detector.update(
            make_bar(108.0, 109.0, 106.0, 107.0, ts_ns=_BASE_TS + (idx + i) * _1H_NS)
        )

    levels = detector.levels()
    prices = {lvl.price for lvl in levels}
    assert 110.0 in prices, "Box top should be a level"
    # Box bottom = lowest low during consolidation (104.0 from the new-high bar)
    assert 104.0 in prices, f"Box bottom should be a level, got prices: {prices}"


def test_no_confirmation_no_box():
    """If price exceeds the candidate top during confirmation, no box is formed yet."""
    detector = DarvasBoxDetector(
        lookback_period=5,
        confirmation_bars=3,
        max_boxes=10,
    )
    for i in range(5):
        detector.update(
            make_bar(100.0, 104.0, 99.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        )

    idx = 5
    # New high
    detector.update(make_bar(105.0, 110.0, 104.0, 109.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Only 1 confirmation bar, then exceed
    detector.update(make_bar(108.0, 109.0, 106.0, 107.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # Exceeds the candidate top
    detector.update(make_bar(109.0, 112.0, 108.0, 111.0, ts_ns=_BASE_TS + idx * _1H_NS))
    idx += 1

    # No confirmed box yet (pending restarted with new high=112)
    assert len(detector.levels()) == 0


def test_max_boxes_limit():
    """Should not exceed max_boxes."""
    detector = DarvasBoxDetector(
        lookback_period=3,
        confirmation_bars=2,
        max_boxes=2,
    )
    base_price = 100.0
    idx = 0

    for box_num in range(4):
        p = base_price + box_num * 20.0
        # Warmup bars below new high
        for i in range(3):
            detector.update(
                make_bar(p, p + 3.0, p - 1.0, p + 1.0, ts_ns=_BASE_TS + idx * _1H_NS)
            )
            idx += 1

        # New high
        new_high = p + 10.0
        detector.update(
            make_bar(p + 5.0, new_high, p + 4.0, new_high - 1.0, ts_ns=_BASE_TS + idx * _1H_NS)
        )
        idx += 1

        # Confirmation bars
        for i in range(2):
            detector.update(
                make_bar(
                    new_high - 2.0, new_high - 1.0, new_high - 4.0, new_high - 2.0,
                    ts_ns=_BASE_TS + idx * _1H_NS,
                )
            )
            idx += 1

    # Should have at most max_boxes boxes (2 boxes = 4 levels: top+bottom each)
    levels = detector.levels()
    box_count = len(levels) // 2
    assert box_count <= 2


def test_deterministic():
    detector_a = DarvasBoxDetector(lookback_period=5, confirmation_bars=3)
    detector_b = DarvasBoxDetector(lookback_period=5, confirmation_bars=3)

    bars = []
    for i in range(5):
        bars.append(make_bar(100.0, 104.0, 99.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS))
    bars.append(make_bar(105.0, 110.0, 104.0, 109.0, ts_ns=_BASE_TS + 5 * _1H_NS))
    for i in range(3):
        bars.append(make_bar(108.0, 109.0, 106.0, 107.0, ts_ns=_BASE_TS + (6 + i) * _1H_NS))

    for bar in bars:
        detector_a.update(bar)
        detector_b.update(bar)

    assert detector_a.levels() == detector_b.levels()


def test_reset():
    detector = DarvasBoxDetector(lookback_period=5, confirmation_bars=3)

    for i in range(5):
        detector.update(make_bar(100.0, 104.0, 99.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS))
    detector.update(make_bar(105.0, 110.0, 104.0, 109.0, ts_ns=_BASE_TS + 5 * _1H_NS))
    for i in range(3):
        detector.update(make_bar(108.0, 109.0, 106.0, 107.0, ts_ns=_BASE_TS + (6 + i) * _1H_NS))

    assert len(detector.levels()) >= 2
    detector.reset()
    assert detector.levels() == []
