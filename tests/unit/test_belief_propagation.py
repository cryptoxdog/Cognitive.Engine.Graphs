"""
Unit tests — Belief Propagation (Theory of Trust implementation).

Coverage:
  - Bayesian update correctness
  - Multi-parent composite scoring
  - Chain propagation
  - Hop trust derivation
  - Candidate rescoring
  - Edge cases and bounds
"""
from __future__ import annotations

import pytest

from engine.scoring.belief_propagation import (
    TRUST_CONTRADICTION,
    TRUST_ENTAILMENT,
    TRUST_NEUTRAL,
    bayesian_update,
    chain_composite,
    composite_score,
    hop_trust_from_entry,
    propagate_chain,
    rescore_candidates,
)


class TestBayesianUpdate:
    """Test Bayesian belief update primitive."""

    def test_neutral_prior_strong_evidence(self):
        result = bayesian_update(0.5, 0.9)
        assert 0.89 < result < 0.91

    def test_strong_prior_strong_evidence(self):
        result = bayesian_update(0.8, 0.9)
        assert 0.97 < result < 0.98

    def test_weak_prior_strong_evidence(self):
        result = bayesian_update(0.2, 0.9)
        assert 0.68 < result < 0.70

    def test_neutral_prior_weak_evidence(self):
        result = bayesian_update(0.5, 0.2)
        assert 0.19 < result < 0.21

    def test_extremes(self):
        assert bayesian_update(1.0, 1.0) == 1.0
        assert bayesian_update(0.0, 0.0) == 0.0
        assert bayesian_update(0.0, 1.0) == 0.0

    def test_output_bounded(self):
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for e in [0.1, 0.3, 0.5, 0.7, 0.9]:
                result = bayesian_update(p, e)
                assert 0.0 <= result <= 1.0

    def test_bounds_validation_prior(self):
        with pytest.raises(ValueError):
            bayesian_update(-0.1, 0.5)

    def test_bounds_validation_evidence(self):
        with pytest.raises(ValueError):
            bayesian_update(0.5, 1.1)


class TestCompositeScore:
    """Test multi-parent belief fusion."""

    def test_high_confidence_low_entropy(self):
        score = composite_score([0.9, 0.85, 0.8], prior=0.5)
        assert score > 0.8

    def test_mixed_signals_high_entropy(self):
        score = composite_score([0.9, 0.5, 0.2], prior=0.5)
        assert score < 0.5

    def test_strong_prior_consistent_evidence(self):
        score = composite_score([0.95] * 5, prior=0.8)
        assert score > 0.94

    def test_empty_signals_returns_prior(self):
        assert composite_score([], prior=0.7) == 0.7

    def test_single_signal(self):
        score = composite_score([0.9], prior=0.5)
        assert 0.85 < score < 0.95

    def test_output_always_bounded(self):
        for signals in [[0.1, 0.9], [0.5, 0.5], [0.99, 0.01]]:
            result = composite_score(signals)
            assert 0.0 <= result <= 1.0


class TestChainComposite:
    """Test chain hop trace quality scoring."""

    def test_consistent_high_trust_path(self):
        score = chain_composite([0.95, 0.95, 0.95], prior=0.6)
        assert score > 0.94

    def test_middle_hop_uncertainty(self):
        score = chain_composite([0.95, 0.6, 0.95], prior=0.6)
        assert 0.6 < score < 0.7

    def test_degrading_trust_chain(self):
        score = chain_composite([0.9, 0.7, 0.5], prior=0.5)
        assert 0.4 < score < 0.6


class TestPropagateChain:
    """Test chain terminal confidence (no entropy penalty)."""

    def test_strong_accumulation(self):
        result = propagate_chain([0.9, 0.85, 0.8], prior=0.5)
        assert result > 0.98

    def test_weak_terminal_hop(self):
        result = propagate_chain([0.9, 0.5, 0.2], prior=0.5)
        assert result < 0.25

    def test_empty_chain_returns_prior(self):
        assert propagate_chain([], prior=0.7) == 0.7

    def test_single_hop(self):
        result = propagate_chain([0.9], prior=0.5)
        assert 0.89 < result < 0.91


