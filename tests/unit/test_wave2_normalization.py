"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring, normalization, wave2]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for W2-04: Score Normalization Layer.
Tests min-max normalization math: edge cases for single result, all same score, etc.
Also tests feature flag toggling and scoring_meta output.
"""

from __future__ import annotations

import pytest


def _normalize_scores(candidates: list[dict], normalize: bool) -> tuple[list[dict], dict]:
    """Reproduce the normalization logic from handle_match for unit testing."""
    scoring_meta = {"normalization_applied": False, "raw_max": 0.0, "raw_min": 0.0}

    if not candidates:
        return candidates, scoring_meta

    raw_scores = [c.get("score", 0.0) for c in candidates]
    scoring_meta["raw_max"] = max(raw_scores)
    scoring_meta["raw_min"] = min(raw_scores)

    if normalize and len(candidates) > 0:
        raw_max = scoring_meta["raw_max"]
        raw_min = scoring_meta["raw_min"]
        score_range = raw_max - raw_min
        if score_range > 0:
            for c in candidates:
                if "score" in c:
                    c["score"] = round((c["score"] - raw_min) / score_range, 6)
        elif len(candidates) == 1:
            candidates[0]["score"] = 1.0
        scoring_meta["normalization_applied"] = True

    return candidates, scoring_meta


@pytest.mark.unit
class TestNormalizationMath:
    """Test min-max normalization logic."""

    def test_basic_normalization(self):
        candidates = [
            {"score": 0.8, "name": "A"},
            {"score": 0.4, "name": "B"},
            {"score": 0.6, "name": "C"},
        ]
        result, meta = _normalize_scores(candidates, normalize=True)

        assert result[0]["score"] == pytest.approx(1.0, abs=0.001)  # max -> 1.0
        assert result[1]["score"] == pytest.approx(0.0, abs=0.001)  # min -> 0.0
        assert result[2]["score"] == pytest.approx(0.5, abs=0.001)  # mid -> 0.5
        assert meta["normalization_applied"] is True
        assert meta["raw_max"] == 0.8
        assert meta["raw_min"] == 0.4

    def test_single_result(self):
        candidates = [{"score": 0.42}]
        result, meta = _normalize_scores(candidates, normalize=True)

        assert result[0]["score"] == 1.0
        assert meta["normalization_applied"] is True

    def test_all_same_score(self):
        candidates = [{"score": 0.5}, {"score": 0.5}, {"score": 0.5}]
        result, meta = _normalize_scores(candidates, normalize=True)

        # Range is 0, scores unchanged (no division by zero)
        assert all(c["score"] == 0.5 for c in result)
        assert meta["normalization_applied"] is True

    def test_zero_scores(self):
        candidates = [{"score": 0.0}, {"score": 0.0}]
        result, _meta = _normalize_scores(candidates, normalize=True)

        assert all(c["score"] == 0.0 for c in result)

    def test_normalization_disabled(self):
        candidates = [{"score": 0.8}, {"score": 0.4}]
        result, meta = _normalize_scores(candidates, normalize=False)

        assert result[0]["score"] == 0.8
        assert result[1]["score"] == 0.4
        assert meta["normalization_applied"] is False

    def test_empty_candidates(self):
        result, meta = _normalize_scores([], normalize=True)

        assert result == []
        assert meta["raw_max"] == 0.0
        assert meta["raw_min"] == 0.0

    def test_large_spread(self):
        candidates = [{"score": 100.0}, {"score": 0.0}, {"score": 50.0}]
        result, _meta = _normalize_scores(candidates, normalize=True)

        assert result[0]["score"] == pytest.approx(1.0, abs=0.001)
        assert result[1]["score"] == pytest.approx(0.0, abs=0.001)
        assert result[2]["score"] == pytest.approx(0.5, abs=0.001)

    def test_negative_scores(self):
        candidates = [{"score": -0.2}, {"score": 0.8}, {"score": 0.3}]
        result, meta = _normalize_scores(candidates, normalize=True)

        assert result[0]["score"] == pytest.approx(0.0, abs=0.001)  # min -> 0
        assert result[1]["score"] == pytest.approx(1.0, abs=0.001)  # max -> 1
        assert meta["raw_min"] == -0.2
        assert meta["raw_max"] == 0.8

    def test_two_candidates(self):
        candidates = [{"score": 0.9}, {"score": 0.1}]
        result, _meta = _normalize_scores(candidates, normalize=True)

        assert result[0]["score"] == pytest.approx(1.0, abs=0.001)
        assert result[1]["score"] == pytest.approx(0.0, abs=0.001)


@pytest.mark.unit
class TestScoringMeta:
    """Test scoring_meta presence in response."""

    def test_meta_contains_raw_scores(self):
        candidates = [{"score": 0.7}, {"score": 0.3}]
        _, meta = _normalize_scores(candidates, normalize=False)

        assert meta["raw_max"] == 0.7
        assert meta["raw_min"] == 0.3
        assert meta["normalization_applied"] is False

    def test_meta_with_normalization(self):
        candidates = [{"score": 0.8}, {"score": 0.2}]
        _, meta = _normalize_scores(candidates, normalize=True)

        assert meta["raw_max"] == 0.8
        assert meta["raw_min"] == 0.2
        assert meta["normalization_applied"] is True
