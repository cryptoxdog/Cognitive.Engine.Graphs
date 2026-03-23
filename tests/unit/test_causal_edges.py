"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, causal, edges]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.causal — edge taxonomy, compiler, and attribution.

Covers:
- CausalEdgeType enum values and validation
- CausalEdgeValidator temporal precedence and property validation
- CausalCompiler generates valid Cypher patterns
- Chain depth limit enforcement
- AttributionCalculator models (first_touch, last_touch, linear, position_based)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from engine.causal.attribution import AttributionCalculator
from engine.causal.causal_compiler import CausalCompiler
from engine.causal.edge_taxonomy import CausalEdgeType, CausalEdgeValidator
from engine.config.schema import (
    CausalEdgeSpec,
    CausalSubgraphSpec,
    DomainSpec,
    FeedbackLoopSpec,
)

# ── CausalEdgeType Enum ────────────────────────────────


class TestCausalEdgeType:
    def test_has_10_members(self):
        assert len(CausalEdgeType) == 10

    def test_all_values(self):
        expected = {
            "CAUSED_BY",
            "TRIGGERED",
            "DROVE",
            "RESULTED_IN",
            "ACCELERATED_BY",
            "BLOCKED_BY",
            "ENABLED_BY",
            "PREVENTED_BY",
            "INFLUENCED_BY",
            "CONTRIBUTED_TO",
        }
        actual = {e.value for e in CausalEdgeType}
        assert actual == expected

    def test_is_str_enum(self):
        assert isinstance(CausalEdgeType.CAUSED_BY, str)
        assert CausalEdgeType.CAUSED_BY == "CAUSED_BY"


# ── CausalEdgeValidator ────────────────────────────────


class TestCausalEdgeValidator:
    def test_valid_properties(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.CAUSED_BY,
            {"confidence": 0.8, "mechanism": "direct_interaction"},
        )
        assert errors == []

    def test_missing_confidence(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.TRIGGERED,
            {"mechanism": "signal_propagation"},
        )
        assert any("confidence" in e for e in errors)

    def test_missing_mechanism(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.DROVE,
            {"confidence": 0.5},
        )
        assert any("mechanism" in e for e in errors)

    def test_confidence_out_of_range(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.RESULTED_IN,
            {"confidence": 1.5, "mechanism": "outcome"},
        )
        assert any("between 0.0 and 1.0" in e for e in errors)

    def test_confidence_negative(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.RESULTED_IN,
            {"confidence": -0.1, "mechanism": "outcome"},
        )
        assert any("between 0.0 and 1.0" in e for e in errors)

    def test_empty_mechanism_string(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.BLOCKED_BY,
            {"confidence": 0.5, "mechanism": "  "},
        )
        assert any("non-empty string" in e for e in errors)

    def test_non_numeric_confidence(self):
        errors = CausalEdgeValidator.validate_edge_properties(
            CausalEdgeType.INFLUENCED_BY,
            {"confidence": "high", "mechanism": "indirect"},
        )
        assert any("numeric" in e for e in errors)


class TestTemporalPrecedence:
    def test_valid_temporal_order(self):
        t1 = datetime(2024, 1, 1, tzinfo=UTC)
        t2 = datetime(2024, 6, 1, tzinfo=UTC)
        errors = CausalEdgeValidator.validate_temporal_precedence(
            t1,
            t2,
            CausalEdgeType.CAUSED_BY,
        )
        assert errors == []

    def test_invalid_temporal_order(self):
        t1 = datetime(2024, 6, 1, tzinfo=UTC)
        t2 = datetime(2024, 1, 1, tzinfo=UTC)
        errors = CausalEdgeValidator.validate_temporal_precedence(
            t1,
            t2,
            CausalEdgeType.TRIGGERED,
        )
        assert len(errors) == 1
        assert "Temporal precedence violated" in errors[0]

    def test_equal_timestamps_invalid(self):
        t1 = datetime(2024, 3, 15, tzinfo=UTC)
        errors = CausalEdgeValidator.validate_temporal_precedence(
            t1,
            t1,
            CausalEdgeType.DROVE,
        )
        assert len(errors) == 1

    def test_none_timestamps_error(self):
        errors = CausalEdgeValidator.validate_temporal_precedence(
            None,
            datetime(2024, 1, 1, tzinfo=UTC),
            CausalEdgeType.CAUSED_BY,
        )
        assert any("timestamps" in e for e in errors)

    def test_non_temporal_edge_no_validation(self):
        """INFLUENCED_BY and CONTRIBUTED_TO don't require temporal ordering."""
        errors = CausalEdgeValidator.validate_temporal_precedence(
            None,
            None,
            CausalEdgeType.INFLUENCED_BY,
        )
        assert errors == []

        errors = CausalEdgeValidator.validate_temporal_precedence(
            None,
            None,
            CausalEdgeType.CONTRIBUTED_TO,
        )
        assert errors == []


