"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring, confidence, wave2]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for W2-03: Ensemble Confidence Bounds Checking.
Tests monoculture detection with various dimension score distributions.
"""

from __future__ import annotations

import pytest

from engine.scoring.confidence import (
    FLAG_ENSEMBLE_DIVERGENCE,
    FLAG_MONOCULTURE,
    ConfidenceChecker,
)


@pytest.mark.unit
class TestMonocultureDetection:
    """Test ConfidenceChecker.check_monoculture()."""

    def test_no_monoculture(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.3, "structural": 0.3, "freshness": 0.2, "reinforcement": 0.2}},
        ]
        flags = checker.check_monoculture(candidates)
        assert flags == []

    def test_monoculture_detected(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.9, "structural": 0.05, "freshness": 0.03, "reinforcement": 0.02}},
        ]
        flags = checker.check_monoculture(candidates)
        assert len(flags) == 1
        assert flags[0]["flag"] == FLAG_MONOCULTURE
        assert flags[0]["dominant_dimension"] == "geo"
        assert flags[0]["contribution"] > 0.70

    def test_exactly_at_threshold_not_flagged(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.70, "structural": 0.30}},
        ]
        flags = checker.check_monoculture(candidates)
        assert flags == []

    def test_just_above_threshold_flagged(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.71, "structural": 0.29}},
        ]
        flags = checker.check_monoculture(candidates)
        assert len(flags) == 1

    def test_multiple_candidates_mixed(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.5, "structural": 0.5}},  # no flag
            {"dimension_scores": {"geo": 0.95, "structural": 0.05}},  # flagged
            {"dimension_scores": {"geo": 0.4, "structural": 0.6}},  # no flag
        ]
        flags = checker.check_monoculture(candidates)
        assert len(flags) == 1
        assert flags[0]["candidate_index"] == 1

    def test_empty_candidates(self):
        checker = ConfidenceChecker()
        flags = checker.check_monoculture([])
        assert flags == []

    def test_missing_dimension_scores(self):
        checker = ConfidenceChecker()
        candidates = [{"name": "no_scores"}]
        flags = checker.check_monoculture(candidates)
        assert flags == []

    def test_zero_total_score_skipped(self):
        checker = ConfidenceChecker()
        candidates = [{"dimension_scores": {"geo": 0.0, "structural": 0.0}}]
        flags = checker.check_monoculture(candidates)
        assert flags == []

    def test_single_dimension(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [{"dimension_scores": {"geo": 0.8}}]
        flags = checker.check_monoculture(candidates)
        # Single dimension = 100% contribution, should be flagged
        assert len(flags) == 1
        assert flags[0]["contribution"] == pytest.approx(1.0, abs=0.001)

    def test_custom_threshold(self):
        checker = ConfidenceChecker(monoculture_threshold=0.50)
        candidates = [
            {"dimension_scores": {"geo": 0.6, "structural": 0.4}},
        ]
        flags = checker.check_monoculture(candidates)
        assert len(flags) == 1  # 0.6/1.0 = 0.6 > 0.5


@pytest.mark.unit
class TestEnsembleDivergence:
    """Test ConfidenceChecker.check_ensemble_divergence() (Wave 6 stub)."""

    def test_no_divergence(self):
        checker = ConfidenceChecker(ensemble_max_divergence=0.30)
        flags = checker.check_ensemble_divergence([0.5, 0.6, 0.7], [0.55, 0.62, 0.68])
        assert flags == []

    def test_divergence_detected(self):
        checker = ConfidenceChecker(ensemble_max_divergence=0.30)
        flags = checker.check_ensemble_divergence([0.2, 0.5], [0.9, 0.5])
        assert len(flags) == 1
        assert flags[0]["flag"] == FLAG_ENSEMBLE_DIVERGENCE
        assert flags[0]["candidate_index"] == 0
        assert flags[0]["divergence"] > 0.30

    def test_empty_scores(self):
        checker = ConfidenceChecker()
        flags = checker.check_ensemble_divergence([], [])
        assert flags == []


@pytest.mark.unit
class TestAnnotateCandidates:
    """Test ConfidenceChecker.annotate_candidates()."""

    def test_annotates_monoculture_flag(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.95, "structural": 0.05}},
            {"dimension_scores": {"geo": 0.5, "structural": 0.5}},
        ]
        result = checker.annotate_candidates(candidates)

        flag = result[0]["confidence_flag"]
        if isinstance(flag, list):
            assert FLAG_MONOCULTURE in flag
        else:
            assert flag == FLAG_MONOCULTURE
        assert result[0]["confidence_detail"]["dominant_dimension"] == "geo"
        assert "confidence_flag" not in result[1]

    def test_no_annotations_when_clean(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.4, "structural": 0.6}},
        ]
        result = checker.annotate_candidates(candidates)

        assert "confidence_flag" not in result[0]

    def test_mutates_in_place(self):
        checker = ConfidenceChecker(monoculture_threshold=0.70)
        candidates = [
            {"dimension_scores": {"geo": 0.95, "structural": 0.05}},
        ]
        result = checker.annotate_candidates(candidates)

        # Should be the same list object
        assert result is candidates
