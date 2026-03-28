"""Tests for PivotPointDetector."""

import pytest

from indicators.key_levels.detectors.pivot_points import PivotPointDetector
from indicators.key_levels.model import PivotPointMeta
from tests.helpers.bar_factory import make_bar, _BASE_TS, _1H_NS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Simple known values: O=100, H=110, L=90, C=105
_O, _H, _L, _C = 100.0, 110.0, 90.0, 105.0
_RANGE = _H - _L  # 20


def _make_period_bars(
    period_bars: int,
    o: float = _O,
    h: float = _H,
    lo: float = _L,
    c: float = _C,
    start_ts: int = _BASE_TS,
) -> list:
    """Create *period_bars* bars whose aggregate OHLC matches the given values.

    First bar carries the period high, last bar carries the period low.
    Each bar satisfies NautilusTrader's constraint: high >= max(open, close)
    and low <= min(open, close).
    """
    mid = (h + lo) / 2
    bars = []
    for i in range(period_bars):
        if i == 0:
            # First bar: open=o, high=h (period high), stay mid-range
            bar_o, bar_c = o, mid
            bar_h = max(h, bar_o, bar_c)
            bar_l = min(lo, bar_o, bar_c) if period_bars == 1 else min(bar_o, bar_c) - 0.5
        elif i == period_bars - 1:
            # Last bar: close=c, low=lo (period low)
            bar_o, bar_c = mid, c
            bar_h = max(bar_o, bar_c) + 0.5
            bar_l = min(lo, bar_o, bar_c)
        else:
            bar_o, bar_c = mid, mid
            bar_h = mid + 1
            bar_l = mid - 1
        bars.append(make_bar(bar_o, bar_h, bar_l, bar_c, ts_ns=start_ts + i * _1H_NS))
    return bars


def _feed(detector, bars):
    for bar in bars:
        detector.update(bar)


def _level_dict(levels) -> dict[str, float]:
    """Map level_name -> price for easy assertions."""
    return {lv.meta.level_name: lv.price for lv in levels}


# ---------------------------------------------------------------------------
# 1. No levels before first period completes
# ---------------------------------------------------------------------------


def test_no_levels_before_period_completes():
    det = PivotPointDetector(variant="standard", period_bars=4, atr_period=2)
    # Feed only 3 of the required 4 bars
    bars = _make_period_bars(4)[:3]
    _feed(det, bars)
    assert det.levels() == []


# ---------------------------------------------------------------------------
# 2. Standard variant
# ---------------------------------------------------------------------------


def test_standard_variant_values():
    det = PivotPointDetector(variant="standard", period_bars=4, atr_period=2)
    bars = _make_period_bars(4)
    _feed(det, bars)

    lvls = _level_dict(det.levels())

    pp = (_H + _L + _C) / 3  # (110+90+105)/3 = 101.6667
    assert lvls["PP"] == pytest.approx(pp)
    assert lvls["R1"] == pytest.approx(2 * pp - _L)
    assert lvls["S1"] == pytest.approx(2 * pp - _H)
    assert lvls["R2"] == pytest.approx(pp + _RANGE)
    assert lvls["S2"] == pytest.approx(pp - _RANGE)

    # 5 levels total
    assert len(det.levels()) == 5


# ---------------------------------------------------------------------------
# 3. Fibonacci variant
# ---------------------------------------------------------------------------


def test_fibonacci_variant():
    det = PivotPointDetector(variant="fibonacci", period_bars=4, atr_period=2)
    _feed(det, _make_period_bars(4))

    levels = det.levels()
    lvls = _level_dict(levels)
    pp = (_H + _L + _C) / 3

    assert len(levels) == 7  # PP + R1-R3 + S1-S3
    assert lvls["PP"] == pytest.approx(pp)
    assert lvls["R1"] == pytest.approx(pp + 0.382 * _RANGE)
    assert lvls["R2"] == pytest.approx(pp + 0.618 * _RANGE)
    assert lvls["R3"] == pytest.approx(pp + 1.0 * _RANGE)
    assert lvls["S1"] == pytest.approx(pp - 0.382 * _RANGE)
    assert lvls["S2"] == pytest.approx(pp - 0.618 * _RANGE)
    assert lvls["S3"] == pytest.approx(pp - 1.0 * _RANGE)


# ---------------------------------------------------------------------------
# 4. Camarilla variant
# ---------------------------------------------------------------------------


def test_camarilla_variant():
    det = PivotPointDetector(variant="camarilla", period_bars=4, atr_period=2)
    _feed(det, _make_period_bars(4))

    levels = det.levels()
    lvls = _level_dict(levels)

    # 9 levels: PP + R1-R4 + S1-S4
    assert len(levels) == 9
    assert lvls["R1"] == pytest.approx(_C + _RANGE * 1.1 / 12)
    assert lvls["R2"] == pytest.approx(_C + _RANGE * 1.1 / 6)
    assert lvls["R3"] == pytest.approx(_C + _RANGE * 1.1 / 4)
    assert lvls["R4"] == pytest.approx(_C + _RANGE * 1.1 / 2)
    assert lvls["S1"] == pytest.approx(_C - _RANGE * 1.1 / 12)
    assert lvls["S2"] == pytest.approx(_C - _RANGE * 1.1 / 6)
    assert lvls["S3"] == pytest.approx(_C - _RANGE * 1.1 / 4)
    assert lvls["S4"] == pytest.approx(_C - _RANGE * 1.1 / 2)


