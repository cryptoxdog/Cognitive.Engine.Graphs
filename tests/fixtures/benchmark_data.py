"""
Benchmark test data — labeled synthetic pairs for score quality validation.

Each scenario defines a "good pair" (high expected score) and a "bad pair"
(low expected score) for score quality benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkPair:
    """A labeled pair of candidate/query properties for benchmark testing."""

    label: str
    candidate_props: dict
    query_params: dict
    expected_quality: str  # "good" or "bad"


# --- Good pairs: candidates that should score highly ---

GOOD_PAIRS: list[BenchmarkPair] = [
    BenchmarkPair(
        label="geo_close_same_community",
        candidate_props={
            "lat": 40.7128,
            "lon": -74.0060,
            "rate": 0.85,
            "community_id": 1,
            "density": 50.0,
            "active": True,
        },
        query_params={
            "lat": 40.7580,
            "lon": -73.9855,
            "community_id": 1,
        },
        expected_quality="good",
    ),
    BenchmarkPair(
        label="high_rate_nearby",
        candidate_props={
            "lat": 34.0522,
            "lon": -118.2437,
            "rate": 0.95,
            "community_id": 2,
            "density": 80.0,
            "active": True,
        },
        query_params={
            "lat": 34.0500,
            "lon": -118.2500,
            "community_id": 2,
        },
        expected_quality="good",
    ),
    BenchmarkPair(
        label="perfect_community_match",
        candidate_props={
            "lat": 51.5074,
            "lon": -0.1278,
            "rate": 0.70,
            "community_id": 5,
            "density": 60.0,
            "active": True,
        },
        query_params={
            "lat": 51.5200,
            "lon": -0.1000,
            "community_id": 5,
        },
        expected_quality="good",
    ),
    BenchmarkPair(
        label="high_density_close",
        candidate_props={
            "lat": 48.8566,
            "lon": 2.3522,
            "rate": 0.80,
            "community_id": 3,
            "density": 90.0,
            "active": True,
        },
        query_params={
            "lat": 48.8600,
            "lon": 2.3400,
            "community_id": 3,
        },
        expected_quality="good",
    ),
    BenchmarkPair(
        label="strong_match_tokyo",
        candidate_props={
            "lat": 35.6762,
            "lon": 139.6503,
            "rate": 0.90,
            "community_id": 7,
            "density": 75.0,
            "active": True,
        },
        query_params={
            "lat": 35.6800,
            "lon": 139.6600,
            "community_id": 7,
        },
        expected_quality="good",
    ),
]

# --- Bad pairs: candidates that should score poorly ---

BAD_PAIRS: list[BenchmarkPair] = [
    BenchmarkPair(
        label="geo_far_diff_community",
        candidate_props={
            "lat": -33.8688,
            "lon": 151.2093,
            "rate": 0.10,
            "community_id": 99,
            "density": 5.0,
            "active": False,
        },
        query_params={
            "lat": 40.7128,
            "lon": -74.0060,
            "community_id": 1,
        },
        expected_quality="bad",
    ),
    BenchmarkPair(
        label="low_rate_far",
        candidate_props={
            "lat": -22.9068,
            "lon": -43.1729,
            "rate": 0.05,
            "community_id": 50,
            "density": 2.0,
            "active": False,
        },
        query_params={
            "lat": 55.7558,
            "lon": 37.6173,
            "community_id": 10,
        },
        expected_quality="bad",
    ),
    BenchmarkPair(
        label="opposite_hemisphere",
        candidate_props={
            "lat": 64.1466,
            "lon": -21.9426,
            "rate": 0.15,
            "community_id": 88,
            "density": 3.0,
            "active": True,
        },
        query_params={
            "lat": -34.6037,
            "lon": -58.3816,
            "community_id": 20,
        },
        expected_quality="bad",
    ),
    BenchmarkPair(
        label="zero_rate_distant",
        candidate_props={
            "lat": 1.3521,
            "lon": 103.8198,
            "rate": 0.0,
            "community_id": 44,
            "density": 1.0,
            "active": False,
        },
        query_params={
            "lat": 59.3293,
            "lon": 18.0686,
            "community_id": 3,
        },
        expected_quality="bad",
    ),
    BenchmarkPair(
        label="mismatched_everything",
        candidate_props={
            "lat": -1.2921,
            "lon": 36.8219,
            "rate": 0.02,
            "community_id": 200,
            "density": 0.5,
            "active": False,
        },
        query_params={
            "lat": 37.7749,
            "lon": -122.4194,
            "community_id": 1,
        },
        expected_quality="bad",
    ),
]

ALL_PAIRS = GOOD_PAIRS + BAD_PAIRS
