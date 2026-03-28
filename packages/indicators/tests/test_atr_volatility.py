"""Tests for AtrVolatilityDetector."""

import math

from indicators.key_levels.detectors.atr_volatility import AtrVolatilityDetector
from indicators.key_levels.model import AtrVolatilityMeta
from tests.helpers.bar_factory import make_bars_from_closes, _BASE_TS, _1H_NS


def _warmup_bars(count: int = 14) -> list:
    """Create bars with stable prices for ATR warmup."""
    return make_bars_from_closes(
        [100.0] * count,
        start_ts=_BASE_TS,
        interval_ns=_1H_NS,
    )


class TestAtrVolatilityDetector:

    def test_no_levels_before_warmup(self):
        det = AtrVolatilityDetector(atr_period=14)
        bars = _warmup_bars(14)
        # Feed only 13 bars (not enough for warmup)
        for bar in bars[:13]:
            det.update(bar)
        assert det.levels() == []

    def test_levels_after_warmup(self):
        det = AtrVolatilityDetector(atr_period=14)
        for bar in _warmup_bars(14):
            det.update(bar)
        levels = det.levels()
        # 4 multipliers * 2 (support + resistance) = 8 levels
        assert len(levels) == 8

    def test_correct_count_custom_multipliers(self):
        det = AtrVolatilityDetector(atr_period=14, multipliers=(1.0, 2.0))
        for bar in _warmup_bars(14):
            det.update(bar)
        assert len(det.levels()) == 4

    def test_levels_symmetric_around_close(self):
        det = AtrVolatilityDetector(atr_period=14)
        for bar in _warmup_bars(14):
            det.update(bar)
        levels = det.levels()
        close = 100.0  # last bar close

        # Group by multiplier and check symmetry
        for i in range(0, len(levels), 2):
            resistance = levels[i]
            support = levels[i + 1]
            assert resistance.meta.multiplier == support.meta.multiplier
            r_dist = resistance.price - close
            s_dist = close - support.price
            assert math.isclose(r_dist, s_dist, rel_tol=1e-9)

    def test_higher_multiplier_higher_strength(self):
        det = AtrVolatilityDetector(atr_period=14)
        for bar in _warmup_bars(14):
            det.update(bar)
        levels = det.levels()

        # Extract unique strengths by multiplier
        mult_strength: dict[float, float] = {}
        for level in levels:
            assert isinstance(level.meta, AtrVolatilityMeta)
            mult_strength[level.meta.multiplier] = level.strength

        sorted_mults = sorted(mult_strength.keys())
        for i in range(1, len(sorted_mults)):
            assert mult_strength[sorted_mults[i]] > mult_strength[sorted_mults[i - 1]]

    def test_max_multiplier_has_strength_one(self):
        det = AtrVolatilityDetector(atr_period=14, multipliers=(1.0, 2.0, 3.0))
        for bar in _warmup_bars(14):
            det.update(bar)
        levels = det.levels()
        max_strengths = [
            lv.strength for lv in levels
            if isinstance(lv.meta, AtrVolatilityMeta) and lv.meta.multiplier == 3.0
        ]
        assert all(math.isclose(s, 1.0) for s in max_strengths)

    def test_levels_update_every_bar(self):
        det = AtrVolatilityDetector(atr_period=14)
        bars = make_bars_from_closes(
            [100.0] * 14 + [110.0],
            start_ts=_BASE_TS,
            interval_ns=_1H_NS,
        )
        for bar in bars[:14]:
            det.update(bar)
        levels_before = det.levels()

        det.update(bars[14])
        levels_after = det.levels()

        # Anchor price should have shifted to 110
        assert all(
            isinstance(lv.meta, AtrVolatilityMeta) and lv.meta.anchor_price == 110.0
            for lv in levels_after
        )
        # Prices should differ from before
        prices_before = {lv.price for lv in levels_before}
        prices_after = {lv.price for lv in levels_after}
        assert prices_before != prices_after

    def test_deterministic(self):
        bars = _warmup_bars(14)

        det1 = AtrVolatilityDetector(atr_period=14)
        det2 = AtrVolatilityDetector(atr_period=14)

        for bar in bars:
            det1.update(bar)
            det2.update(bar)

        levels1 = det1.levels()
        levels2 = det2.levels()
        assert len(levels1) == len(levels2)
        for l1, l2 in zip(levels1, levels2):
            assert l1.price == l2.price
            assert l1.strength == l2.strength

    def test_reset_clears_state(self):
        det = AtrVolatilityDetector(atr_period=14)
        for bar in _warmup_bars(14):
            det.update(bar)
        assert len(det.levels()) > 0

        det.reset()
        assert det.levels() == []

        # After reset, should need warmup again
        for bar in _warmup_bars(13):
            det.update(bar)
        assert det.levels() == []

    def test_source_and_meta_types(self):
        det = AtrVolatilityDetector(atr_period=14)
        for bar in _warmup_bars(14):
            det.update(bar)
        for level in det.levels():
            assert level.source == "atr_volatility"
            assert isinstance(level.meta, AtrVolatilityMeta)
            assert level.meta.atr_value > 0
            assert level.meta.multiplier > 0
            assert level.meta.anchor_price > 0

    def test_zone_width_proportional_to_atr(self):
        det = AtrVolatilityDetector(atr_period=14)
        for bar in _warmup_bars(14):
            det.update(bar)
        for level in det.levels():
            assert isinstance(level.meta, AtrVolatilityMeta)
            expected_half = 0.25 * level.meta.atr_value
            assert math.isclose(
                level.zone_upper - level.zone_lower,
                2 * expected_half,
                rel_tol=1e-9,
            )
