# tests/test_scoring_extended.py
"""Tests for traversalalias, kge, and candidateproperty C-06 fix."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from engine.config.schema import ComputationType
from engine.scoring.assembler import ScoringAssembler


def _dim(*, computation: ComputationType, alias: str | None = None,
         candidateprop: str | None = None, defaultwhennull: float = 0.0) -> MagicMock:
    d = MagicMock()
    d.name = "test"
    d.computation = computation
    d.alias = alias
    d.candidateprop = candidateprop
    d.defaultwhennull = defaultwhennull
    d.queryprop = None
    d.expression = None
    d.matchdirections = None
    d.weightkey = "test"
    d.defaultweight = 1.0
    return d


def _asm(dims: list | None = None) -> ScoringAssembler:
    spec = MagicMock()
    spec.scoring.dimensions = dims or []
    return ScoringAssembler(spec)


def test_traversalalias_with_alias() -> None:
    dim = _dim(computation=ComputationType.TRAVERSALALIAS, alias="rel_sc", candidateprop="score")
    assert _asm()._compile_traversalalias(dim) == "coalesce(rel_sc.score, 0.0)"


def test_traversalalias_default_prop() -> None:
    dim = _dim(computation=ComputationType.TRAVERSALALIAS, alias="edge1")
    assert _asm()._compile_traversalalias(dim) == "coalesce(edge1.score, 0.0)"


def test_traversalalias_no_alias_raises() -> None:
    with pytest.raises(ValueError, match="requires \'alias\'"):
        _asm()._compile_traversalalias(_dim(computation=ComputationType.TRAVERSALALIAS))


def test_kge_with_alias() -> None:
    dim = _dim(computation=ComputationType.KGE, alias="kge_rel", candidateprop="kge_score")
    assert _asm()._compile_kge(dim) == "coalesce(kge_rel.kge_score, 0.0)"


def test_kge_candidateprop_only() -> None:
    dim = _dim(computation=ComputationType.KGE, candidateprop="embedding_sim")
    assert _asm()._compile_kge(dim) == "coalesce(candidate.embedding_sim, 0.0)"


def test_kge_no_source_raises() -> None:
    with pytest.raises(ValueError, match="requires \'alias\' or \'candidateprop\'"):
        _asm()._compile_kge(_dim(computation=ComputationType.KGE))


def test_candidateproperty_default_is_safe_literal() -> None:
    dim = _dim(computation=ComputationType.CANDIDATEPROPERTY, candidateprop="quality", defaultwhennull=0.5)
    result = _asm()._compile_candidateproperty(dim)
    assert "0.5" in result
    assert "$" not in result
