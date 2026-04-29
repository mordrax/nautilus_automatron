"""Tests for SessionLevelDetector."""

from indicators.key_levels.detectors.session_levels import SessionLevelDetector
from indicators.key_levels.model import SessionLevelMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _feed_bars(detector, bars):
    for bar in bars:
        detector.update(bar)


def test_no_levels_before_first_session_completes():
    detector = SessionLevelDetector(sessions={"asian": (0, 8)})
    # Feed only 3 bars (hours 0-2), session hasn't ended
    for i in range(3):
        bar = make_bar(100.0, 101.0, 99.0, 100.5, ts_ns=_BASE_TS + i * _1H_NS)
        detector.update(bar)
    assert detector.levels() == []


def test_finds_session_levels_after_session_ends():
    detector = SessionLevelDetector(sessions={"asian": (0, 8)})
    # Feed bars for hours 0-7 (the Asian session) then hour 8 to trigger close
    bars = []
    for i in range(9):  # hours 0 through 8
        # Vary prices so H/L are clear
        high = 105.0 if i == 3 else 101.0
        low = 95.0 if i == 5 else 99.0
        bars.append(make_bar(100.0, high, low, 100.5, ts_ns=_BASE_TS + i * _1H_NS))

    _feed_bars(detector, bars)

    levels = detector.levels()
    assert len(levels) == 2, f"Expected 2 levels (high+low), got {len(levels)}"

    highs = [lv for lv in levels if lv.meta.level_type == "high"]
    lows = [lv for lv in levels if lv.meta.level_type == "low"]
    assert len(highs) == 1
    assert len(lows) == 1
    assert highs[0].price == 105.0
    assert lows[0].price == 95.0
    assert highs[0].source == "session_level"
    assert highs[0].strength == 0.7
    assert isinstance(highs[0].meta, SessionLevelMeta)
    assert highs[0].meta.session == "asian"


def test_multiple_sessions():
    detector = SessionLevelDetector(
        sessions={"early": (0, 4), "late": (4, 8)}
    )
    bars = []
    for i in range(9):  # hours 0 through 8
        if i < 4:
            bars.append(make_bar(100.0, 102.0, 98.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS))
        elif i < 8:
            bars.append(make_bar(110.0, 112.0, 108.0, 110.0, ts_ns=_BASE_TS + i * _1H_NS))
        else:
            bars.append(make_bar(110.0, 111.0, 109.0, 110.0, ts_ns=_BASE_TS + i * _1H_NS))

    _feed_bars(detector, bars)
    levels = detector.levels()
    # Both sessions completed: 2 levels each = 4 total
    assert len(levels) == 4


def test_session_resets_on_new_day():
    detector = SessionLevelDetector(sessions={"asian": (0, 8)})
    # Day 1: hours 0-8
    for i in range(9):
        bar = make_bar(100.0, 103.0, 97.0, 100.0, ts_ns=_BASE_TS + i * _1H_NS)
        detector.update(bar)
    levels_day1 = detector.levels()
    assert len(levels_day1) == 2

    # Day 2: hours 0-8 with different prices
    day2_base = _BASE_TS + 24 * _1H_NS
    for i in range(9):
        high = 115.0 if i == 2 else 111.0
        low = 85.0 if i == 4 else 109.0
        bar = make_bar(110.0, high, low, 110.0, ts_ns=day2_base + i * _1H_NS)
        detector.update(bar)

    levels_day2 = detector.levels()
    # Should now have day 2's session levels (replacing day 1)
    assert len(levels_day2) == 2
    highs = [lv for lv in levels_day2 if lv.meta.level_type == "high"]
    assert highs[0].price == 115.0


def test_deterministic():
    bars = []
    for i in range(10):
        bars.append(make_bar(100.0, 102.0, 98.0, 100.5, ts_ns=_BASE_TS + i * _1H_NS))

    det_a = SessionLevelDetector(sessions={"asian": (0, 8)})
    det_b = SessionLevelDetector(sessions={"asian": (0, 8)})
    _feed_bars(det_a, bars)
    _feed_bars(det_b, bars)
    assert det_a.levels() == det_b.levels()


def test_reset():
    detector = SessionLevelDetector(sessions={"asian": (0, 8)})
    for i in range(9):
        bar = make_bar(100.0, 102.0, 98.0, 100.5, ts_ns=_BASE_TS + i * _1H_NS)
        detector.update(bar)
    assert len(detector.levels()) > 0
    detector.reset()
    assert detector.levels() == []
