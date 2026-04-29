"""Integration test composing MaConfluenceDetector and WyckoffZoneDetector."""

from indicators.key_levels.detectors import MaConfluenceDetector, WyckoffZoneDetector
from indicators.key_levels.model import MaConfluenceMeta, WyckoffZoneMeta
from tests.helpers.bar_factory import make_bar, make_bars_from_closes, _BASE_TS, _1H_NS


def test_composite_detectors_produce_independent_levels():
    """Both detectors run on the same bar stream and produce independent levels."""
    ma_det = MaConfluenceDetector(
        ma_periods=(5, 10, 20),
        min_converging=3,
        spread_threshold=0.5,
        atr_period=5,
    )
    wyckoff_det = WyckoffZoneDetector(
        volume_period=20,
        swing_period=10,
        atr_period=14,
    )

    # Phase 1: flat bars to warm up both detectors
    flat_bars = make_bars_from_closes(
        [100.0] * 30,
        volume=100.0,
        start_ts=_BASE_TS,
    )
    for bar in flat_bars:
        ma_det.update(bar)
        wyckoff_det.update(bar)

    # MA confluence should detect convergence on flat data
    ma_levels = ma_det.levels()
    assert len(ma_levels) >= 1
    assert all(isinstance(lvl.meta, MaConfluenceMeta) for lvl in ma_levels)
    assert all(0.0 <= lvl.strength <= 1.0 for lvl in ma_levels)
    assert all(lvl.zone_lower <= lvl.price <= lvl.zone_upper for lvl in ma_levels)

    # Wyckoff should have no events on flat, normal-volume bars
    assert wyckoff_det.levels() == []

    # Phase 2: selling climax bar triggers Wyckoff but disrupts MA confluence
    sc_bar = make_bar(
        100.0, 101.0, 92.0, 93.0,
        volume=300.0,
        ts_ns=_BASE_TS + 30 * _1H_NS,
    )
    wyckoff_det.update(sc_bar)

    wyckoff_levels = wyckoff_det.levels()
    assert len(wyckoff_levels) == 1
    assert isinstance(wyckoff_levels[0].meta, WyckoffZoneMeta)
    assert wyckoff_levels[0].meta.event == "sc"
    assert wyckoff_levels[0].source == "wyckoff_zone"
    assert 0.0 < wyckoff_levels[0].strength <= 0.9
    assert wyckoff_levels[0].zone_lower <= wyckoff_levels[0].price <= wyckoff_levels[0].zone_upper

    # Both detector types produced levels at different points in the stream
    all_sources = {lvl.source for lvl in ma_levels + wyckoff_levels}
    assert "ma_confluence" in all_sources
    assert "wyckoff_zone" in all_sources


def test_composite_reset_independence():
    """Resetting one detector does not affect the other."""
    ma_det = MaConfluenceDetector(ma_periods=(5, 10, 20), atr_period=5)
    wyckoff_det = WyckoffZoneDetector(volume_period=20, swing_period=10, atr_period=14)

    # Flat bars give MA confluence; we need separate SC bar for Wyckoff
    flat_bars = make_bars_from_closes([100.0] * 30, volume=100.0)
    for bar in flat_bars:
        ma_det.update(bar)
        wyckoff_det.update(bar)

    # MA has levels on flat data
    assert len(ma_det.levels()) > 0

    # SC bar for Wyckoff (only feed to wyckoff to preserve MA confluence)
    sc_bar = make_bar(100.0, 101.0, 92.0, 93.0, volume=300.0, ts_ns=_BASE_TS + 30 * _1H_NS)
    wyckoff_det.update(sc_bar)
    assert len(wyckoff_det.levels()) > 0

    # Reset MA — Wyckoff unaffected
    ma_det.reset()
    assert ma_det.levels() == []
    assert len(wyckoff_det.levels()) > 0
