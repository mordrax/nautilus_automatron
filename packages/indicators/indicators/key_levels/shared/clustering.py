"""Agglomerative clustering for grouping nearby price levels.

Simple 1D bottom-up clustering: start with each value as its own cluster,
iteratively merge the two closest clusters until the minimum distance
between any two clusters exceeds merge_distance.
"""

from __future__ import annotations


def agglomerative_cluster(
    values: list[float],
    merge_distance: float,
) -> list[tuple[list[float], float]]:
    """Cluster 1D values using agglomerative (bottom-up) clustering.

    Args:
        values: List of float values to cluster.
        merge_distance: Maximum distance between cluster centroids to merge.

    Returns:
        List of (members, centroid) tuples, sorted by centroid.
        Each member list contains the original values in that cluster.
    """
    if not values:
        return []

    clusters: list[list[float]] = [[v] for v in sorted(values)]

    while len(clusters) > 1:
        best_dist = float("inf")
        best_idx = -1
        for i in range(len(clusters) - 1):
            centroid_i = sum(clusters[i]) / len(clusters[i])
            centroid_j = sum(clusters[i + 1]) / len(clusters[i + 1])
            dist = abs(centroid_j - centroid_i)
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_dist > merge_distance:
            break

        merged = clusters[best_idx] + clusters[best_idx + 1]
        clusters[best_idx] = merged
        del clusters[best_idx + 1]

    return [
        (members, sum(members) / len(members))
        for members in clusters
    ]
