"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, wave1, invariants, sel4]
owner: engine-team
status: active
--- /L9_META ---

Tests for Wave 1: Invariant & Validation Hardening (seL4-inspired).
Covers W1-01 through W1-05 feature flags, validators, and error paths.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from engine.config.schema import (
    DomainSpec,
    GateSpec,
    GateType,
    NullBehavior,
)
from engine.config.settings import Settings

# Canonical patch target — all `from engine.config.settings import settings`
# binds the module-level singleton, so we patch the object at its source.
_SETTINGS_TARGET = "engine.config.settings.settings"


# ── Helpers ──────────────────────────────────────────────


def _minimal_spec_raw(**overrides: Any) -> dict[str, Any]:
    """Build a minimal domain spec dict, with optional overrides."""
    base: dict[str, Any] = {
        "domain": {"id": "test", "name": "Test Domain", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [
                        {"name": "facility_id", "type": "int", "required": True},
                        {"name": "name", "type": "string"},
                        {"name": "lat", "type": "float"},
                        {"name": "lon", "type": "float"},
                        {"name": "credit_score", "type": "float"},
                        {"name": "min_density", "type": "float"},
                        {"name": "max_density", "type": "float"},
                        {"name": "is_active", "type": "bool"},
                    ],
                },
                {
                    "label": "MaterialIntake",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [
                        {"name": "intake_id", "type": "int", "required": True},
                    ],
                },
            ],
            "edges": [
                {
                    "type": "EXCLUDED_FROM",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "exclusion",
                    "managedby": "sync",
                },
            ],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "intake_to_buyer"}],
            "queryentity": [{"label": "MaterialIntake", "matchdirection": "intake_to_buyer"}],
        },
        "queryschema": {
            "matchdirections": ["intake_to_buyer"],
            "fields": [
                {"name": "density", "type": "float"},
                {"name": "target_score", "type": "float"},
            ],
        },
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }
    base.update(overrides)
    return base


