"""Tests for agglomerative clustering utility."""

import pytest

from indicators.key_levels.shared.clustering import agglomerative_cluster


def test_empty_input():
    assert agglomerative_cluster([], merge_distance=1.0) == []


def test_single_value():
    result = agglomerative_cluster([100.0], merge_distance=1.0)
    assert len(result) == 1
    assert result[0] == ([100.0], 100.0)


def test_two_close_values_merge():
    result = agglomerative_cluster([100.0, 100.3], merge_distance=0.5)
    assert len(result) == 1
    prices, centroid = result[0]
    assert set(prices) == {100.0, 100.3}
    assert centroid == pytest.approx(100.15, abs=0.01)


def test_two_far_values_stay_separate():
    result = agglomerative_cluster([100.0, 110.0], merge_distance=0.5)
    assert len(result) == 2


def test_three_clusters():
    values = [99.8, 100.0, 100.2, 109.9, 110.1, 119.8, 120.0, 120.3]
    result = agglomerative_cluster(values, merge_distance=1.0)
    assert len(result) == 3
    centroids = sorted(c for _, c in result)
    assert centroids[0] == pytest.approx(100.0, abs=0.5)
    assert centroids[1] == pytest.approx(110.0, abs=0.5)
    assert centroids[2] == pytest.approx(120.0, abs=0.5)


def test_all_same_value():
    result = agglomerative_cluster([100.0, 100.0, 100.0], merge_distance=0.5)
    assert len(result) == 1
    prices, centroid = result[0]
    assert len(prices) == 3
    assert centroid == 100.0


def test_deterministic():
    values = [99.8, 100.0, 100.2, 109.9, 110.1]
    result_a = agglomerative_cluster(values, merge_distance=1.0)
    result_b = agglomerative_cluster(values, merge_distance=1.0)
    assert result_a == result_b
