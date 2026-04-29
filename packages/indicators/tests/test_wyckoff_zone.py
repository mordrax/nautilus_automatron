"""Tests for WyckoffZoneDetector."""

from indicators.key_levels.detectors.wyckoff_zone import WyckoffZoneDetector
from indicators.key_levels.model import WyckoffZoneMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_warmup_bars(n: int = 25, volume: float = 100.0):
    """Create N neutral bars for warmup (flat price, average volume)."""
    return [
        make_bar(100.0, 101.0, 99.0, 100.0, volume=volume, ts_ns=_BASE_TS + i * _1H_NS)
        for i in range(n)
    ]


def test_no_levels_before_warmup():
    """No levels emitted before volume/swing/atr buffers are full."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)
    # Feed only 10 bars — not enough for any buffer
    bars = _make_warmup_bars(10)
    for bar in bars:
        detector.update(bar)
    assert detector.levels() == []


def test_selling_climax():
    """Detect a selling climax: large bearish bar + extreme volume."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    # Warmup: 25 bars, ATR ~2.0 (high-low=2.0), avg volume=100
    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    # SC bar: bearish, body > 2*ATR (~4.0), needs body > 4.0; volume > 200
    # open=100, close=93 -> body=7, high=101, low=92
    sc_bar = make_bar(100.0, 101.0, 92.0, 93.0, volume=300.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(sc_bar)

    levels = detector.levels()
    assert len(levels) == 1
    level = levels[0]
    assert level.source == "wyckoff_zone"
    assert isinstance(level.meta, WyckoffZoneMeta)
    assert level.meta.event == "sc"
    assert level.meta.phase == "accumulation"
    assert level.zone_upper == 101.0
    assert level.zone_lower == 92.0
    assert 0.0 < level.strength <= 0.9


def test_buying_climax():
    """Detect a buying climax: large bullish bar + extreme volume."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    # BC bar: bullish, body > 2*ATR, volume > 2x avg
    bc_bar = make_bar(100.0, 108.0, 99.0, 107.0, volume=300.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(bc_bar)

    levels = detector.levels()
    assert len(levels) == 1
    level = levels[0]
    assert level.meta.event == "bc"
    assert level.meta.phase == "distribution"


def test_spring():
    """Detect a spring: dip below recent low then close back above, low volume."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    # Warmup bars with lows at 99.0 (lowest low of the swing_period window)
    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    # Spring bar: low < 99.0 (prior lowest), close > 99.0, volume < 50
    spring_bar = make_bar(100.0, 100.5, 97.0, 99.5, volume=40.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(spring_bar)

    levels = detector.levels()
    assert len(levels) == 1
    level = levels[0]
    assert level.meta.event == "spring"
    assert level.meta.phase == "accumulation"
    assert 0.0 < level.strength <= 0.7


def test_upthrust():
    """Detect an upthrust: spike above recent high then close back below, low volume."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    # Warmup bars with highs at 101.0
    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    # Upthrust bar: high > 101.0, close < 101.0, volume < 50
    ut_bar = make_bar(100.0, 103.0, 99.5, 100.5, volume=40.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(ut_bar)

    levels = detector.levels()
    assert len(levels) == 1
    level = levels[0]
    assert level.meta.event == "upthrust"
    assert level.meta.phase == "distribution"


def test_strength_decays_with_age():
    """Strength should decrease as bars pass after the event."""
    detector = WyckoffZoneDetector(
        volume_period=20, swing_period=10, atr_period=14, max_age_bars=100,
    )

    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    # SC event
    sc_bar = make_bar(100.0, 101.0, 92.0, 93.0, volume=300.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(sc_bar)
    strength_fresh = detector.levels()[0].strength

    # Feed 50 more neutral bars
    for i in range(50):
        neutral = make_bar(100.0, 101.0, 99.0, 100.0, volume=100.0, ts_ns=_BASE_TS + (26 + i) * _1H_NS)
        detector.update(neutral)

    levels = detector.levels()
    assert len(levels) == 1
    assert levels[0].strength < strength_fresh


def test_events_expire_after_max_age():
    """Events older than max_age_bars should be purged."""
    detector = WyckoffZoneDetector(
        volume_period=20, swing_period=10, atr_period=14, max_age_bars=30,
    )

    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    sc_bar = make_bar(100.0, 101.0, 92.0, 93.0, volume=300.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(sc_bar)
    assert len(detector.levels()) == 1

    # Feed 31 more bars to exceed max_age_bars
    for i in range(31):
        neutral = make_bar(100.0, 101.0, 99.0, 100.0, volume=100.0, ts_ns=_BASE_TS + (26 + i) * _1H_NS)
        detector.update(neutral)

    assert detector.levels() == []


def test_deterministic():
    """Two identical detectors produce identical results."""
    bars = _make_warmup_bars(25, volume=100.0)
    sc_bar = make_bar(100.0, 101.0, 92.0, 93.0, volume=300.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    all_bars = bars + [sc_bar]

    det_a = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)
    det_b = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)
    for bar in all_bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_reset():
    """After reset, detector returns no levels and can be reused."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    bars = _make_warmup_bars(25, volume=100.0)
    for bar in bars:
        detector.update(bar)

    sc_bar = make_bar(100.0, 101.0, 92.0, 93.0, volume=300.0, ts_ns=_BASE_TS + 25 * _1H_NS)
    detector.update(sc_bar)
    assert len(detector.levels()) > 0

    detector.reset()
    assert detector.levels() == []


def test_no_event_for_normal_bars():
    """Normal bars should not trigger any Wyckoff events."""
    detector = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    # All bars are neutral — no extreme volume or body
    bars = _make_warmup_bars(40, volume=100.0)
    for bar in bars:
        detector.update(bar)

    assert detector.levels() == []
