"""
Data model contract tests for OutcomeRecord, graph-schema, and shared models.

Sources:
  engine/models/outcomes.py:OutcomeRecord
  engine/handlers.py:handle_outcomes(), handle_resolve()
  engine/config/schema.py:OntologySpec, NodeSpec, EdgeSpec
  docs/contracts/data/graph-schema.yaml
"""

import pytest

try:
    from jsonschema import ValidationError, validate
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)


def _make_outcome(**overrides) -> dict:
    base = {
        "match_id": "match_abc123",
        "candidate_id": "buyer_042",
        "outcome": "success",
        "dimension_scores": {
            "structural": 0.92,
            "geo": 0.71,
            "reinforcement": 0.88,
            "freshness": 0.95,
        },
        "was_selected": True,
    }
    base.update(overrides)
    return base


def test_outcome_schema_has_meta(outcome_record_schema):
    assert outcome_record_schema.get("type") == "object"
    assert "$schema" in outcome_record_schema
    assert "title" in outcome_record_schema


def test_outcome_schema_required_fields(outcome_record_schema):
    required = set(outcome_record_schema.get("required", []))
    for field in ("match_id", "candidate_id", "dimension_scores", "was_selected"):
        assert field in required, (
            f"OutcomeRecord.required must include '{field}'. Source: engine/models/outcomes.py:OutcomeRecord"
        )


def test_outcome_dimension_scores_type(outcome_record_schema):
    prop = outcome_record_schema["properties"]["dimension_scores"]
    assert prop.get("type") == "object"
    additional = prop.get("additionalProperties", {})
    assert additional.get("type") == "number"


def test_outcome_feedback_score_bounded(outcome_record_schema):
    prop = outcome_record_schema["properties"].get("feedback_score", {})
    assert prop.get("minimum") == 0.0, "feedback_score minimum must be 0.0"
    assert prop.get("maximum") == 1.0, "feedback_score maximum must be 1.0"


def test_outcome_feedback_score_nullable(outcome_record_schema):
    prop = outcome_record_schema["properties"].get("feedback_score", {})
    type_val = prop.get("type", "")
    is_nullable = (isinstance(type_val, list) and "null" in type_val) or prop.get("nullable") is True
    assert is_nullable, "feedback_score must be nullable (optional field)"


def test_outcome_schema_has_examples(outcome_record_schema):
    assert outcome_record_schema.get("examples"), "OutcomeRecord schema missing examples"


def test_valid_outcome_passes_schema(outcome_record_schema):
    validate(instance=_make_outcome(), schema=outcome_record_schema)


def test_outcome_missing_match_id_fails(outcome_record_schema):
    data = _make_outcome()
    del data["match_id"]
    with pytest.raises(ValidationError):
        validate(instance=data, schema=outcome_record_schema)


def test_outcome_missing_was_selected_fails(outcome_record_schema):
    data = _make_outcome()
    del data["was_selected"]
    with pytest.raises(ValidationError):
        validate(instance=data, schema=outcome_record_schema)


def test_outcome_additional_properties_rejected(outcome_record_schema):
    if outcome_record_schema.get("additionalProperties") is not False:
        pytest.skip("additionalProperties not set to false — strict mode not enabled")
    data = _make_outcome(unknown_field="bad")
    with pytest.raises(ValidationError):
        validate(instance=data, schema=outcome_record_schema)


# ── Graph Schema ─────────────────────────────────────────────────────────────


def test_graph_schema_has_system_nodes(graph_schema):
    assert "system_nodes" in graph_schema, (
        "graph-schema.yaml must define system_nodes. Source: engine/handlers.py:handle_outcomes()"
    )


def test_transaction_outcome_node_defined(graph_schema):
    labels = [n.get("label") for n in graph_schema.get("system_nodes", [])]
    assert "TransactionOutcome" in labels


def test_transaction_outcome_has_required_properties(graph_schema):
    node = next(
        (n for n in graph_schema.get("system_nodes", []) if n.get("label") == "TransactionOutcome"),
        None,
    )
    assert node is not None, "TransactionOutcome node not found"
    prop_names = {p["name"] for p in node.get("properties", [])}
    for field in ("outcome_id", "match_id", "candidate_id", "outcome", "created_at"):
        assert field in prop_names, f"TransactionOutcome missing property '{field}'"


def test_graph_schema_has_system_edges(graph_schema):
    assert "system_edges" in graph_schema


def test_resulted_in_edge_defined(graph_schema):
    edge_types = [e.get("type") for e in graph_schema.get("system_edges", [])]
    assert "RESULTED_IN" in edge_types


def test_resolved_from_edge_defined(graph_schema):
    edge_types = [e.get("type") for e in graph_schema.get("system_edges", [])]
    assert "RESOLVED_FROM" in edge_types


def test_graph_schema_has_domain_abstraction_note(graph_schema):
    assert "domain_schema_abstraction" in graph_schema
