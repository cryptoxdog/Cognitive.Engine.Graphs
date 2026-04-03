"""
Tests for Milestone 2.1 / 2.2 Pareto wiring:
- DecisionArbitrationSpec schema extension
- pareto_integrator (build_pareto_candidates, apply_constraint_penalties, apply_pareto_filter)
- OutcomeRecord + OutcomeHistoryStore
- adaptive_weight_discovery
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════
#  Milestone 2.1: Schema Extension
# ═══════════════════════════════════════════════════════════════════════════


class TestDecisionArbitrationSpec:
    """Tests for the DecisionArbitrationSpec on DomainSpec."""

    def test_default_disabled(self):
        from engine.config.schema import DecisionArbitrationSpec

        spec = DecisionArbitrationSpec()
        assert spec.enabled is False
        assert spec.optimization_method == "pareto"
        assert spec.constraints == []
        assert spec.pareto_config.objectives == []

    def test_full_config(self):
        from engine.config.schema import (
            ArbitrationConstraintSpec,
            DecisionArbitrationSpec,
            ParetoConfigSpec,
            ParetoObjectiveSpec,
        )

        spec = DecisionArbitrationSpec(
            enabled=True,
            optimization_method="pareto",
            pareto_config=ParetoConfigSpec(
                objectives=[
                    ParetoObjectiveSpec(dimension="structural", direction="maximize"),
                    ParetoObjectiveSpec(dimension="geo_decay", direction="maximize"),
                    ParetoObjectiveSpec(dimension="price_alignment", direction="maximize", weight_hint=0.8),
                ],
                front_size_limit=30,
            ),
            constraints=[
                ArbitrationConstraintSpec(dimension="structural", threshold=0.7, hard=True),
                ArbitrationConstraintSpec(dimension="geo_decay", threshold=0.5, hard=False, penalty=0.5),
            ],
            policy_weights={
                "balanced": {"structural": 0.33, "geo_decay": 0.33, "price_alignment": 0.34},
                "quality_first": {"structural": 0.6, "geo_decay": 0.2, "price_alignment": 0.2},
            },
        )
        assert spec.enabled is True
        assert len(spec.pareto_config.objectives) == 3
        assert spec.pareto_config.front_size_limit == 30
        assert len(spec.constraints) == 2
        assert spec.constraints[0].hard is True
        assert spec.constraints[1].penalty == 0.5
        assert "balanced" in spec.policy_weights

    def test_domain_spec_has_decision_arbitration(self):
        """DomainSpec should have a decision_arbitration field that defaults to disabled."""
        from engine.config.schema import DomainSpec

        # Check the field exists in the model
        assert "decision_arbitration" in DomainSpec.model_fields


# ═══════════════════════════════════════════════════════════════════════════
#  Milestone 2.1: Pareto Integrator
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildParetoCandidates:
    def test_basic_construction(self):
        from engine.scoring.pareto_integrator import build_pareto_candidates

        results = [
            {
                "candidate": {"entity_id": "c1"},
                "structural": 0.9,
                "geo_decay": 0.7,
                "score": 0.8,
            },
            {
                "candidate": {"entity_id": "c2"},
                "structural": 0.6,
                "geo_decay": 0.95,
                "score": 0.75,
            },
        ]
        candidates = build_pareto_candidates(results, ["structural", "geo_decay"])
        assert len(candidates) == 2
        assert candidates[0].candidate_id == "c1"
        assert candidates[0].dimension_scores["structural"] == 0.9
        assert candidates[1].dimension_scores["geo_decay"] == 0.95

    def test_dimension_scores_subdict(self):
        from engine.scoring.pareto_integrator import build_pareto_candidates

        results = [
            {
                "candidate": {"entity_id": "c1"},
                "dimension_scores": {"structural": 0.8, "geo_decay": 0.6},
            },
        ]
        candidates = build_pareto_candidates(results, ["structural", "geo_decay"])
        assert candidates[0].dimension_scores["structural"] == 0.8

    def test_missing_dimension_defaults_to_zero(self):
        from engine.scoring.pareto_integrator import build_pareto_candidates

        results = [{"candidate": {"entity_id": "c1"}, "structural": 0.9}]
        candidates = build_pareto_candidates(results, ["structural", "missing_dim"])
        assert candidates[0].dimension_scores["missing_dim"] == 0.0

    def test_empty_results(self):
        from engine.scoring.pareto_integrator import build_pareto_candidates

        assert build_pareto_candidates([], ["a", "b"]) == []


class TestApplyConstraintPenalties:
    def test_hard_constraint_rejects(self):
        from engine.scoring.pareto_integrator import apply_constraint_penalties

        candidates = [
            {"dimension_scores": {"structural": 0.5, "geo": 0.8}, "score": 0.7},
            {"dimension_scores": {"structural": 0.9, "geo": 0.8}, "score": 0.85},
        ]
        constraints = [{"dimension": "structural", "threshold": 0.7, "hard": True, "penalty": 0.5}]
        result = apply_constraint_penalties(candidates, constraints)
        assert len(result) == 1
        assert result[0]["dimension_scores"]["structural"] == 0.9

    def test_soft_constraint_applies_penalty(self):
        from engine.scoring.pareto_integrator import apply_constraint_penalties

        candidates = [
            {"dimension_scores": {"geo": 0.3}, "score": 1.0},
        ]
        constraints = [{"dimension": "geo", "threshold": 0.5, "hard": False, "penalty": 0.5}]
        result = apply_constraint_penalties(candidates, constraints)
        assert len(result) == 1
        assert result[0]["score"] == 0.5  # 1.0 * 0.5

    def test_no_constraints_passes_all(self):
        from engine.scoring.pareto_integrator import apply_constraint_penalties

        candidates = [{"dimension_scores": {"a": 0.1}, "score": 0.5}]
        result = apply_constraint_penalties(candidates, [])
        assert len(result) == 1


class TestApplyParetoFilter:
    def test_basic_filter(self):
        from engine.scoring.pareto_integrator import apply_pareto_filter

        candidates = [
            {"candidate": {"entity_id": "c1"}, "structural": 0.9, "geo": 0.9},
            {"candidate": {"entity_id": "c2"}, "structural": 0.5, "geo": 0.5},
            {"candidate": {"entity_id": "c3"}, "structural": 0.8, "geo": 0.95},
        ]
        result = apply_pareto_filter(candidates, ["structural", "geo"])
        assert "c1" in result["nondominated"]
        assert "c3" in result["nondominated"]
        assert "c2" in result["dominated"]
        assert result["frontsize"] == 2

    def test_empty_candidates(self):
        from engine.scoring.pareto_integrator import apply_pareto_filter

        result = apply_pareto_filter([], ["a"])
        assert result["frontsize"] == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Milestone 2.2: Outcome Models
# ═══════════════════════════════════════════════════════════════════════════


class TestOutcomeRecord:
    def test_basic_construction(self):
        from engine.models.outcomes import OutcomeRecord

        rec = OutcomeRecord(
            match_id="m1",
            candidate_id="c1",
            dimension_scores={"structural": 0.9, "geo": 0.7},
            was_selected=True,
        )
        assert rec.match_id == "m1"
        assert rec.was_selected is True
        assert rec.feedback_score is None

    def test_with_feedback_score(self):
        from engine.models.outcomes import OutcomeRecord

        rec = OutcomeRecord(
            match_id="m1",
            candidate_id="c1",
            dimension_scores={"a": 0.5},
            was_selected=False,
            feedback_score=0.8,
        )
        assert rec.feedback_score == 0.8


class TestOutcomeHistoryStore:
    def test_add_and_get_recent(self):
        from engine.models.outcomes import OutcomeHistoryStore, OutcomeRecord

        store = OutcomeHistoryStore()
        for i in range(20):
            store.add_outcome(
                "plasticos",
                OutcomeRecord(
                    match_id=f"m{i}",
                    candidate_id=f"c{i}",
                    dimension_scores={"structural": 0.5 + i * 0.02},
                    was_selected=i % 2 == 0,
                ),
            )
        recent = store.get_recent("plasticos", days=90)
        assert len(recent) == 20
        assert "dimension_scores" in recent[0]
        assert "was_selected" in recent[0]

    def test_ttl_filtering(self):
        from engine.models.outcomes import OutcomeHistoryStore, OutcomeRecord

        store = OutcomeHistoryStore()
        # Add an old outcome
        old = OutcomeRecord(
            match_id="old",
            candidate_id="c_old",
            dimension_scores={"a": 0.5},
            was_selected=True,
            timestamp=datetime.now(UTC) - timedelta(days=100),
        )
        store.add_outcome("t1", old)
        # Add a recent outcome
        store.add_outcome(
            "t1",
            OutcomeRecord(
                match_id="new",
                candidate_id="c_new",
                dimension_scores={"a": 0.9},
                was_selected=False,
            ),
        )
        recent = store.get_recent("t1", days=90)
        assert len(recent) == 1
        assert recent[0]["dimension_scores"]["a"] == 0.9

    def test_capacity_eviction(self):
        from engine.models.outcomes import OutcomeHistoryStore, OutcomeRecord

        store = OutcomeHistoryStore(max_per_tenant=5)
        for i in range(10):
            store.add_outcome(
                "t1",
                OutcomeRecord(
                    match_id=f"m{i}",
                    candidate_id=f"c{i}",
                    dimension_scores={"a": float(i)},
                    was_selected=True,
                ),
            )
        assert store.count("t1") == 5

    def test_tenant_isolation(self):
        from engine.models.outcomes import OutcomeHistoryStore, OutcomeRecord

        store = OutcomeHistoryStore()
        store.add_outcome(
            "t1",
            OutcomeRecord(match_id="m1", candidate_id="c1", dimension_scores={"a": 1.0}, was_selected=True),
        )
        store.add_outcome(
            "t2",
            OutcomeRecord(match_id="m2", candidate_id="c2", dimension_scores={"a": 2.0}, was_selected=False),
        )
        assert store.count("t1") == 1
        assert store.count("t2") == 1
        assert store.get_recent("t1")[0]["dimension_scores"]["a"] == 1.0

    def test_clear(self):
        from engine.models.outcomes import OutcomeHistoryStore, OutcomeRecord

        store = OutcomeHistoryStore()
        store.add_outcome(
            "t1",
            OutcomeRecord(match_id="m1", candidate_id="c1", dimension_scores={"a": 1.0}, was_selected=True),
        )
        cleared = store.clear("t1")
        assert cleared == 1
        assert store.count("t1") == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Milestone 2.2: Adaptive Weight Discovery
# ═══════════════════════════════════════════════════════════════════════════


class TestAdaptiveWeightDiscovery:
    def test_basic_discovery(self):
        from engine.scoring.weight_discovery import adaptive_weight_discovery

        outcome_history = [
            {"dimension_scores": {"structural": 0.9, "geo": 0.7}, "was_selected": True},
            {"dimension_scores": {"structural": 0.5, "geo": 0.95}, "was_selected": False},
            {"dimension_scores": {"structural": 0.8, "geo": 0.8}, "was_selected": True},
        ] * 5  # 15 outcomes

        result = asyncio.get_event_loop().run_until_complete(
            adaptive_weight_discovery(
                dimension_names=["structural", "geo"],
                outcome_history=outcome_history,
                n_samples=20,
            )
        )
        assert len(result) > 0
        # Each result should have weights for both dimensions
        for wv in result:
            assert "structural" in wv.weights
            assert "geo" in wv.weights
            # Weights should sum to ~1.0
            assert abs(sum(wv.weights.values()) - 1.0) < 1e-6

    def test_empty_dimensions(self):
        from engine.scoring.weight_discovery import adaptive_weight_discovery

        result = asyncio.get_event_loop().run_until_complete(
            adaptive_weight_discovery(dimension_names=[], outcome_history=[])
        )
        assert result == []

    def test_no_outcome_history(self):
        from engine.scoring.weight_discovery import adaptive_weight_discovery

        result = asyncio.get_event_loop().run_until_complete(
            adaptive_weight_discovery(
                dimension_names=["a", "b"],
                outcome_history=[],
                n_samples=10,
            )
        )
        # Should still return weight vectors (just without NDCG signal)
        assert len(result) > 0

    def test_deterministic_with_seed(self):
        from engine.scoring.weight_discovery import adaptive_weight_discovery

        history = [{"dimension_scores": {"x": 0.8, "y": 0.6}, "was_selected": True}] * 10

        r1 = asyncio.get_event_loop().run_until_complete(adaptive_weight_discovery(["x", "y"], history, n_samples=15))
        r2 = asyncio.get_event_loop().run_until_complete(adaptive_weight_discovery(["x", "y"], history, n_samples=15))
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2, strict=True):
            assert a.weights == b.weights