def _make_settings(**overrides: Any) -> Settings:
    """Create a Settings instance with overrides (avoids .env side effects)."""
    defaults = {
        "neo4j_password": "test-pw",
        "api_secret_key": "test-key",
        "l9_env": "dev",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# W1-01: Domain-Spec Cross-Reference Invariant Validators
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestW101DomainCrossRef:
    """W1-01: Domain-spec cross-reference validators."""

    def test_valid_spec_passes(self) -> None:
        """A well-formed spec passes all cross-reference checks."""
        raw = _minimal_spec_raw()
        spec = DomainSpec.model_validate(raw)
        assert spec.domain.id == "test"

    def test_edge_source_unknown_node_raises(self) -> None:
        """W1-01(a): Edge source referencing an undeclared node is rejected."""
        raw = _minimal_spec_raw()
        raw["ontology"]["edges"].append(
            {
                "type": "LINKS_TO",
                "from": "GhostNode",
                "to": "Facility",
                "direction": "DIRECTED",
                "category": "capability",
                "managedby": "sync",
            }
        )
        with pytest.raises(ValueError, match="source 'GhostNode' not found"):
            DomainSpec.model_validate(raw)

    def test_edge_target_unknown_node_raises(self) -> None:
        """W1-01(a): Edge target referencing an undeclared node is rejected."""
        raw = _minimal_spec_raw()
        raw["ontology"]["edges"].append(
            {
                "type": "LINKS_TO",
                "from": "Facility",
                "to": "PhantomNode",
                "direction": "DIRECTED",
                "category": "capability",
                "managedby": "sync",
            }
        )
        with pytest.raises(ValueError, match="target 'PhantomNode' not found"):
            DomainSpec.model_validate(raw)

    def test_edge_validation_skipped_when_flag_off(self) -> None:
        """W1-01: Edge validation is skipped when DOMAIN_STRICT_VALIDATION=False."""
        raw = _minimal_spec_raw()
        raw["ontology"]["edges"].append(
            {
                "type": "LINKS_TO",
                "from": "GhostNode",
                "to": "Facility",
                "direction": "DIRECTED",
                "category": "capability",
                "managedby": "sync",
            }
        )
        s = _make_settings(domain_strict_validation=False)
        with patch(_SETTINGS_TARGET, s):
            spec = DomainSpec.model_validate(raw)
            assert spec is not None

    def test_scoring_weight_sum_exceeds_ceiling_raises(self) -> None:
        """W1-01(c): Total scoring default weights > 1.0 is rejected."""
        raw = _minimal_spec_raw()
        raw["scoring"] = {
            "dimensions": [
                {
                    "name": "dim1",
                    "source": "candidateproperty",
                    "candidateprop": "credit_score",
                    "computation": "candidateproperty",
                    "weightkey": "w1",
                    "defaultweight": 0.6,
                },
                {
                    "name": "dim2",
                    "source": "candidateproperty",
                    "candidateprop": "lat",
                    "computation": "candidateproperty",
                    "weightkey": "w2",
                    "defaultweight": 0.6,
                },
            ],
        }
        with pytest.raises(ValueError, match="weights sum to"):
            DomainSpec.model_validate(raw)

    def test_scoring_weight_sum_at_ceiling_passes(self) -> None:
        """W1-01(c): Weights summing to exactly 1.0 are allowed."""
        raw = _minimal_spec_raw()
        raw["scoring"] = {
            "dimensions": [
                {
                    "name": "dim1",
                    "source": "candidateproperty",
                    "candidateprop": "credit_score",
                    "computation": "candidateproperty",
                    "weightkey": "w1",
                    "defaultweight": 0.5,
                },
                {
                    "name": "dim2",
                    "source": "candidateproperty",
                    "candidateprop": "lat",
                    "computation": "candidateproperty",
                    "weightkey": "w2",
                    "defaultweight": 0.5,
                },
            ],
        }
        spec = DomainSpec.model_validate(raw)
        assert len(spec.scoring.dimensions) == 2

    def test_gate_exclusion_unknown_edge_raises(self) -> None:
        """Exclusion gate referencing unknown edge type is rejected."""
        raw = _minimal_spec_raw()
        raw["gates"] = [
            {
                "name": "excl_gate",
                "type": "exclusion",
                "edgetype": "NONEXISTENT_EDGE",
                "nullbehavior": "pass",
            }
        ]
        with pytest.raises(ValueError, match="unknown edge type"):
            DomainSpec.model_validate(raw)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# W1-02: Score-Range Invariants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestW102ScoreRange:
    """W1-02: Score clamping and weight validation."""

    def test_clamp_expression(self) -> None:
        """The _clamp_expression wraps an expression in a CASE clamp."""
        from engine.scoring.assembler import ScoringAssembler

        result = ScoringAssembler._clamp_expression("candidate.score")
        assert "CASE WHEN" in result
        assert "< 0.0 THEN 0.0" in result
        assert "> 1.0 THEN 1.0" in result
        assert "candidate.score" in result

    def test_scoring_assembler_clamps_when_enabled(self) -> None:
        """Dimension expressions are clamped when SCORE_CLAMP_ENABLED=True."""
        raw = _minimal_spec_raw()
        raw["scoring"] = {
            "dimensions": [
                {
                    "name": "test_dim",
                    "source": "candidateproperty",
                    "candidateprop": "credit_score",
                    "computation": "candidateproperty",
                    "weightkey": "w_test",
                    "defaultweight": 0.5,
                },
            ],
        }
        spec = DomainSpec.model_validate(raw)

        from engine.scoring.assembler import ScoringAssembler

        assembler = ScoringAssembler(spec)
        s = _make_settings(score_clamp_enabled=True)
        with patch(_SETTINGS_TARGET, s):
            clause, _ = assembler.assemble_scoring_clause("intake_to_buyer", {})
        assert "CASE WHEN" in clause

    def test_scoring_assembler_no_clamp_when_disabled(self) -> None:
        """Dimension expressions are NOT clamped when SCORE_CLAMP_ENABLED=False."""
        raw = _minimal_spec_raw()
        raw["scoring"] = {
            "dimensions": [
                {
                    "name": "test_dim",
                    "source": "candidateproperty",
                    "candidateprop": "credit_score",
                    "computation": "candidateproperty",
                    "weightkey": "w_test",
                    "defaultweight": 0.5,
                },
            ],
        }
        spec = DomainSpec.model_validate(raw)

        from engine.scoring.assembler import ScoringAssembler

        assembler = ScoringAssembler(spec)
        s = _make_settings(score_clamp_enabled=False)
        with patch(_SETTINGS_TARGET, s):
            clause, _ = assembler.assemble_scoring_clause("intake_to_buyer", {})
        # The raw expression (before AS test_dim) should NOT be wrapped in CASE clamp
        before_alias = clause.split("AS test_dim")[0]
        assert "CASE WHEN" not in before_alias

    def test_match_weight_validation_rejects_negative(self) -> None:
        """User-supplied negative weight is rejected."""
        from engine.handlers import ValidationError, _validate_match_weights

        with pytest.raises(ValidationError, match="outside allowed range"):
            _validate_match_weights({"w1": -0.1}, "test-tenant")

    def test_match_weight_validation_rejects_over_one(self) -> None:
        """User-supplied weight > 1.0 is rejected."""
        from engine.handlers import ValidationError, _validate_match_weights

        with pytest.raises(ValidationError, match="outside allowed range"):
            _validate_match_weights({"w1": 1.5}, "test-tenant")

    def test_match_weight_validation_rejects_sum_over_one(self) -> None:
        """Weights summing to > 1.0 are rejected."""
        from engine.handlers import ValidationError, _validate_match_weights

        with pytest.raises(ValidationError, match="Weights sum to"):
            _validate_match_weights({"w1": 0.6, "w2": 0.6}, "test-tenant")

    def test_match_weight_validation_valid_passes(self) -> None:
        """Valid weights pass without error."""
        from engine.handlers import _validate_match_weights

        _validate_match_weights({"w1": 0.3, "w2": 0.3}, "test-tenant")

    def test_boot_weight_sum_assertion_passes_default(self) -> None:
        """Default weights (0.30+0.25+0.20+0.10=0.85) pass the assertion."""
        from engine.boot import _assert_default_weight_sum

        s = _make_settings()
        with patch("engine.boot.settings", s):
            _assert_default_weight_sum()  # Should not raise

    def test_boot_weight_sum_assertion_fails_overflow(self) -> None:
        """Weights summing to > 1.0 fail the startup assertion."""
        from engine.boot import _assert_default_weight_sum

        s = _make_settings(w_structural=0.5, w_geo=0.3, w_reinforcement=0.2, w_freshness=0.2)
        with patch("engine.boot.settings", s):
            with pytest.raises(ValueError, match="Default scoring weights sum to"):
                _assert_default_weight_sum()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# W1-03: Gate Compilation Invariants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestW103GateInvariants:
    """W1-03: Null-semantic and type-consistency gate checks."""

    def test_validate_gates_missing_param(self) -> None:
        """Missing parameter in resolved set is flagged."""
        raw = _minimal_spec_raw()
        raw["gates"] = [
            {
                "name": "threshold_gate",
                "type": "threshold",
                "candidateprop": "credit_score",
                "queryparam": "target_score",
                "operator": ">=",
                "nullbehavior": "pass",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.gates.compiler import GateCompiler

        compiler = GateCompiler(spec)
        s = _make_settings(strict_null_gates=True)
        with patch(_SETTINGS_TARGET, s):
            warnings = compiler.validate_gates(resolved_params={"other_param": 42})
        assert any("target_score" in w for w in warnings)

    def test_validate_gates_null_param(self) -> None:
        """Null-resolved parameter is flagged when strict mode on."""
        raw = _minimal_spec_raw()
        raw["gates"] = [
            {
                "name": "threshold_gate",
                "type": "threshold",
                "candidateprop": "credit_score",
                "queryparam": "target_score",
                "operator": ">=",
                "nullbehavior": "pass",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.gates.compiler import GateCompiler

        compiler = GateCompiler(spec)
        s = _make_settings(strict_null_gates=True)
        with patch(_SETTINGS_TARGET, s):
            warnings = compiler.validate_gates(resolved_params={"target_score": None})
        assert any("resolved to null" in w for w in warnings)

    def test_validate_gates_operator_type_mismatch(self) -> None:
        """Numeric operator on string property is flagged."""
        raw = _minimal_spec_raw()
        raw["gates"] = [
            {
                "name": "name_gate",
                "type": "threshold",
                "candidateprop": "name",
                "queryparam": "target_score",
                "operator": ">=",
                "nullbehavior": "pass",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.gates.compiler import GateCompiler

        compiler = GateCompiler(spec)
        s = _make_settings(strict_null_gates=True)
        with patch(_SETTINGS_TARGET, s):
            warnings = compiler.validate_gates(resolved_params={"target_score": 5})
        assert any("incompatible" in w for w in warnings)

    def test_validate_gates_clean_passes(self) -> None:
        """Well-formed gates produce no warnings."""
        raw = _minimal_spec_raw()
        raw["gates"] = [
            {
                "name": "threshold_gate",
                "type": "threshold",
                "candidateprop": "credit_score",
                "queryparam": "target_score",
                "operator": ">=",
                "nullbehavior": "pass",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.gates.compiler import GateCompiler

        compiler = GateCompiler(spec)
        s = _make_settings(strict_null_gates=True)
        with patch(_SETTINGS_TARGET, s):
            warnings = compiler.validate_gates(resolved_params={"target_score": 5.0})
        assert len(warnings) == 0

    def test_gate_operator_validation_rejects_bad_operator(self) -> None:
        """W1-03: GateSpec rejects unknown operators."""
        with pytest.raises(ValueError, match="not in the allowed set"):
            GateSpec(
                name="bad_op",
                type=GateType.THRESHOLD,
                candidateprop="credit_score",
                queryparam="target",
                operator="LIKE",
                nullbehavior=NullBehavior.PASS,
            )

    def test_gate_operator_validation_allows_valid(self) -> None:
        """W1-03: GateSpec accepts known operators."""
        gate = GateSpec(
            name="good_op",
            type=GateType.THRESHOLD,
            candidateprop="credit_score",
            queryparam="target",
            operator=">=",
            nullbehavior=NullBehavior.PASS,
        )
        assert gate.operator == ">="


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# W1-04: Traversal Pattern Validators
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestW104TraversalValidators:
    """W1-04: Hop count, direction, and label-reference validators."""

    def test_hop_count_within_cap_passes(self) -> None:
        """Traversal with hops within MAX_HOP_HARD_CAP passes."""
        raw = _minimal_spec_raw()
        raw["traversal"] = {
            "steps": [
                {
                    "name": "step1",
                    "pattern": "(candidate:Facility)-[:EXCLUDED_FROM*1..3]->(target:Facility)",
                    "required": True,
                },
            ],
        }
        s = _make_settings(max_hop_hard_cap=10)
        with patch(_SETTINGS_TARGET, s):
            spec = DomainSpec.model_validate(raw)
        assert spec.traversal is not None

    def test_hop_count_exceeds_cap_raises(self) -> None:
        """Traversal with hops exceeding MAX_HOP_HARD_CAP is rejected."""
        raw = _minimal_spec_raw()
        raw["traversal"] = {
            "steps": [
                {
                    "name": "step1",
                    "pattern": "(candidate:Facility)-[:EXCLUDED_FROM*1..15]->(target:Facility)",
                    "required": True,
                },
            ],
        }
        s = _make_settings(max_hop_hard_cap=10)
        with patch(_SETTINGS_TARGET, s):
            with pytest.raises(ValueError, match="exceeds hard cap"):
                DomainSpec.model_validate(raw)

    def test_hop_count_zero_raises(self) -> None:
        """Traversal with 0 hops is rejected."""
        raw = _minimal_spec_raw()
        raw["traversal"] = {
            "steps": [
                {
                    "name": "step1",
                    "pattern": "(candidate:Facility)-[:EXCLUDED_FROM*0..3]->(target:Facility)",
                    "required": True,
                },
            ],
        }
        s = _make_settings(max_hop_hard_cap=10)
        with patch(_SETTINGS_TARGET, s):
            with pytest.raises(ValueError, match="hop count must be >= 1"):
                DomainSpec.model_validate(raw)

    def test_validate_traversal_undeclared_label_warning(self) -> None:
        """W1-04: References to undeclared labels/types produce warnings."""
        raw = _minimal_spec_raw()
        raw["traversal"] = {
            "steps": [
                {
                    "name": "step1",
                    "pattern": "(candidate:Facility)-[:UNKNOWN_EDGE]->(target:Facility)",
                    "required": True,
                },
            ],
        }
        s = _make_settings(max_hop_hard_cap=10)
        with patch(_SETTINGS_TARGET, s):
            spec = DomainSpec.model_validate(raw)

        from engine.traversal.assembler import TraversalAssembler

        assembler = TraversalAssembler(spec)
        warnings = assembler.validate_traversal("intake_to_buyer")
        assert any("UNKNOWN_EDGE" in w for w in warnings)

    def test_empty_traversal_passes(self) -> None:
        """Spec with no traversal steps passes validation."""
        raw = _minimal_spec_raw()
        raw["traversal"] = {"steps": []}
        spec = DomainSpec.model_validate(raw)
        assert spec.traversal is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# W1-05: Parameter Resolver Strict Mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestW105ParamStrictMode:
    """W1-05: Parameter resolver strict mode tests."""

    def test_strict_mode_raises_on_bad_expression(self) -> None:
        """Strict mode raises ParameterResolutionError on failed derived param."""
        raw = _minimal_spec_raw()
        raw["derivedparameters"] = [
            {
                "name": "monthly_income",
                "expression": "annualincomeusd / 12.0",
                "type": "float",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.traversal.resolver import ParameterResolutionError, ParameterResolver

        resolver = ParameterResolver(spec)
        s = _make_settings(param_strict_mode=True)
        with patch(_SETTINGS_TARGET, s):
            with pytest.raises(ParameterResolutionError, match="monthly_income"):
                # Missing 'annualincomeusd' in query data → expression fails
                resolver.resolve_parameters({"density": 0.95})

    def test_lenient_mode_swallows_error(self) -> None:
        """Lenient mode logs but doesn't raise on failed derived param."""
        raw = _minimal_spec_raw()
        raw["derivedparameters"] = [
            {
                "name": "monthly_income",
                "expression": "annualincomeusd / 12.0",
                "type": "float",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.traversal.resolver import ParameterResolver

        resolver = ParameterResolver(spec)
        s = _make_settings(param_strict_mode=False)
        with patch(_SETTINGS_TARGET, s):
            result = resolver.resolve_parameters({"density": 0.95})
        # Parameter not resolved — should be absent, not errored
        assert "monthly_income" not in result

    def test_strict_mode_succeeds_for_valid_expression(self) -> None:
        """Strict mode passes when expression evaluates successfully."""
        raw = _minimal_spec_raw()
        raw["derivedparameters"] = [
            {
                "name": "monthly_income",
                "expression": "annualincomeusd / 12.0",
                "type": "float",
            },
        ]
        spec = DomainSpec.model_validate(raw)

        from engine.traversal.resolver import ParameterResolver

        resolver = ParameterResolver(spec)
        s = _make_settings(param_strict_mode=True)
        with patch(_SETTINGS_TARGET, s):
            result = resolver.resolve_parameters({"annualincomeusd": 120000.0})
        assert result["monthly_income"] == 10000.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Feature Flag Toggle Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFeatureFlags:
    """Verify all 5 feature flags exist and default to expected values."""

    def test_all_flags_present(self) -> None:
        """All Wave 1 flags are present in Settings with correct defaults."""
        s = _make_settings()
        assert s.domain_strict_validation is True
        assert s.score_clamp_enabled is True
        assert s.strict_null_gates is True
        assert s.max_hop_hard_cap == 10
        assert s.param_strict_mode is True

    def test_flags_can_be_disabled(self) -> None:
        """All flags can be toggled off."""
        s = _make_settings(
            domain_strict_validation=False,
            score_clamp_enabled=False,
            strict_null_gates=False,
            max_hop_hard_cap=5,
            param_strict_mode=False,
        )
        assert s.domain_strict_validation is False
        assert s.score_clamp_enabled is False
        assert s.strict_null_gates is False
        assert s.max_hop_hard_cap == 5
        assert s.param_strict_mode is False
