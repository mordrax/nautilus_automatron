"""Tests for KeyLevel data model and metadata types."""

import pytest
from dataclasses import FrozenInstanceError

from indicators.key_levels.model import (
    EqualHighsLowsMeta,
    FibonacciMeta,
    KeyLevel,
    PivotPointMeta,
)


def _ehl_meta(side: str = "high", touches: int = 2) -> EqualHighsLowsMeta:
    return EqualHighsLowsMeta(
        touch_prices=(100.0, 100.5),
        side=side,  # type: ignore[arg-type]
        touch_count=touches,
    )


def test_key_level_is_frozen():
    level = KeyLevel(
        price=100.0,
        strength=0.8,
        start_ts=1000,
        end_ts=2000,
        source="equal_highs_lows",
        bounce_count=3,
        zone_upper=100.5,
        zone_lower=99.5,
        meta=_ehl_meta(),
    )
    with pytest.raises(FrozenInstanceError):
        level.price = 101.0  # type: ignore[misc]


def test_key_level_equality():
    meta = _ehl_meta()
    level_a = KeyLevel(
        price=100.0, strength=0.8, start_ts=0, end_ts=100,
        source="equal_highs_lows", bounce_count=2,
        zone_upper=100.5, zone_lower=99.5, meta=meta,
    )
    level_b = KeyLevel(
        price=100.0, strength=0.8, start_ts=0, end_ts=100,
        source="equal_highs_lows", bounce_count=2,
        zone_upper=100.5, zone_lower=99.5, meta=meta,
    )
    assert level_a == level_b


def test_key_level_invariants():
    level = KeyLevel(
        price=100.0, strength=0.8, start_ts=0, end_ts=100,
        source="equal_highs_lows", bounce_count=1,
        zone_upper=100.5, zone_lower=99.5, meta=_ehl_meta(),
    )
    assert level.zone_lower is not None and level.zone_upper is not None
    assert level.zone_lower <= level.price <= level.zone_upper
    assert 0.0 <= level.strength <= 1.0
    assert level.start_ts <= (level.end_ts or level.start_ts)
    assert level.bounce_count >= 0


def test_key_level_active_when_end_ts_none():
    level = KeyLevel(
        price=100.0, strength=0.8, start_ts=0, end_ts=None,
        source="equal_highs_lows", bounce_count=2,
        zone_upper=None, zone_lower=None, meta=_ehl_meta(),
    )
    assert level.end_ts is None  # active sentinel


def test_key_level_zone_optional():
    level = KeyLevel(
        price=100.0, strength=0.8, start_ts=0, end_ts=None,
        source="equal_highs_lows", bounce_count=2,
        zone_upper=None, zone_lower=None, meta=_ehl_meta(),
    )
    assert level.zone_upper is None
    assert level.zone_lower is None


def test_pivot_point_meta():
    meta = PivotPointMeta(
        variant="fibonacci",
        level_name="R1",
        period_high=110.0,
        period_low=90.0,
        period_close=105.0,
        side="high",
        touch_count=0,
    )
    assert meta.variant == "fibonacci"
    assert meta.level_name == "R1"
    assert meta.side == "high"
    assert meta.touch_count == 0


def test_fibonacci_meta():
    meta = FibonacciMeta(
        ratio=0.618,
        swing_high=110.0,
        swing_low=90.0,
        direction="retracement",
        side="low",
        touch_count=0,
    )
    assert meta.ratio == 0.618
    assert meta.direction == "retracement"
    assert meta.side == "low"
    assert meta.touch_count == 0


def test_equal_highs_lows_meta_has_touch_count():
    meta = EqualHighsLowsMeta(
        touch_prices=(100.0, 100.2, 100.1),
        side="high",
        touch_count=7,
    )
    assert meta.touch_count == 7
    assert meta.side == "high"
