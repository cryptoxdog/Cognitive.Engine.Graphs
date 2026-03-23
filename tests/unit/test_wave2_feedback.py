"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring, feedback, wave2]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for W2-02: Outcome Feedback Loop.
Tests discriminability computation, weight proposals, and apply logic.
"""

from __future__ import annotations

import pytest

from engine.scoring.feedback import MIN_OUTCOMES, WEIGHT_NUDGE, OutcomeFeedback


@pytest.mark.unit
class TestOutcomeFeedbackCompute:
    """Test OutcomeFeedback.compute_feedback()."""

    def test_insufficient_data(self):
        outcomes = [{"outcome": "positive", "dimension_scores": {"geo": 0.8}}]
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        assert result["sufficient_data"] is False
        assert result["sample_count"] == 1
        assert result["proposed_weights"] == {}

    def test_sufficient_positive_only(self):
        outcomes = [
            {"outcome": "positive", "dimension_scores": {"geo": 0.9, "structural": 0.7}} for _ in range(MIN_OUTCOMES)
        ]
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        assert result["sufficient_data"] is True
        assert result["sample_count"] == MIN_OUTCOMES
        assert "geo" in result["dimension_analysis"]
        assert "structural" in result["dimension_analysis"]

    def test_discriminability_positive_vs_negative(self):
        outcomes = []
        for _ in range(6):
            outcomes.append({"outcome": "positive", "dimension_scores": {"geo": 0.9}})
        for _ in range(6):
            outcomes.append({"outcome": "negative", "dimension_scores": {"geo": 0.2}})
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        assert result["sufficient_data"] is True
        analysis = result["dimension_analysis"]["geo"]
        assert analysis["positive_mean"] == pytest.approx(0.9, abs=0.01)
        assert analysis["negative_mean"] == pytest.approx(0.2, abs=0.01)
        assert analysis["discriminability"] > 0
        # Nudge should be positive (dimension predicts success)
        assert result["proposed_weights"]["geo"] > 0

    def test_negative_discriminability(self):
        outcomes = []
        for _ in range(6):
            outcomes.append({"outcome": "positive", "dimension_scores": {"geo": 0.2}})
        for _ in range(6):
            outcomes.append({"outcome": "negative", "dimension_scores": {"geo": 0.8}})
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        # Negative discriminability means the dimension anti-predicts success
        assert result["proposed_weights"]["geo"] < 0

    def test_nudge_capped_at_max(self):
        outcomes = []
        for _ in range(6):
            outcomes.append({"outcome": "positive", "dimension_scores": {"d": 100.0}})
        for _ in range(6):
            outcomes.append({"outcome": "negative", "dimension_scores": {"d": -100.0}})
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        # Nudge should be capped at WEIGHT_NUDGE
        assert abs(result["proposed_weights"]["d"]) <= WEIGHT_NUDGE + 0.0001

    def test_neutral_outcomes_ignored(self):
        outcomes = [{"outcome": "neutral", "dimension_scores": {"geo": 0.5}} for _ in range(MIN_OUTCOMES)]
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        assert result["sufficient_data"] is True
        # Neutral outcomes don't contribute to positive or negative
        assert result["proposed_weights"] == {}

    def test_invalid_outcome_items_skipped(self):
        outcomes = [
            "not a dict",
            {"outcome": "positive"},  # missing dimension_scores
            {"outcome": "positive", "dimension_scores": "not a dict"},
        ]
        # Pad to minimum
        for _ in range(MIN_OUTCOMES):
            outcomes.append({"outcome": "positive", "dimension_scores": {"geo": 0.5}})
        fb = OutcomeFeedback(outcomes)
        result = fb.compute_feedback()

        assert result["sufficient_data"] is True

    def test_empty_outcomes(self):
        fb = OutcomeFeedback([])
        result = fb.compute_feedback()

        assert result["sufficient_data"] is False
        assert result["sample_count"] == 0


@pytest.mark.unit
class TestApplyWeights:
    """Test OutcomeFeedback.apply_weights()."""

    def test_apply_positive_delta(self):
        current = {"geo": 0.25, "structural": 0.30}
        proposed = {"geo": 0.02, "structural": -0.01}
        result = OutcomeFeedback.apply_weights(current, proposed)

        assert result["geo"] == pytest.approx(0.27, abs=0.001)
        assert result["structural"] == pytest.approx(0.29, abs=0.001)

    def test_clamp_to_zero(self):
        current = {"geo": 0.01}
        proposed = {"geo": -0.05}
        result = OutcomeFeedback.apply_weights(current, proposed)

        assert result["geo"] == 0.0

    def test_clamp_to_one(self):
        current = {"geo": 0.99}
        proposed = {"geo": 0.05}
        result = OutcomeFeedback.apply_weights(current, proposed)

        assert result["geo"] == 1.0

    def test_missing_delta_is_noop(self):
        current = {"geo": 0.5, "structural": 0.3}
        proposed = {"geo": 0.01}  # no delta for structural
        result = OutcomeFeedback.apply_weights(current, proposed)

        assert result["structural"] == 0.3
        assert result["geo"] == pytest.approx(0.51, abs=0.001)

    def test_empty_inputs(self):
        result = OutcomeFeedback.apply_weights({}, {})
        assert result == {}
