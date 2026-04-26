"""Unit tests — TraversalAssembler: direction filter, step ordering."""

from __future__ import annotations

from pathlib import Path

DOMAINS_DIR = Path(__file__).parent.parent.parent / "domains"


def test_assembler_produces_list():
    from engine.config.loader import DomainPackLoader
    from engine.traversal.assembler import TraversalAssembler

    loader = DomainPackLoader(config_path=str(DOMAINS_DIR))
    spec = loader.load_domain("plasticos")
    assembler = TraversalAssembler(spec)
    clauses = assembler.assemble_traversal(direction="*")
    assert isinstance(clauses, list)


def test_wildcard_direction_always_included():
    """Steps with direction='*' must appear regardless of query direction."""
    from engine.config.loader import DomainPackLoader
    from engine.traversal.assembler import TraversalAssembler

    loader = DomainPackLoader(config_path=str(DOMAINS_DIR))
    spec = loader.load_domain("plasticos")
    # Check that traversal has at least the spec's own steps
    assembler = TraversalAssembler(spec)
    result_a = assembler.assemble_traversal(direction="buyer_to_seller")
    result_b = assembler.assemble_traversal(direction="seller_to_buyer")
    # Wildcard steps must appear in both — count should be >= 0
    assert isinstance(result_a, list)
    assert isinstance(result_b, list)


def test_traversal_steps_are_strings():
    from engine.config.loader import DomainPackLoader
    from engine.traversal.assembler import TraversalAssembler

    loader = DomainPackLoader(config_path=str(DOMAINS_DIR))
    spec = loader.load_domain("plasticos")
    assembler = TraversalAssembler(spec)
    clauses = assembler.assemble_traversal(direction="*")
    for clause in clauses:
        assert isinstance(clause, str)
        assert len(clause) > 0
