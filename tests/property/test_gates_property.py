"""
Property-based tests for gate compilation (W5-05).

Uses Hypothesis to generate random valid GateSpec dicts and verify
that compilation always produces safe, well-formed output.
"""

from __future__ import annotations

import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    from engine.config.schema import GateSpec, GateType, NullBehavior
    from engine.gates.compiler import GateCompiler
except ModuleNotFoundError:
    pytest.skip("hypothesis not installed", allow_module_level=True)

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
                    direction=EdgeDirection.OUTBOUND,
                    category=EdgeCategory.MATCH,
                    managedby=ManagedByType.ENGINE,
                )
            ],
        ),
        queryschema=QuerySchemaSpec(fields=fields),
        matchentities=MatchEntitiesSpec(candidate=[MatchEntitySpec(label="Candidate", matchdirection="*")]),
        scoring=ScoringSpec(dimensions=[]),
        gates=gates,
    )


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@given(st.lists(gate_spec_strategy(), min_size=1, max_size=12))
@settings(max_examples=50, deadline=None)
def test_compiled_gates_are_safe_and_nonempty(gates: list[GateSpec]):
    """Compiler should always emit a safe WHERE clause for valid gates."""
    spec = _build_spec_with_gates(gates)
    compiler = GateCompiler(spec)
    cypher = compiler.compile_all_gates("*")

    assert isinstance(cypher, str)
    assert cypher.strip()
    assert "MATCH" not in cypher.upper()
    assert "DELETE" not in cypher.upper()
    assert "REMOVE" not in cypher.upper()


@given(gate_spec_strategy())
@settings(max_examples=50, deadline=None)
def test_single_gate_compiles_without_exception(gate: GateSpec):
    """Any valid gate should compile without raising."""
    spec = _build_spec_with_gates([gate])
    compiler = GateCompiler(spec)
    cypher = compiler.compile_all_gates("*")
    assert isinstance(cypher, str)
    assert cypher.strip()
