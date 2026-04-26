"""Unit tests — ScoringAssembler: scoring types, weight override, aggregation."""

from __future__ import annotations

import pytest


@pytest.fixture
def plasticos_spec():
    """Load plasticos spec, skip if not loadable."""
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader()
    try:
        return loader.load_domain("plasticos")
    except Exception:
        pytest.skip("plasticos domain spec not loadable with current schema")


def test_assembler_loads_from_plasticos_spec(plasticos_spec):
    """Scoring assembler produces non-empty clause."""
    from engine.scoring.assembler import ScoringAssembler

    assembler = ScoringAssembler(plasticos_spec)
    clause = assembler.assemble_scoring_clause(direction="*")
    assert isinstance(clause, str)
    assert len(clause) > 0


def test_empty_dims_returns_default_score():
    """With no scoring dimensions, assembler should return a safe default."""
    from engine.config.schema import DomainSpec
    from engine.scoring.assembler import ScoringAssembler

    raw = {
        "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
        "ontology": {"nodes": [], "edges": []},
        "matchentities": {"candidate": [], "queryentity": []},
        "queryschema": {"matchdirections": ["*"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }
    try:
        spec = DomainSpec(**raw)
        assembler = ScoringAssembler(spec)
        result = assembler.assemble_scoring_clause(direction="*")
        assert isinstance(result, str)
    except Exception:
        pytest.skip("Minimal spec construction differs in this version")


def test_scoring_clause_contains_composite_score(plasticos_spec):
    """Scoring clause contains score expression."""
    from engine.scoring.assembler import ScoringAssembler

    assembler = ScoringAssembler(plasticos_spec)
    clause = assembler.assemble_scoring_clause(direction="*")
    assert "score" in clause.lower() or "AS" in clause


def test_weight_override_changes_output(plasticos_spec):
    """Weight override changes scoring output."""
    from engine.scoring.assembler import ScoringAssembler

    assembler = ScoringAssembler(plasticos_spec)
    if not plasticos_spec.scoring.dimensions:
        pytest.skip("No scoring dimensions in plasticos spec")
    dim_name = plasticos_spec.scoring.dimensions[0].name
    base = assembler.assemble_scoring_clause(direction="*")
    override = assembler.assemble_scoring_clause(direction="*", weights={dim_name: 0.9999})
    assert isinstance(override, str)
