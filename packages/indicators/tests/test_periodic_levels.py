"""Tests for PeriodicLevelDetector."""

from indicators.key_levels.detectors.periodic_levels import PeriodicLevelDetector
from indicators.key_levels.model import PeriodicLevelMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _feed_bars(detector, bars):
    for bar in bars:
        detector.update(bar)


def test_no_levels_before_first_period_completes():
    detector = PeriodicLevelDetector(periods=("daily",))
    # Feed bars for a single day — no completed period yet
    for i in range(12):
        bar = make_bar(100.0, 102.0, 98.0, 100.5, ts_ns=_BASE_TS + i * _1H_NS)
        detector.update(bar)
    assert detector.levels() == []


def test_finds_daily_levels_after_day_rolls():
    detector = PeriodicLevelDetector(periods=("daily",))

    # Day 1: 24 bars, hour 0-23 — prices vary
    for i in range(24):
        if i == 5:
            bar = make_bar(100.0, 110.0, 98.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        elif i == 10:
            bar = make_bar(100.0, 102.0, 90.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        elif i == 23:
            bar = make_bar(100.0, 105.0, 98.0, 105.0, ts_ns=_BASE_TS + i * _1H_NS)
        else:
            bar = make_bar(100.0, 102.0, 98.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        detector.update(bar)

    # Day 2: first bar triggers the period rollover
    day2_ts = _BASE_TS + 24 * _1H_NS
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=day2_ts)
    detector.update(bar)

    levels = detector.levels()
    assert len(levels) == 3, f"Expected 3 levels (H/L/C), got {len(levels)}"

    highs = [lv for lv in levels if lv.meta.level_type == "high"]
    lows = [lv for lv in levels if lv.meta.level_type == "low"]
    closes = [lv for lv in levels if lv.meta.level_type == "close"]

    assert len(highs) == 1
    assert len(lows) == 1
    assert len(closes) == 1
    assert highs[0].price == 110.0
    assert lows[0].price == 90.0
    assert closes[0].price == 105.0
    assert highs[0].strength == 0.8
    assert closes[0].strength == 0.6
    assert highs[0].source == "periodic_level"
    assert isinstance(highs[0].meta, PeriodicLevelMeta)
    assert highs[0].meta.period == "daily"


def test_weekly_levels():
    detector = PeriodicLevelDetector(periods=("weekly",))

    # _BASE_TS is 2024-01-01 (Monday). Feed 7 full days + 1 bar of next week.
    bars_per_day = 24
    for day in range(7):
        for hour in range(bars_per_day):
            idx = day * bars_per_day + hour
            high = 120.0 if day == 3 and hour == 5 else 102.0
            low = 80.0 if day == 5 and hour == 10 else 98.0
            close = 100.0
            ts = _BASE_TS + idx * _1H_NS
            bar = make_bar(100.0, high, low, close, ts_ns=ts)
            detector.update(bar)

    # Next week's first bar
    next_week_ts = _BASE_TS + 7 * 24 * _1H_NS
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=next_week_ts)
    detector.update(bar)

    levels = detector.levels()
    assert len(levels) == 3
    highs = [lv for lv in levels if lv.meta.level_type == "high"]
    assert highs[0].price == 120.0


def test_multiple_periods():
    detector = PeriodicLevelDetector(periods=("daily", "weekly"))

    # Feed 7 full days + 1 bar of next week
    bars_per_day = 24
    for day in range(7):
        for hour in range(bars_per_day):
            idx = day * bars_per_day + hour
            ts = _BASE_TS + idx * _1H_NS
            bar = make_bar(100.0, 102.0, 98.0, 100.5, ts_ns=ts)
            detector.update(bar)

    # Next week's first bar triggers both daily and weekly rollover
    next_week_ts = _BASE_TS + 7 * 24 * _1H_NS
    bar = make_bar(100.0, 101.0, 99.0, 100.0, ts_ns=next_week_ts)
    detector.update(bar)

    levels = detector.levels()
    daily_levels = [lv for lv in levels if lv.meta.period == "daily"]
    weekly_levels = [lv for lv in levels if lv.meta.period == "weekly"]
    assert len(daily_levels) == 3
    assert len(weekly_levels) == 3


def test_deterministic():
    bars = []
    for i in range(30):
        bars.append(make_bar(100.0, 102.0, 98.0, 100.5, ts_ns=_BASE_TS + i * _1H_NS))

    det_a = PeriodicLevelDetector(periods=("daily",))
    det_b = PeriodicLevelDetector(periods=("daily",))
    _feed_bars(det_a, bars)
    _feed_bars(det_b, bars)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = PeriodicLevelDetector(periods=("daily",))
    # Feed 25 bars (crosses day boundary)
    for i in range(25):
        bar = make_bar(100.0, 102.0, 98.0, 100.5, ts_ns=_BASE_TS + i * _1H_NS)
        detector.update(bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
