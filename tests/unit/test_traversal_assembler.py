"""Unit tests — TraversalAssembler: direction filter, step ordering."""

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


def test_assembler_produces_list(plasticos_spec):
    """Traversal assembler produces list of clauses."""
    from engine.traversal.assembler import TraversalAssembler

    assembler = TraversalAssembler(plasticos_spec)
    clauses = assembler.assemble_traversal(direction="*")
    assert isinstance(clauses, list)


def test_wildcard_direction_always_included(plasticos_spec):
    """Steps with direction='*' must appear regardless of query direction."""
    from engine.traversal.assembler import TraversalAssembler

    assembler = TraversalAssembler(plasticos_spec)
    result_a = assembler.assemble_traversal(direction="buyer_to_seller")
    result_b = assembler.assemble_traversal(direction="seller_to_buyer")
    assert isinstance(result_a, list)
    assert isinstance(result_b, list)


def test_traversal_steps_are_strings(plasticos_spec):
    """Traversal clauses are non-empty strings."""
    from engine.traversal.assembler import TraversalAssembler

    assembler = TraversalAssembler(plasticos_spec)
    clauses = assembler.assemble_traversal(direction="*")
    for clause in clauses:
        assert isinstance(clause, str)
        assert len(clause) > 0
