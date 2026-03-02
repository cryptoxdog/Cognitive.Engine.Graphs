# tests/test_traversal.py
"""
Tests for engine.traversal — assembler + parameter resolver.

Covers:
- TraversalAssembler: MATCH vs OPTIONAL MATCH, direction filtering, empty specs
- ParameterResolver: derived parameter evaluation, error handling, context passthrough
"""

from __future__ import annotations

import pytest

from engine.config.schema import DomainSpec, TraversalStepSpec
from engine.traversal.assembler import TraversalAssembler
from engine.traversal.resolver import ParameterResolver

# ── Helpers ───────────────────────────────────────────────


def _step(
    name: str,
    pattern: str,
    required: bool = True,
    match_directions: list[str] | None = None,
) -> TraversalStepSpec:
    return TraversalStepSpec(
        name=name,
        pattern=pattern,
        required=required,
        matchdirections=match_directions,
    )


def _spec_with_steps(steps: list[TraversalStepSpec]) -> DomainSpec:
    """Build minimal DomainSpec with given traversal steps."""
    raw = {
        "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "MaterialIntake",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [{"name": "intake_id", "type": "int", "required": True}],
                },
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "intake_to_buyer"}],
            "queryentity": [{"label": "MaterialIntake", "matchdirection": "intake_to_buyer"}],
        },
        "queryschema": {"matchdirections": ["intake_to_buyer"], "fields": []},
        "traversal": {"steps": [s.model_dump() for s in steps]},
        "gates": [],
        "scoring": {"dimensions": []},
    }
    return DomainSpec(**raw)


def _resolver_spec(derived_params: list[dict]) -> DomainSpec:
    """Build minimal DomainSpec with derived parameters."""
    raw = {
        "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
        "ontology": {
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
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        "queryschema": {"matchdirections": ["d1"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
        "derivedparameters": derived_params,
    }
    return DomainSpec(**raw)


# ── TraversalAssembler ────────────────────────────────────


class TestTraversalAssembler:
    """Tests for TraversalAssembler.assemble_traversal()."""

    def test_required_step_produces_match(self):
        spec = _spec_with_steps(
            [
                _step("cap", "(candidate)-[:ACCEPTS_POLYMER]->(poly:PolymerFamily)", required=True),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert len(clauses) == 1
        assert clauses[0].startswith("MATCH ")
        assert "ACCEPTS_POLYMER" in clauses[0]

    def test_optional_step_produces_optional_match(self):
        spec = _spec_with_steps(
            [
                _step("geo", "(candidate)-[:COLOCATED_WITH]->(neighbor)", required=False),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert len(clauses) == 1
        assert clauses[0].startswith("OPTIONAL MATCH ")

    def test_mixed_required_and_optional(self):
        spec = _spec_with_steps(
            [
                _step("cap", "(candidate)-[:ACCEPTS]->(p)", required=True),
                _step("geo", "(candidate)-[:NEARBY]->(n)", required=False),
                _step("txn", "(candidate)-[:TRANSACTED]->(t)", required=True),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert len(clauses) == 3
        assert clauses[0].startswith("MATCH ")
        assert clauses[1].startswith("OPTIONAL MATCH ")
        assert clauses[2].startswith("MATCH ")

    def test_direction_filtering_includes_matching(self):
        spec = _spec_with_steps(
            [
                _step("cap", "(c)-[:R]->(t)", match_directions=["intake_to_buyer"]),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert len(clauses) == 1

    def test_direction_filtering_excludes_nonmatching(self):
        spec = _spec_with_steps(
            [
                _step("cap", "(c)-[:R]->(t)", match_directions=["buyer_to_intake"]),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert len(clauses) == 0

    def test_null_matchdirections_always_included(self):
        spec = _spec_with_steps(
            [
                _step("cap", "(c)-[:R]->(t)", match_directions=None),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("anything")
        assert len(clauses) == 1

    def test_empty_steps(self):
        spec = _spec_with_steps([])
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert clauses == []

    def test_pattern_preserved_verbatim(self):
        pattern = "(candidate)-[:ACCEPTED_MATERIAL_FROM]->(seller:Facility)"
        spec = _spec_with_steps([_step("reinf", pattern)])
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("intake_to_buyer")
        assert pattern in clauses[0]

    def test_multiple_directions_partial_match(self):
        spec = _spec_with_steps(
            [
                _step("a", "(c)-[:X]->(t)", match_directions=["d1", "d2"]),
                _step("b", "(c)-[:Y]->(t)", match_directions=["d2", "d3"]),
                _step("c", "(c)-[:Z]->(t)", match_directions=["d1"]),
            ]
        )
        asm = TraversalAssembler(spec)
        clauses = asm.assemble_traversal("d2")
        assert len(clauses) == 2  # steps a and b match d2


# ── ParameterResolver ─────────────────────────────────────


class TestParameterResolver:
    """Tests for ParameterResolver.resolve_parameters()."""

    def test_simple_division(self):
        spec = _resolver_spec(
            [
                {"name": "monthly_income", "expression": "annual_income / 12.0", "type": "float"},
            ]
        )
        resolver = ParameterResolver(spec)
        result = resolver.resolve_parameters({"annual_income": 120000.0})
        assert result["monthly_income"] == pytest.approx(10000.0)

    def test_original_fields_preserved(self):
        spec = _resolver_spec(
            [
                {"name": "derived", "expression": "x + 1", "type": "float"},
            ]
        )
        resolver = ParameterResolver(spec)
        result = resolver.resolve_parameters({"x": 5, "other": "keep"})
        assert result["x"] == 5
        assert result["other"] == "keep"
        assert result["derived"] == 6

    def test_chained_derived_parameters(self):
        spec = _resolver_spec(
            [
                {"name": "half", "expression": "total / 2", "type": "float"},
                {"name": "quarter", "expression": "half / 2", "type": "float"},
            ]
        )
        resolver = ParameterResolver(spec)
        result = resolver.resolve_parameters({"total": 100.0})
        assert result["half"] == pytest.approx(50.0)
        assert result["quarter"] == pytest.approx(25.0)

    def test_expression_error_does_not_crash(self):
        spec = _resolver_spec(
            [
                {"name": "bad", "expression": "nonexistent_var + 1", "type": "float"},
            ]
        )
        resolver = ParameterResolver(spec)
        result = resolver.resolve_parameters({"x": 1})
        assert "bad" not in result  # failed silently, logged error
        assert result["x"] == 1  # original data intact

    def test_no_derived_parameters(self):
        spec = _resolver_spec([])
        resolver = ParameterResolver(spec)
        result = resolver.resolve_parameters({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_multiplication_and_subtraction(self):
        spec = _resolver_spec(
            [
                {"name": "margin", "expression": "price - cost", "type": "float"},
                {"name": "total", "expression": "margin * quantity", "type": "float"},
            ]
        )
        resolver = ParameterResolver(spec)
        result = resolver.resolve_parameters({"price": 10.0, "cost": 3.0, "quantity": 100})
        assert result["margin"] == pytest.approx(7.0)
        assert result["total"] == pytest.approx(700.0)
