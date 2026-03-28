"""Tests for SwingClusterDetector."""


from indicators.key_levels.detectors.swing_cluster import SwingClusterDetector
from indicators.key_levels.model import SwingClusterMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


def _make_swing_bars():
    """Create bars with clear swing highs near 110 and swing lows near 90.

    Pattern: rise to 110, drop to 90, rise to ~109 (clusters with 110),
    drop to ~91 (clusters with 90).
    """
    data = [
        # First swing high at 110
        (100.0, 102.0, 98.0, 101.0, 100.0),
        (101.0, 106.0, 100.0, 105.0, 100.0),
        (105.0, 110.0, 104.0, 108.0, 100.0),   # bar 2 - swing high
        (108.0, 108.0, 100.0, 102.0, 100.0),
        (102.0, 103.0, 95.0, 96.0, 100.0),
        # First swing low at 90
        (96.0, 97.0, 92.0, 93.0, 100.0),
        (93.0, 94.0, 90.0, 91.0, 100.0),        # bar 6 - swing low
        (91.0, 96.0, 91.0, 95.0, 100.0),
        (95.0, 100.0, 94.0, 99.0, 100.0),
        # Second swing high near 110
        (99.0, 104.0, 98.0, 103.0, 100.0),
        (103.0, 109.0, 102.0, 107.0, 100.0),    # bar 10 - swing high
        (107.0, 107.0, 99.0, 101.0, 100.0),
        (101.0, 102.0, 95.0, 97.0, 100.0),
        # Second swing low near 90
        (97.0, 98.0, 93.0, 94.0, 100.0),
        (94.0, 95.0, 91.0, 92.0, 100.0),        # bar 14 - swing low
        (92.0, 97.0, 91.0, 96.0, 100.0),
        (96.0, 100.0, 95.0, 99.0, 100.0),
    ]
    return [
        make_bar(o, h, lo, c, v, ts_ns=_BASE_TS + i * _1H_NS)
        for i, (o, h, lo, c, v) in enumerate(data)
    ]


def test_swing_cluster_no_levels_before_warmup():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bar = make_bar(100.0, 105.0, 95.0, 100.0)
    detector.update(bar)
    assert detector.levels() == []


def test_swing_cluster_finds_levels():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    assert len(levels) > 0
    for level in levels:
        assert level.source == "swing_cluster"
        assert 0.0 <= level.strength <= 1.0
        assert level.zone_lower <= level.price <= level.zone_upper
        assert isinstance(level.meta, SwingClusterMeta)


def test_swing_cluster_strength_increases_with_bounces():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    levels = detector.levels()
    multi_bounce = [lvl for lvl in levels if lvl.bounce_count > 1]
    single_bounce = [lvl for lvl in levels if lvl.bounce_count == 1]
    if multi_bounce and single_bounce:
        assert max(lvl.strength for lvl in multi_bounce) >= max(lvl.strength for lvl in single_bounce)


def test_swing_cluster_deterministic():
    bars = _make_swing_bars()
    det_a = SwingClusterDetector(period=2, cluster_distance=2.0)
    det_b = SwingClusterDetector(period=2, cluster_distance=2.0)
    for bar in bars:
        det_a.update(bar)
        det_b.update(bar)
    assert det_a.levels() == det_b.levels()


def test_swing_cluster_reset():
    detector = SwingClusterDetector(period=2, cluster_distance=2.0)
    bars = _make_swing_bars()
    for bar in bars:
        detector.update(bar)
    assert len(detector.levels()) > 0
    detector.reset()
    assert detector.levels() == []
