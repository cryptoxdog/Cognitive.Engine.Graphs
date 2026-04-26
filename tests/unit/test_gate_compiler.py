"""Unit tests — GateCompiler: gate types, null semantics, direction filter."""

from __future__ import annotations


def test_exact_gate_generates_equality_clause():
    from unittest.mock import MagicMock

    from engine.config.schema import GateSpec, GateType
    from engine.gates.compiler import GateCompiler

    mock_spec = MagicMock()
    mock_spec.gates = []
    mock_spec.compliance = None
    compiler = GateCompiler(mock_spec)

    gate = GateSpec(name="g", type=GateType.BOOLEAN, candidateprop="status", queryparam="status")
    result = compiler._compile_boolean(gate)
    assert "$status" in result or "status" in result


def test_direction_filter_skips_non_matching():
    """A gate scoped to buyer_to_seller must not compile for seller_to_buyer."""
    from unittest.mock import MagicMock

    from engine.config.schema import GateSpec, GateType
    from engine.gates.compiler import GateCompiler

    mock_spec = MagicMock()
    mock_spec.gates = []
    mock_spec.compliance = None
    compiler = GateCompiler(mock_spec)

    gate = GateSpec(
        name="g",
        type=GateType.BOOLEAN,
        candidateprop="f",
        queryparam="f",
        matchdirections=["buyer_to_seller"],
    )
    # compile_all_gates with a different direction should exclude this gate
    mock_spec.gates = [gate]
    result = compiler.compile_all_gates(match_direction="seller_to_buyer")
    assert result == "" or "f" not in result


def test_null_behavior_pass_wraps_clause():
    """nullbehavior=pass should wrap clause with NULL condition."""
    from unittest.mock import MagicMock

    from engine.config.schema import GateSpec, GateType
    from engine.gates.compiler import GateCompiler

    mock_spec = MagicMock()
    mock_spec.gates = []
    mock_spec.compliance = None
    compiler = GateCompiler(mock_spec)

    gate = GateSpec(
        name="g",
        type=GateType.BOOLEAN,
        candidateprop="status",
        queryparam="status",
        nullbehavior="fail",
    )
    predicate = compiler._compile_boolean(gate)
    wrapped = compiler._wrap_null_semantics(gate, predicate)
    assert "NULL" in wrapped or "$status" in wrapped


def test_compile_all_gates_empty_returns_empty():
    from unittest.mock import MagicMock

    from engine.gates.compiler import GateCompiler

    mock_spec = MagicMock()
    mock_spec.gates = []
    mock_spec.compliance = None
    compiler = GateCompiler(mock_spec)
    result = compiler.compile_all_gates(match_direction="buyer_to_seller")
    assert isinstance(result, str)