class TestHopTrustFromEntry:
    """Test GATE HopEntry trust derivation."""

    def test_completed_fast(self):
        trust = hop_trust_from_entry("COMPLETED", 1000, 30000)
        assert trust == TRUST_ENTAILMENT

    def test_completed_near_timeout(self):
        trust = hop_trust_from_entry("COMPLETED", 25000, 30000)
        assert TRUST_NEUTRAL < trust < TRUST_ENTAILMENT

    def test_completed_at_timeout(self):
        trust = hop_trust_from_entry("COMPLETED", 30000, 30000)
        assert trust == pytest.approx(TRUST_NEUTRAL, abs=0.01)

    def test_pending_status(self):
        assert hop_trust_from_entry("PENDING", 5000, 30000) == TRUST_NEUTRAL

    def test_delegated_status(self):
        assert hop_trust_from_entry("DELEGATED", 5000, 30000) == TRUST_NEUTRAL

    def test_failed_status(self):
        assert hop_trust_from_entry("FAILED", 5000, 30000) == TRUST_CONTRADICTION

    def test_timeout_status(self):
        assert hop_trust_from_entry("TIMEOUT", 30000, 30000) == TRUST_CONTRADICTION

    def test_unknown_status(self):
        assert hop_trust_from_entry("UNKNOWN_XYZ", 5000, 30000) == TRUST_NEUTRAL

    def test_output_bounded(self):
        for status in ("COMPLETED", "PENDING", "FAILED", "TIMEOUT"):
            trust = hop_trust_from_entry(status, 10000, 30000)
            assert 0.0 <= trust <= 1.0


class TestRescoreCandidates:
    """Test CEG candidate rescoring."""

    def test_higher_prior_wins(self):
        candidates = [
            {"id": "A", "geo": 0.9,  "temporal": 0.85, "confidence": 0.7},
            {"id": "B", "geo": 0.95, "temporal": 0.9,  "confidence": 0.5},
        ]
        rescored = rescore_candidates(candidates, ["geo", "temporal"])
        assert rescored[0]["id"] == "A"

    def test_sorting_descending(self):
        candidates = [
            {"id": "A", "score": 0.5},
            {"id": "B", "score": 0.9},
            {"id": "C", "score": 0.7},
        ]
        rescored = rescore_candidates(candidates, ["score"])
        assert [c["id"] for c in rescored] == ["B", "C", "A"]

    def test_empty_candidates(self):
        assert rescore_candidates([], ["score"]) == []

    def test_missing_dimensions_treated_as_zero(self):
        candidates = [{"id": "A", "geo": 0.9}]
        rescored = rescore_candidates(candidates, ["geo", "missing_dim"])
        assert "belief_score" in rescored[0]

    def test_immutability(self):
        candidates = [{"id": "A", "geo": 0.9}]
        rescore_candidates(candidates, ["geo"])
        assert "belief_score" not in candidates[0]

    def test_custom_prior_key(self):
        candidates = [{"id": "A", "score": 0.8, "custom_prior": 0.9}]
        rescored = rescore_candidates(candidates, ["score"], prior_key="custom_prior")
        assert rescored[0]["belief_score"] > 0.85

    def test_custom_score_key(self):
        candidates = [{"id": "A", "score": 0.8}]
        rescored = rescore_candidates(candidates, ["score"], score_key="my_score")
        assert "my_score" in rescored[0]
        assert "belief_score" not in rescored[0]

    def test_belief_score_bounded(self):
        candidates = [{"id": str(i), "geo": i / 10, "confidence": 0.5} for i in range(1, 10)]
        rescored = rescore_candidates(candidates, ["geo"])
        for c in rescored:
            assert 0.0 <= c["belief_score"] <= 1.0
