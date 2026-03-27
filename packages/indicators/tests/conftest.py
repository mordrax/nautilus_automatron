"""Shared fixtures for indicator tests."""

import pytest

from tests.helpers.bar_factory import (
    make_bar,
    make_bars_from_closes,
    make_bars_from_ohlcv,
)


@pytest.fixture
def make_bar_fn():
    return make_bar


@pytest.fixture
def make_bars_from_closes_fn():
    return make_bars_from_closes


@pytest.fixture
def make_bars_from_ohlcv_fn():
    return make_bars_from_ohlcv
