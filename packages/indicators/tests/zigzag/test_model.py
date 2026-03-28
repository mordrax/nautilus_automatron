"""Tests for ZigZagPivot data model."""

import dataclasses

import pytest

from indicators.zigzag.model import ZigZagPivot


class TestZigZagPivot:
    def test_create_pivot(self):
        pivot = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)

        assert pivot.price == 110.0
        assert pivot.timestamp == 1_000_000
        assert pivot.direction == 1
        assert pivot.bar_index == 5

    def test_frozen_immutability(self):
        pivot = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)

        with pytest.raises(dataclasses.FrozenInstanceError):
            pivot.price = 120.0  # type: ignore[misc]

    def test_equality(self):
        a = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)
        b = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)

        assert a == b

    def test_inequality_different_price(self):
        a = ZigZagPivot(price=110.0, timestamp=1_000_000, direction=1, bar_index=5)
        b = ZigZagPivot(price=115.0, timestamp=1_000_000, direction=1, bar_index=5)

        assert a != b
