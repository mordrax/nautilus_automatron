"""Tests for OpeningRangeDetector."""

from indicators.key_levels.detectors.opening_range import OpeningRangeDetector
from indicators.key_levels.model import OpeningRangeMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _feed_bars(detector, bars):
    for bar in bars:
        detector.update(bar)


# _BASE_TS = 2024-01-01 00:00 UTC.
# With market_open_hour_utc=9, the opening range starts at hour 9.
# With range_minutes=60 (1 hour), the range covers hour 9 only.

_HOUR_9_TS = _BASE_TS + 9 * _1H_NS  # 2024-01-01 09:00 UTC


def test_no_levels_before_range_completes():
    detector = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)
    # Feed one bar at hour 9 — still in range, not locked yet
    bar = make_bar(100.0, 105.0, 95.0, 102.0, ts_ns=_HOUR_9_TS)
    detector.update(bar)
    assert detector.levels() == []


def test_finds_opening_range_levels():
    detector = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)

    # Bar at hour 9 — within opening range
    bar1 = make_bar(100.0, 108.0, 93.0, 102.0, ts_ns=_HOUR_9_TS)
    detector.update(bar1)
    assert detector.levels() == []  # Not locked yet

    # Bar at hour 10 — outside range, should lock the OR
    bar2 = make_bar(102.0, 104.0, 100.0, 103.0, ts_ns=_HOUR_9_TS + _1H_NS)
    detector.update(bar2)

    levels = detector.levels()
    assert len(levels) == 2, f"Expected 2 levels (OR high + low), got {len(levels)}"

    highs = [lv for lv in levels if lv.meta.level_type == "high"]
    lows = [lv for lv in levels if lv.meta.level_type == "low"]

    assert len(highs) == 1
    assert len(lows) == 1
    assert highs[0].price == 108.0
    assert lows[0].price == 93.0
    assert highs[0].strength == 0.8
    assert highs[0].source == "opening_range"
    assert isinstance(highs[0].meta, OpeningRangeMeta)
    assert highs[0].meta.range_minutes == 60


def test_levels_persist_after_lock():
    detector = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)

    # Opening range bar
    bar1 = make_bar(100.0, 108.0, 93.0, 102.0, ts_ns=_HOUR_9_TS)
    detector.update(bar1)

    # Lock bar
    bar2 = make_bar(102.0, 104.0, 100.0, 103.0, ts_ns=_HOUR_9_TS + _1H_NS)
    detector.update(bar2)

    # More bars later in the day — levels should remain
    bar3 = make_bar(103.0, 106.0, 101.0, 104.0, ts_ns=_HOUR_9_TS + 2 * _1H_NS)
    detector.update(bar3)

    levels = detector.levels()
    assert len(levels) == 2
    highs = [lv for lv in levels if lv.meta.level_type == "high"]
    assert highs[0].price == 108.0


def test_resets_on_new_day():
    detector = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)

    # Day 1 opening range
    bar1 = make_bar(100.0, 108.0, 93.0, 102.0, ts_ns=_HOUR_9_TS)
    detector.update(bar1)
    bar2 = make_bar(102.0, 104.0, 100.0, 103.0, ts_ns=_HOUR_9_TS + _1H_NS)
    detector.update(bar2)
    assert len(detector.levels()) == 2

    # Day 2: new day's opening range with different prices
    day2_hour9 = _HOUR_9_TS + 24 * _1H_NS
    bar3 = make_bar(200.0, 220.0, 190.0, 210.0, ts_ns=day2_hour9)
    detector.update(bar3)

    # Day 2 lock
    bar4 = make_bar(210.0, 215.0, 205.0, 212.0, ts_ns=day2_hour9 + _1H_NS)
    detector.update(bar4)

    levels = detector.levels()
    assert len(levels) == 2
    highs = [lv for lv in levels if lv.meta.level_type == "high"]
    assert highs[0].price == 220.0  # Day 2 values


def test_deterministic():
    bars = [
        make_bar(100.0, 108.0, 93.0, 102.0, ts_ns=_HOUR_9_TS),
        make_bar(102.0, 104.0, 100.0, 103.0, ts_ns=_HOUR_9_TS + _1H_NS),
    ]

    det_a = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)
    det_b = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)
    _feed_bars(det_a, bars)
    _feed_bars(det_b, bars)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = OpeningRangeDetector(range_minutes=60, market_open_hour_utc=9)
    bar1 = make_bar(100.0, 108.0, 93.0, 102.0, ts_ns=_HOUR_9_TS)
    bar2 = make_bar(102.0, 104.0, 100.0, 103.0, ts_ns=_HOUR_9_TS + _1H_NS)
    detector.update(bar1)
    detector.update(bar2)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
