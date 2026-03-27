"""Tests for KeyLevel data model and metadata types."""

import pytest
from dataclasses import FrozenInstanceError

from indicators.key_levels.model import (
    KeyLevel,
    SwingClusterMeta,
    PivotPointMeta,
    FibonacciMeta,
)


def test_key_level_is_frozen():
    level = KeyLevel(
        price=100.0,
        strength=0.8,
        bounce_count=3,
        first_seen_ts=1000,
        last_touched_ts=2000,
        zone_upper=100.5,
        zone_lower=99.5,
        source="swing_cluster",
        meta=SwingClusterMeta(cluster_radius=0.5, pivot_indices=(1, 5, 12)),
    )
    with pytest.raises(FrozenInstanceError):
        level.price = 101.0  # type: ignore[misc]


def test_key_level_equality():
    meta = SwingClusterMeta(cluster_radius=0.5, pivot_indices=(1, 5))
    level_a = KeyLevel(
        price=100.0, strength=0.8, bounce_count=2,
        first_seen_ts=0, last_touched_ts=100,
        zone_upper=100.5, zone_lower=99.5,
        source="swing_cluster", meta=meta,
    )
    level_b = KeyLevel(
        price=100.0, strength=0.8, bounce_count=2,
        first_seen_ts=0, last_touched_ts=100,
        zone_upper=100.5, zone_lower=99.5,
        source="swing_cluster", meta=meta,
    )
    assert level_a == level_b


def test_key_level_invariants():
    meta = SwingClusterMeta(cluster_radius=0.5, pivot_indices=(1,))
    level = KeyLevel(
        price=100.0, strength=0.8, bounce_count=1,
        first_seen_ts=0, last_touched_ts=100,
        zone_upper=100.5, zone_lower=99.5,
        source="swing_cluster", meta=meta,
    )
    assert level.zone_lower <= level.price <= level.zone_upper
    assert 0.0 <= level.strength <= 1.0
    assert level.first_seen_ts <= level.last_touched_ts
    assert level.bounce_count >= 0


def test_pivot_point_meta():
    meta = PivotPointMeta(
        variant="fibonacci",
        level_name="R1",
        period_high=110.0,
        period_low=90.0,
        period_close=105.0,
    )
    assert meta.variant == "fibonacci"
    assert meta.level_name == "R1"


def test_fibonacci_meta():
    meta = FibonacciMeta(
        ratio=0.618,
        swing_high=110.0,
        swing_low=90.0,
        direction="retracement",
    )
    assert meta.ratio == 0.618
    assert meta.direction == "retracement"


def test_source_literal_accepts_valid_sources():
    meta = SwingClusterMeta(cluster_radius=0.5, pivot_indices=())
    for source in ["swing_cluster", "pivot_standard", "volume_profile"]:
        level = KeyLevel(
            price=100.0, strength=0.5, bounce_count=0,
            first_seen_ts=0, last_touched_ts=0,
            zone_upper=100.5, zone_lower=99.5,
            source=source, meta=meta,
        )
        assert level.source == source
