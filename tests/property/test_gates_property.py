"""
Property-based tests for gate compilation (W5-05).

Uses Hypothesis to generate random valid GateSpec dicts and verify
that compilation always produces safe, well-formed output.
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
settings = hypothesis.settings
st = hypothesis.strategies

from engine.config.schema import GateSpec, GateType, NullBehavior
from engine.gates.compiler import GateCompiler

# ---------------------------------------------------------------------------
# Custom Hypothesis strategies
# ---------------------------------------------------------------------------

_SAFE_IDENTIFIER = st.from_regex(r"[a-z][a-z0-9_]{1,20}", fullmatch=True)

_GATE_TYPES_WITH_CANDIDATEPROP = [
    GateType.BOOLEAN,
    GateType.THRESHOLD,
    GateType.RANGE,
    GateType.ENUMMAP,
    GateType.SELFRANGE,
    GateType.FRESHNESS,
]

_NULL_BEHAVIORS = st.sampled_from([NullBehavior.PASS, NullBehavior.FAIL])


@st.composite
def gate_spec_strategy(draw):
    """Generate a valid GateSpec for property testing."""
    gate_type = draw(st.sampled_from(_GATE_TYPES_WITH_CANDIDATEPROP))
    name = draw(_SAFE_IDENTIFIER)
    candidateprop = draw(_SAFE_IDENTIFIER)
    queryparam = draw(_SAFE_IDENTIFIER)
    null_behavior = draw(_NULL_BEHAVIORS)

    kwargs = {
        "name": name,
        "type": gate_type,
        "candidateprop": candidateprop,
        "queryparam": queryparam,
        "nullbehavior": null_behavior,
    }

    if gate_type == GateType.THRESHOLD:
        kwargs["operator"] = draw(st.sampled_from([">=", "<=", ">", "<"]))

    if gate_type == GateType.RANGE:
        kwargs["candidateprop_min"] = draw(_SAFE_IDENTIFIER)
        kwargs["candidateprop_max"] = draw(_SAFE_IDENTIFIER)

    if gate_type == GateType.SELFRANGE:
        kwargs["candidateprop_min"] = draw(_SAFE_IDENTIFIER)
        kwargs["candidateprop_max"] = draw(_SAFE_IDENTIFIER)

    if gate_type == GateType.FRESHNESS:
        kwargs["maxagedays"] = draw(st.integers(min_value=1, max_value=365))

    return GateSpec(**kwargs)


# ---------------------------------------------------------------------------
# Minimal spec builder for the compiler
# ---------------------------------------------------------------------------


def _build_spec_with_gates(gates: list[GateSpec]):
    """Build a minimal DomainSpec with given gates."""
    from engine.config.schema import (
        DomainMetadata,
        DomainSpec,
        EdgeCategory,
        EdgeDirection,
        EdgeSpec,
        ManagedByType,
        MatchEntitiesSpec,
        MatchEntitySpec,
        NodeSpec,
        OntologySpec,
        PropertySpec,
        PropertyType,
        QueryFieldSpec,
        QuerySchemaSpec,
        ScoringSpec,
    )

    # Collect all candidateprop and queryparam names to build valid ontology
    prop_names = set()
    param_names = set()
    for g in gates:
        if g.candidateprop:
            prop_names.add(g.candidateprop)
        if g.candidateprop_min:
            prop_names.add(g.candidateprop_min)
        if g.candidateprop_max:
            prop_names.add(g.candidateprop_max)
        if g.queryparam:
            param_names.add(g.queryparam)

    properties = [PropertySpec(name=p, type=PropertyType.FLOAT) for p in prop_names]
    fields = [QueryFieldSpec(name=p, type=PropertyType.FLOAT) for p in param_names]

    return DomainSpec(
        domain=DomainMetadata(id="proptest", name="Property Test", version="1.0.0"),
        ontology=OntologySpec(
            nodes=[
                NodeSpec(label="Candidate", candidate=True, properties=properties),
                NodeSpec(label="Query", queryentity=True),
            ],
            edges=[
                EdgeSpec(
                    type="RELATES",
                    **{"from": "Candidate"},
                    to="Query",
                    direction=EdgeDirection.DIRECTED,
                    category=EdgeCategory.CAPABILITY,
                    managedby=ManagedByType.SYNC,
                ),
            ],
        ),
        matchentities=MatchEntitiesSpec(
            candidate=[MatchEntitySpec(label="Candidate", matchdirection="forward")],
            queryentity=[MatchEntitySpec(label="Query", matchdirection="forward")],
        ),
        queryschema=QuerySchemaSpec(matchdirections=["forward"], fields=fields),
        gates=gates,
        scoring=ScoringSpec(dimensions=[]),
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestGateCompilationProperties:
    """Property-based tests for gate compilation."""

    @given(gate=gate_spec_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_compilation_produces_nonempty_output(self, gate):
        """For any valid GateSpec, compilation produces non-empty output."""
        spec = _build_spec_with_gates([gate])
        compiler = GateCompiler(spec)
        result = compiler.compile(gate)
        assert result, f"Gate {gate.name} ({gate.type}) compiled to empty string"
        assert len(result) > 0

    @given(gate=gate_spec_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_compilation_has_balanced_parentheses(self, gate):
        """For any valid GateSpec, compiled output has balanced parentheses."""
        spec = _build_spec_with_gates([gate])
        compiler = GateCompiler(spec)
        result = compiler.compile(gate)
        assert result.count("(") == result.count(")"), f"Unbalanced parens in: {result}"

    @given(gate=gate_spec_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_no_injection_patterns(self, gate):
        """Compiled gate output contains no dangerous Cypher keywords."""
        spec = _build_spec_with_gates([gate])
        compiler = GateCompiler(spec)
        result = compiler.compile(gate)

        # These should never appear in gate WHERE clauses
        dangerous = ["CREATE", "DELETE", "MERGE", "DETACH", "DROP", "CALL dbms", "LOAD CSV"]
        result_upper = result.upper()
        for keyword in dangerous:
            assert keyword not in result_upper, f"Injection keyword '{keyword}' found in: {result}"

    @given(gate=gate_spec_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_compile_all_gates_wraps_in_and(self, gate):
        """compile_all_gates returns valid combined clause."""
        spec = _build_spec_with_gates([gate])
        compiler = GateCompiler(spec)
        result = compiler.compile_all_gates("forward")
        assert result, "compile_all_gates returned empty"
        # Should either be "true" or contain the gate logic
        assert result == "true" or "candidate" in result or "IS" in result
