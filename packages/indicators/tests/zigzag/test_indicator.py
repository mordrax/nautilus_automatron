"""Tests for ZigZagIndicator."""

import pytest

from indicators.zigzag.indicator import ZigZagIndicator
from tests.helpers.bar_factory import make_bar, make_bars_from_ohlcv, _BASE_TS, _1H_NS


class TestZigZagInstantiation:
    def test_name(self):
        zz = ZigZagIndicator(0.05)
        assert zz.name == "ZigZagIndicator"

    def test_repr_percentage_mode(self):
        zz = ZigZagIndicator(0.05)
        assert str(zz) == "ZigZagIndicator(0.05, PERCENTAGE, 14, PIVOT, 10000)"

    def test_repr_atr_mode(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=20)
        assert str(zz) == "ZigZagIndicator(2.0, ATR, 20, PIVOT, 10000)"

    def test_default_properties(self):
        zz = ZigZagIndicator(0.05)
        assert zz.threshold == 0.05
        assert zz.atr_period == 14
        assert zz.max_pivots == 10000
        assert zz.direction == 0
        assert zz.changed is False
        assert zz.initialized is False
        assert zz.has_inputs is False
        assert zz.pivot_price == 0.0
        assert zz.pivot_timestamp == 0
        assert zz.pivot_direction == 0
        assert zz.tentative_price == 0.0
        assert zz.tentative_timestamp == 0
        assert zz.pivot_count == 0
        assert zz.pivots == []

    def test_unlimited_pivots(self):
        zz = ZigZagIndicator(0.05, max_pivots=0)
        assert zz.max_pivots == 0

    def test_invalid_mode_raises(self):
        with pytest.raises(KeyError):
            ZigZagIndicator(0.05, mode="INVALID")

    def test_invalid_threshold_base_raises(self):
        with pytest.raises(KeyError):
            ZigZagIndicator(0.05, threshold_base="INVALID")

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError):
            ZigZagIndicator(-0.05)

    def test_negative_max_pivots_raises(self):
        with pytest.raises(ValueError):
            ZigZagIndicator(0.05, max_pivots=-1)


class TestZigZagPercentageMode:
    def setup_method(self):
        self.zz = ZigZagIndicator(0.05)  # 5% threshold

    def test_has_inputs_after_first_bar(self):
        bar = make_bar(100.0, 101.0, 99.0, 100.5)
        self.zz.handle_bar(bar)
        assert self.zz.has_inputs is True
        assert self.zz.initialized is False

    def test_first_reversal_from_high(self):
        # Bar 2 has high=110, low=104: 110-104=6 >= 110*0.05=5.5 triggers reversal within that bar.
        # The indicator confirms initial_low (98.0) and then high pivot (110.0) on bar 2.
        # Bar 3 does not trigger another change, so changed=False by end.
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (103.0, 105.0, 100.0, 103.0, 100),
            (107.0, 110.0, 104.0, 107.0, 100),  # reversal confirmed here: high=110, drop to low=104
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.initialized is True
        assert self.zz.changed is True  # changed=True because pivot confirmed on this bar
        assert self.zz.direction == -1
        assert self.zz.pivot_price == 110.0
        assert self.zz.pivot_direction == 1
        assert self.zz.pivot_count == 2  # initial low (98.0) + high pivot (110.0)
        assert self.zz.tentative_price == 104.0

    def test_first_reversal_from_low(self):
        # Price drops to 90, then rises >5% (90 * 0.05 = 4.5)
        # During initialization, the indicator first confirms the initial high (100.0)
        # then the low reversal confirms the low pivot (90.0).
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (95.0, 97.0, 93.0, 95.0, 100),
            (91.0, 92.0, 90.0, 91.0, 100),   # low=90
            (94.0, 95.0, 91.0, 94.0, 100),   # high=95, rise=5 > 4.5
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.initialized is True
        assert self.zz.changed is True
        assert self.zz.direction == 1
        assert self.zz.pivot_price == 90.0
        assert self.zz.pivot_direction == -1
        assert self.zz.pivot_count == 2  # initial high (100.0) + low pivot (90.0)

    def test_extending_tentative_no_confirmation(self):
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # reversal: pivot at 110
            (103.0, 104.0, 102.0, 103.0, 100),   # extends tentative to 102
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.changed is False
        assert self.zz.tentative_price == 102.0
        assert self.zz.pivot_count == 2  # initial low (98.0) + high pivot (110.0)

    def test_full_zigzag_sequence(self):
        # Up to 110, reversal down, down to 100, reversal up
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),   # high=110
            (104.5, 105.0, 104.0, 104.5, 100),    # reversal 1
            (101.0, 103.0, 100.0, 101.0, 100),    # tentative=100
            (105.0, 106.0, 101.0, 105.0, 100),    # reversal 2 (PIVOT base: 110*0.05=5.5, 106>=100+5.5)
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.pivot_count == 3  # initial low (98.0) + high pivot (110.0) + low pivot (100.0)
        assert self.zz.pivot_price == 100.0
        assert self.zz.pivot_direction == -1
        assert self.zz.direction == 1
        assert self.zz.changed is True

    def test_changed_flag_resets_next_bar(self):
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # changed=True
            (104.0, 105.0, 103.0, 104.0, 100),  # next bar
        ])
        for bar in bars:
            self.zz.handle_bar(bar)

        assert self.zz.changed is False


