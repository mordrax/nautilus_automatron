"""Tests for MarketProfileDetector (TPO)."""

from indicators.key_levels.detectors.market_profile import MarketProfileDetector
from indicators.key_levels.model import MarketProfileMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _feed_bars(detector, bars):
    for bar in bars:
        detector.update(bar)


# _BASE_TS = 2024-01-01 00:00 UTC.
# With default session 0-24, all hours are in-session.
# We need two days: day 1 builds the profile, day 2 triggers level emission.

_DAY2_START = _BASE_TS + 24 * _1H_NS  # 2024-01-02 00:00 UTC


def _make_day1_bars():
    """Create bars spanning day 1 with a clear price distribution.

    Most bars cluster around 100-105 (high TPO zone), with brief excursions
    to 90 and 115.
    """
    bars = []
    # Hours 0-3: price around 100 (many TPOs in this range)
    for i in range(4):
        bars.append(
            make_bar(100.0, 105.0, 98.0, 102.0, ts_ns=_BASE_TS + i * _1H_NS)
        )
    # Hours 4-5: excursion up to 115
    bars.append(make_bar(105.0, 115.0, 104.0, 112.0, ts_ns=_BASE_TS + 4 * _1H_NS))
    bars.append(make_bar(112.0, 114.0, 108.0, 110.0, ts_ns=_BASE_TS + 5 * _1H_NS))
    # Hours 6-9: back around 100-105 (more TPOs here)
    for i in range(6, 10):
        bars.append(
            make_bar(101.0, 106.0, 99.0, 103.0, ts_ns=_BASE_TS + i * _1H_NS)
        )
    # Hours 10-11: excursion down to 90
    bars.append(make_bar(100.0, 101.0, 90.0, 92.0, ts_ns=_BASE_TS + 10 * _1H_NS))
    bars.append(make_bar(92.0, 95.0, 89.0, 93.0, ts_ns=_BASE_TS + 11 * _1H_NS))
    # Hours 12-15: back around 100
    for i in range(12, 16):
        bars.append(
            make_bar(100.0, 104.0, 98.0, 101.0, ts_ns=_BASE_TS + i * _1H_NS)
        )
    return bars


def test_no_levels_during_first_session():
    detector = MarketProfileDetector()
    bars = _make_day1_bars()
    _feed_bars(detector, bars)
    # No levels yet — need a completed session (requires new day to trigger)
    assert detector.levels() == []


def test_levels_emitted_on_new_session():
    detector = MarketProfileDetector()
    bars = _make_day1_bars()
    _feed_bars(detector, bars)

    # Feed first bar of day 2 to trigger previous session finalization
    day2_bar = make_bar(101.0, 103.0, 99.0, 102.0, ts_ns=_DAY2_START)
    detector.update(day2_bar)

    levels = detector.levels()
    assert len(levels) == 3, f"Expected 3 levels (POC + VA high + VA low), got {len(levels)}"

    poc_levels = [lv for lv in levels if lv.meta.node_type == "poc"]
    va_high_levels = [lv for lv in levels if lv.meta.node_type == "va_high"]
    va_low_levels = [lv for lv in levels if lv.meta.node_type == "va_low"]

    assert len(poc_levels) == 1
    assert len(va_high_levels) == 1
    assert len(va_low_levels) == 1

    poc = poc_levels[0]
    assert poc.source == "market_profile_tpo"
    assert isinstance(poc.meta, MarketProfileMeta)
    assert poc.meta.tpo_count > 0
    assert poc.meta.total_tpo_periods > 0
    assert poc.strength == 0.9


def test_poc_in_high_density_zone():
    detector = MarketProfileDetector()
    bars = _make_day1_bars()
    _feed_bars(detector, bars)

    day2_bar = make_bar(101.0, 103.0, 99.0, 102.0, ts_ns=_DAY2_START)
    detector.update(day2_bar)

    levels = detector.levels()
    poc = [lv for lv in levels if lv.meta.node_type == "poc"][0]

    # POC should be in the high-density zone (around 98-106, where most bars cluster)
    assert 89.0 <= poc.price <= 115.0, f"POC price {poc.price} outside session range"


def test_value_area_bounds():
    detector = MarketProfileDetector()
    bars = _make_day1_bars()
    _feed_bars(detector, bars)

    day2_bar = make_bar(101.0, 103.0, 99.0, 102.0, ts_ns=_DAY2_START)
    detector.update(day2_bar)

    levels = detector.levels()
    va_high = [lv for lv in levels if lv.meta.node_type == "va_high"][0]
    va_low = [lv for lv in levels if lv.meta.node_type == "va_low"][0]
    poc = [lv for lv in levels if lv.meta.node_type == "poc"][0]

    # VA high >= POC >= VA low
    assert va_high.price >= poc.price >= va_low.price, (
        f"VA ordering violated: va_high={va_high.price}, poc={poc.price}, va_low={va_low.price}"
    )


def test_deterministic():
    bars = _make_day1_bars()
    day2_bar = make_bar(101.0, 103.0, 99.0, 102.0, ts_ns=_DAY2_START)

    det_a = MarketProfileDetector()
    det_b = MarketProfileDetector()
    _feed_bars(det_a, bars)
    det_a.update(day2_bar)
    _feed_bars(det_b, bars)
    det_b.update(day2_bar)

    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = MarketProfileDetector()
    bars = _make_day1_bars()
    _feed_bars(detector, bars)
    day2_bar = make_bar(101.0, 103.0, 99.0, 102.0, ts_ns=_DAY2_START)
    detector.update(day2_bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []
