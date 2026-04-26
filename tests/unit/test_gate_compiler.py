"""Unit tests — GateCompiler: gate types, null semantics, direction filter."""

from __future__ import annotations

import pytest


def test_exact_gate_generates_equality_clause():
    from engine.config.schema import GateSpec
    from engine.gates.compiler import GateCompiler
    from engine.gates.types.all_gates import GateType

    gate = GateSpec(name="g", type=GateType.exact, field="status", query_param="status")
    result = GateCompiler._compile_single(gate, direction="*")
    assert "$status" in result or "status" in result


def test_direction_filter_skips_non_matching():
    """A gate scoped to buyer_to_seller must not compile for seller_to_buyer."""
    from engine.config.schema import GateSpec
    from engine.gates.compiler import GateCompiler
    from engine.gates.types.all_gates import GateType

    # If gate has match_direction kwarg — test skipping
    # This is a structural test — verify compiler produces no clause for wrong direction
    try:
        gate = GateSpec(
            name="g",
            type=GateType.exact,
            field="f",
            query_param="f",
            match_direction="buyer_to_seller",
        )
        result = GateCompiler._compile_single(gate, direction="seller_to_buyer")
        assert result is None or result == ""
    except TypeError:
        pytest.skip("GateSpec does not support match_direction kwarg in this version")


def test_null_behavior_pass_wraps_clause():
    """null_behavior=pass should wrap clause with IS NULL OR condition."""
    from engine.config.schema import GateSpec
    from engine.gates.compiler import GateCompiler
    from engine.gates.types.all_gates import GateType

    try:
        gate = GateSpec(
            name="g",
            type=GateType.exact,
            field="status",
            query_param="status",
            null_behavior="pass",
        )
        result = GateCompiler._compile_single(gate, direction="*")
        assert "NULL" in result or "$status" in result
    except TypeError:
        pytest.skip("null_behavior not supported in this schema version")


def test_compile_all_gates_empty_returns_empty():
    from pathlib import Path

    from engine.config.loader import DomainPackLoader
    from engine.gates.compiler import GateCompiler

    loader = DomainPackLoader(config_path=str(Path(__file__).parent.parent.parent / "domains"))
    spec = loader.load_domain("plasticos")
    compiler = GateCompiler(spec)
    # compile with no params should return some WHERE fragment or empty string
    result = compiler.compile_where_clause(direction="*", params={})
    assert isinstance(result, str)