class TestZigZagATRMode:
    def test_not_initialized_until_atr_warmed_up(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=3)
        bars = make_bars_from_ohlcv([
            (100.0, 102.0, 98.0, 100.0, 100),
            (100.0, 101.0, 99.0, 100.0, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.has_inputs is True
        assert zz.initialized is False
        assert zz.direction == 0

    def test_reversal_after_atr_warmup(self):
        # After ATR warms up (bar 2), the indicator initializes with initial_low=98.0 (direction=1).
        # A big enough drop then reverses to direction=-1 and confirms the high pivot.
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=3)
        bars = make_bars_from_ohlcv([
            (100.0, 102.0, 98.0, 100.0, 100),   # TR=4
            (100.0, 101.0, 99.0, 100.0, 100),   # TR=2
            (105.0, 110.0, 100.0, 105.0, 100),  # ATR warmed up; confirms initial_low=98.0, direction=1
            (100.0, 105.0, 98.0, 100.0, 100),   # extends tentative high
            (90.0, 95.0, 88.0, 90.0, 100),      # big drop confirms high pivot
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.initialized is True
        assert zz.direction == -1
        assert zz.pivot_direction == 1
        assert zz.pivot_count >= 2


class TestZigZagThresholdBase:
    def test_tentative_base_easier_reversal(self):
        zz = ZigZagIndicator(0.05, threshold_base="TENTATIVE")
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # pivot at 110
            (101.0, 103.0, 100.0, 101.0, 100),  # tentative=100
            # TENTATIVE: 100*0.05=5.0, need high>=105. With 105.5 => reversal
            (104.0, 105.5, 101.0, 104.0, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_count == 3  # initial low (98.0) + high pivot (110.0) + low pivot (100.0)
        assert zz.direction == 1

    def test_pivot_base_harder_reversal(self):
        zz = ZigZagIndicator(0.05, threshold_base="PIVOT")
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # pivot at 110
            (101.0, 103.0, 100.0, 101.0, 100),  # tentative=100
            # PIVOT: 110*0.05=5.5, need high>=105.5. With 105.0 => NO reversal
            (104.0, 105.0, 101.0, 104.0, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_count == 2  # initial low (98.0) + high pivot (110.0); no second reversal
        assert zz.direction == -1


    def test_atr_mode_ignores_threshold_base(self):
        # ATR mode: threshold is always atr.value * threshold, regardless of threshold_base
        zz_pivot = ZigZagIndicator(2.0, mode="ATR", atr_period=3, threshold_base="PIVOT")
        zz_tentative = ZigZagIndicator(2.0, mode="ATR", atr_period=3, threshold_base="TENTATIVE")

        bars = make_bars_from_ohlcv([
            (100.0, 102.0, 98.0, 100.0, 100),
            (100.0, 101.0, 99.0, 100.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (100.0, 105.0, 98.0, 100.0, 100),
        ])
        for bar in bars:
            zz_pivot.handle_bar(bar)
            zz_tentative.handle_bar(bar)

        # Both should produce identical results
        assert zz_pivot.pivot_count == zz_tentative.pivot_count
        assert zz_pivot.direction == zz_tentative.direction
        assert zz_pivot.pivot_price == zz_tentative.pivot_price


class TestZigZagMaxPivots:
    def test_evicts_oldest_when_full(self):
        zz = ZigZagIndicator(0.05, max_pivots=2)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),    # pivot 1: 110 (high)
            (101.0, 103.0, 100.0, 101.0, 100),
            (105.0, 106.0, 101.0, 105.0, 100),    # pivot 2: 100 (low)
            (112.0, 115.0, 106.0, 112.0, 100),
            (109.0, 112.0, 108.0, 109.0, 100),    # pivot 3: 115 (high)
        ])
        for bar in bars:
            zz.handle_bar(bar)

        pivots = zz.pivots
        # With max_pivots=2, the deque retains the 2 most recent confirmed pivots.
        # Sequence: 98.0 (low), 110.0 (high), 100.0 (low), 115.0 (high), 106.0 (low)
        # After eviction only the last 2 remain.
        assert len(pivots) == 2
        assert pivots[0].price == 115.0
        assert pivots[1].price == 106.0


class TestZigZagEdgeCases:
    def test_tentative_repaints_confirmed_does_not(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),  # pivot at 110
            (102.0, 103.0, 101.0, 102.0, 100),  # tentative extends to 101
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_price == 110.0
        assert zz.tentative_price == 101.0

    def test_timestamp_tracking(self):
        zz = ZigZagIndicator(0.05)
        ts = [_BASE_TS + i * _1H_NS for i in range(5)]
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),   # high=110 at ts[1]
            (104.5, 105.0, 104.0, 104.5, 100),    # reversal at ts[2]
            (102.0, 103.0, 101.0, 102.0, 100),    # tentative extends at ts[3]
        ])
        for bar in bars:
            zz.handle_bar(bar)

        assert zz.pivot_timestamp == ts[1]
        assert zz.tentative_timestamp == ts[3]

    def test_multiple_pivots_in_history(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),    # pivot 1: 110
            (101.0, 103.0, 100.0, 101.0, 100),
            (105.0, 106.0, 101.0, 105.0, 100),    # pivot 2: 100
            (112.0, 115.0, 106.0, 112.0, 100),
            (109.0, 112.0, 108.0, 109.0, 100),    # pivot 3: 115
        ])
        for bar in bars:
            zz.handle_bar(bar)

        pivots = zz.pivots
        # The indicator produces 5 confirmed pivots in this sequence:
        # 98.0 (low, from initialization), 110.0 (high), 100.0 (low), 115.0 (high), 106.0 (low tentative confirmed)
        assert len(pivots) == 5
        assert pivots[0].price == 98.0
        assert pivots[0].direction == -1
        assert pivots[1].price == 110.0
        assert pivots[1].direction == 1
        assert pivots[2].price == 100.0
        assert pivots[2].direction == -1
        assert pivots[3].price == 115.0
        assert pivots[3].direction == 1

    def test_pivots_returns_copy(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)

        pivots = zz.pivots
        original_count = len(pivots)
        pivots.clear()
        assert len(zz.pivots) == original_count  # clearing the copy does not affect the indicator


class TestZigZagReset:
    def test_reset_clears_all_state(self):
        zz = ZigZagIndicator(0.05)
        bars = make_bars_from_ohlcv([
            (99.0, 100.0, 98.0, 99.0, 100),
            (105.0, 110.0, 100.0, 105.0, 100),
            (104.5, 105.0, 104.0, 104.5, 100),
        ])
        for bar in bars:
            zz.handle_bar(bar)
        assert zz.initialized is True

        zz.reset()

        assert zz.has_inputs is False
        assert zz.initialized is False
        assert zz.direction == 0
        assert zz.changed is False
        assert zz.pivot_price == 0.0
        assert zz.pivot_timestamp == 0
        assert zz.pivot_direction == 0
        assert zz.tentative_price == 0.0
        assert zz.tentative_timestamp == 0
        assert zz.pivot_count == 0
        assert zz.pivots == []

    def test_reset_atr_mode(self):
        zz = ZigZagIndicator(2.0, mode="ATR", atr_period=3)
        bar = make_bar(100.0, 102.0, 98.0, 100.0)
        zz.handle_bar(bar)

        zz.reset()

        assert zz.has_inputs is False
        assert zz.initialized is False