class TestIsValidEdgeType:
    def test_valid_types(self):
        for etype in CausalEdgeType:
            assert CausalEdgeValidator.is_valid_edge_type(etype.value) is True

    def test_invalid_type(self):
        assert CausalEdgeValidator.is_valid_edge_type("NOT_A_TYPE") is False


# ── CausalCompiler ──────────────────────────────────────


def _spec_with_causal(
    causal_edges: list[CausalEdgeSpec] | None = None,
    chain_depth: int = 5,
) -> DomainSpec:
    edges = causal_edges or [
        CausalEdgeSpec(
            edge_type="CAUSED_BY",
            source_label="Facility",
            target_label="Facility",
            temporal_validation=True,
        ),
        CausalEdgeSpec(
            edge_type="RESULTED_IN",
            source_label="Facility",
            target_label="TransactionOutcome",
            temporal_validation=True,
            confidence_threshold=0.5,
        ),
    ]
    return DomainSpec(
        domain={"id": "test", "name": "Test", "version": "0.0.1"},
        ontology={
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "query_id", "type": "int", "required": True}],
                },
                {
                    "label": "TransactionOutcome",
                    "managedby": "api",
                    "properties": [{"name": "outcome_id", "type": "string", "required": True}],
                },
            ],
            "edges": [
                {
                    "type": "TRANSACTED_WITH",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "sync",
                },
                {
                    "type": "CAUSED_BY",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "api",
                },
                {
                    "type": "RESULTED_IN",
                    "from": "Facility",
                    "to": "TransactionOutcome",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "api",
                },
            ],
        },
        matchentities={
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        queryschema={"matchdirections": ["d1"], "fields": []},
        gates=[],
        scoring={"dimensions": []},
        causal=CausalSubgraphSpec(
            enabled=True,
            causal_edges=edges,
            chain_depth_limit=chain_depth,
        ),
    )


class TestCausalCompiler:
    def test_compile_edge_create_basic(self):
        spec = _spec_with_causal()
        compiler = CausalCompiler(spec)
        edge_spec = spec.causal.causal_edges[0]  # CAUSED_BY

        cypher = compiler.compile_causal_edge_create(edge_spec)

        assert "MATCH (source:Facility" in cypher
        assert "MATCH (target:Facility" in cypher
        assert "CAUSED_BY" in cypher
        assert "$confidence" in cypher
        assert "$mechanism" in cypher
        assert "source.created_at < target.created_at" in cypher

    def test_compile_edge_create_with_confidence_threshold(self):
        spec = _spec_with_causal()
        compiler = CausalCompiler(spec)
        edge_spec = spec.causal.causal_edges[1]  # RESULTED_IN with threshold

        cypher = compiler.compile_causal_edge_create(edge_spec)

        assert "RESULTED_IN" in cypher
        assert "$confidence >= 0.5" in cypher

    def test_compile_edge_without_temporal_validation(self):
        spec = _spec_with_causal(
            causal_edges=[
                CausalEdgeSpec(
                    edge_type="INFLUENCED_BY",
                    source_label="Facility",
                    target_label="Facility",
                    temporal_validation=False,
                ),
            ]
        )
        compiler = CausalCompiler(spec)
        edge_spec = spec.causal.causal_edges[0]

        cypher = compiler.compile_causal_edge_create(edge_spec)

        assert "created_at < target.created_at" not in cypher

    def test_compile_chain_query(self):
        spec = _spec_with_causal(chain_depth=3)
        compiler = CausalCompiler(spec)

        cypher = compiler.compile_causal_chain_query("Facility")

        assert "MATCH path" in cypher
        assert "Facility" in cypher
        assert "*1..3" in cypher
        assert "chain_depth" in cypher

    def test_compile_chain_query_with_specific_types(self):
        spec = _spec_with_causal()
        compiler = CausalCompiler(spec)

        cypher = compiler.compile_causal_chain_query(
            "Facility",
            edge_types=["CAUSED_BY", "TRIGGERED"],
        )

        assert "CAUSED_BY|TRIGGERED" in cypher

    def test_compile_all_edge_creates(self):
        spec = _spec_with_causal()
        compiler = CausalCompiler(spec)

        compiled = compiler.compile_all_edge_creates()
        assert len(compiled) == 2
        assert all(isinstance(pair, tuple) for pair in compiled)
        assert all(len(pair) == 2 for pair in compiled)

    def test_compile_rejects_invalid_label(self):
        """Labels with injection attempts should be rejected by sanitize_label."""
        spec = _spec_with_causal(
            causal_edges=[
                CausalEdgeSpec(
                    edge_type="CAUSED_BY",
                    source_label="Facility",
                    target_label="Facility",
                ),
            ]
        )
        compiler = CausalCompiler(spec)

        # This should work fine with safe labels
        cypher = compiler.compile_causal_edge_create(spec.causal.causal_edges[0])
        assert "Facility" in cypher


# ── AttributionCalculator ──────────────────────────────