# ---------------------------------------------------------------------------
# 5. Woodie variant (PP differs from standard)
# ---------------------------------------------------------------------------


def test_woodie_variant():
    det = PivotPointDetector(variant="woodie", period_bars=4, atr_period=2)
    _feed(det, _make_period_bars(4))

    lvls = _level_dict(det.levels())

    pp_woodie = (_H + _L + 2 * _C) / 4  # (110+90+210)/4 = 102.5
    pp_standard = (_H + _L + _C) / 3     # 101.6667

    assert lvls["PP"] == pytest.approx(pp_woodie)
    assert lvls["PP"] != pytest.approx(pp_standard)
    assert lvls["R1"] == pytest.approx(2 * pp_woodie - _L)
    assert lvls["S1"] == pytest.approx(2 * pp_woodie - _H)


# ---------------------------------------------------------------------------
# 6. DeMark variant (conditional formula)
# ---------------------------------------------------------------------------


def test_demark_close_gt_open():
    """When C > O: X = 2*H + L + C."""
    det = PivotPointDetector(variant="demark", period_bars=4, atr_period=2)
    # C=105 > O=100
    _feed(det, _make_period_bars(4, o=100, h=110, lo=90, c=105))

    lvls = _level_dict(det.levels())
    x = 2 * 110 + 90 + 105  # 415
    assert lvls["PP"] == pytest.approx(x / 4)
    assert lvls["R1"] == pytest.approx(x / 2 - 90)
    assert lvls["S1"] == pytest.approx(x / 2 - 110)


def test_demark_close_lt_open():
    """When C < O: X = H + 2*L + C."""
    det = PivotPointDetector(variant="demark", period_bars=4, atr_period=2)
    # C=95 < O=100
    _feed(det, _make_period_bars(4, o=100, h=110, lo=90, c=95))

    lvls = _level_dict(det.levels())
    x = 110 + 2 * 90 + 95  # 385
    assert lvls["PP"] == pytest.approx(x / 4)
    assert lvls["R1"] == pytest.approx(x / 2 - 90)
    assert lvls["S1"] == pytest.approx(x / 2 - 110)


def test_demark_close_eq_open():
    """When C == O: X = H + L + 2*C."""
    det = PivotPointDetector(variant="demark", period_bars=4, atr_period=2)
    # C == O == 100
    _feed(det, _make_period_bars(4, o=100, h=110, lo=90, c=100))

    lvls = _level_dict(det.levels())
    x = 110 + 90 + 2 * 100  # 400
    assert lvls["PP"] == pytest.approx(x / 4)


# ---------------------------------------------------------------------------
# 7. Levels update when new period completes
# ---------------------------------------------------------------------------


def test_levels_update_on_new_period():
    det = PivotPointDetector(variant="standard", period_bars=4, atr_period=2)

    # First period
    bars1 = _make_period_bars(4, h=110, lo=90, c=105)
    _feed(det, bars1)
    lvls1 = _level_dict(det.levels())

    # Second period with different OHLC
    bars2 = _make_period_bars(4, h=120, lo=95, c=115, start_ts=_BASE_TS + 4 * _1H_NS)
    _feed(det, bars2)
    lvls2 = _level_dict(det.levels())

    # PP should change because OHLC changed
    assert lvls2["PP"] != pytest.approx(lvls1["PP"])
    expected_pp = (120 + 95 + 115) / 3
    assert lvls2["PP"] == pytest.approx(expected_pp)


# ---------------------------------------------------------------------------
# 8. Deterministic
# ---------------------------------------------------------------------------


def test_deterministic():
    bars = _make_period_bars(4)
    det_a = PivotPointDetector(variant="fibonacci", period_bars=4, atr_period=2)
    det_b = PivotPointDetector(variant="fibonacci", period_bars=4, atr_period=2)
    _feed(det_a, bars)
    _feed(det_b, bars)
    assert det_a.levels() == det_b.levels()


# ---------------------------------------------------------------------------
# 9. Reset
# ---------------------------------------------------------------------------


def test_reset_clears_state():
    det = PivotPointDetector(variant="standard", period_bars=4, atr_period=2)
    _feed(det, _make_period_bars(4))
    assert len(det.levels()) > 0

    det.reset()
    assert det.levels() == []


# ---------------------------------------------------------------------------
# Source and meta
# ---------------------------------------------------------------------------


def test_source_and_meta():
    det = PivotPointDetector(variant="camarilla", period_bars=4, atr_period=2)
    _feed(det, _make_period_bars(4))

    for lv in det.levels():
        assert lv.source == "pivot_camarilla"
        assert isinstance(lv.meta, PivotPointMeta)
        assert lv.meta.variant == "camarilla"
        assert lv.meta.period_high == pytest.approx(_H)
        assert lv.meta.period_low == pytest.approx(_L)
        assert lv.meta.period_close == pytest.approx(_C)
        assert lv.bounce_count == 0


def test_name_property():
    for variant in ("standard", "fibonacci", "camarilla", "woodie", "demark"):
        det = PivotPointDetector(variant=variant, period_bars=4)
        assert det.name == f"pivot_{variant}"


def test_strength_values():
    det = PivotPointDetector(variant="standard", period_bars=4, atr_period=2)
    _feed(det, _make_period_bars(4))

    strength_map = {lv.meta.level_name: lv.strength for lv in det.levels()}
    assert strength_map["PP"] == 1.0
    assert strength_map["R1"] == 0.8
    assert strength_map["S1"] == 0.8
    assert strength_map["R2"] == 0.6
    assert strength_map["S2"] == 0.6