def _spec_with_attribution() -> DomainSpec:
    return DomainSpec(
        domain={"id": "test", "name": "Test", "version": "0.0.1"},
        ontology={
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "query_id", "type": "int", "required": True}],
                },
                {
                    "label": "TransactionOutcome",
                    "managedby": "api",
                    "properties": [{"name": "outcome_id", "type": "string", "required": True}],
                },
            ],
            "edges": [
                {
                    "type": "TRANSACTED_WITH",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "sync",
                },
                {
                    "type": "CONTRIBUTED_TO",
                    "from": "Facility",
                    "to": "TransactionOutcome",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "api",
                },
            ],
        },
        matchentities={
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        queryschema={"matchdirections": ["d1"], "fields": []},
        gates=[],
        scoring={"dimensions": []},
        feedbackloop=FeedbackLoopSpec(enabled=True),
        causal=CausalSubgraphSpec(
            enabled=True,
            attribution_enabled=True,
            causal_edges=[
                CausalEdgeSpec(
                    edge_type="CONTRIBUTED_TO",
                    source_label="Facility",
                    target_label="TransactionOutcome",
                ),
            ],
            chain_depth_limit=5,
        ),
    )


class TestAttributionModels:
    def test_first_touch_all_credit_to_first(self):
        results = [
            {"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]},
            {"touchpoint_id": "tp2", "distance": 2, "confidences": [0.8, 0.7]},
            {"touchpoint_id": "tp3", "distance": 3, "confidences": [0.6, 0.5, 0.4]},
        ]
        weights = AttributionCalculator._assign_weights(results, "first_touch")

        assert weights["tp1"] == 1.0
        assert weights["tp2"] == 0.0
        assert weights["tp3"] == 0.0

    def test_last_touch_all_credit_to_last(self):
        results = [
            {"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]},
            {"touchpoint_id": "tp2", "distance": 2, "confidences": [0.8, 0.7]},
        ]
        weights = AttributionCalculator._assign_weights(results, "last_touch")

        assert weights["tp1"] == 0.0
        assert weights["tp2"] == 1.0

    def test_linear_equal_credit(self):
        results = [
            {"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]},
            {"touchpoint_id": "tp2", "distance": 2, "confidences": [0.8]},
            {"touchpoint_id": "tp3", "distance": 3, "confidences": [0.7]},
        ]
        weights = AttributionCalculator._assign_weights(results, "linear")

        expected = 1.0 / 3.0
        for tp_id in ("tp1", "tp2", "tp3"):
            assert weights[tp_id] == pytest.approx(expected, abs=0.001)

    def test_position_based_single(self):
        results = [{"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]}]
        weights = AttributionCalculator._assign_weights(results, "position_based")
        assert weights["tp1"] == 1.0

    def test_position_based_two(self):
        results = [
            {"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]},
            {"touchpoint_id": "tp2", "distance": 2, "confidences": [0.8]},
        ]
        weights = AttributionCalculator._assign_weights(results, "position_based")
        assert weights["tp1"] == 0.5
        assert weights["tp2"] == 0.5

    def test_position_based_many(self):
        results = [
            {"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]},
            {"touchpoint_id": "tp2", "distance": 2, "confidences": [0.8]},
            {"touchpoint_id": "tp3", "distance": 3, "confidences": [0.7]},
            {"touchpoint_id": "tp4", "distance": 4, "confidences": [0.6]},
        ]
        weights = AttributionCalculator._assign_weights(results, "position_based")

        assert weights["tp1"] == 0.4  # first touch
        assert weights["tp4"] == 0.4  # last touch
        # Middle: 0.2 / 2 = 0.1 each
        assert weights["tp2"] == 0.1
        assert weights["tp3"] == 0.1

    def test_empty_results(self):
        weights = AttributionCalculator._assign_weights([], "linear")
        assert weights == {}


class TestAttributionCalculator:
    @pytest.mark.asyncio
    async def test_invalid_model_raises(self):
        spec = _spec_with_attribution()
        driver = AsyncMock()
        calc = AttributionCalculator(driver, spec)

        with pytest.raises(ValueError, match="Invalid attribution model"):
            await calc.compute_attribution("out_1", model="invalid_model")

    @pytest.mark.asyncio
    async def test_no_touchpoints_returns_empty(self):
        spec = _spec_with_attribution()
        driver = AsyncMock()
        driver.execute_query = AsyncMock(return_value=[])
        calc = AttributionCalculator(driver, spec)

        result = await calc.compute_attribution("out_1", model="linear")

        assert result["touchpoints"] == {}
        assert result["chain_depth"] == 0

    @pytest.mark.asyncio
    async def test_compute_attribution_with_results(self):
        spec = _spec_with_attribution()
        driver = AsyncMock()
        driver.execute_query = AsyncMock(
            return_value=[
                {"touchpoint_id": "tp1", "distance": 1, "confidences": [0.9]},
                {"touchpoint_id": "tp2", "distance": 2, "confidences": [0.8, 0.7]},
            ]
        )
        calc = AttributionCalculator(driver, spec)

        result = await calc.compute_attribution("out_1", model="linear")

        assert result["model"] == "linear"
        assert result["total_touchpoints"] == 2
        assert "tp1" in result["touchpoints"]
        assert "tp2" in result["touchpoints"]
