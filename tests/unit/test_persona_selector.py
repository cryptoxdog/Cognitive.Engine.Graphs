"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, personas, selector, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for persona selector: scoring and low-confidence fallback.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

import pytest

from engine.personas.selector import score_personas, select_personas
from engine.personas.types import FeatureVector, Persona, TraitVector


def _make_persona(pid: str, name: str = "Test", **trait_kwargs: float) -> Persona:
    """Helper to build a Persona with custom traits."""
    tv = TraitVector(**trait_kwargs)
    return Persona(id=pid, name=name, trait_vector=tv)


@pytest.mark.unit
class TestScorePersonas:
    """Test dot-product persona scoring."""

    def test_scoring_order(self) -> None:
        """Personas are returned sorted by score descending."""
        p1 = _make_persona("p1", "Low", analytical_depth=0.1)
        p2 = _make_persona("p2", "High", analytical_depth=0.9)
        p3 = _make_persona("p3", "Mid", analytical_depth=0.5)

        fv = FeatureVector(analytical_depth=1.0)
        scored = score_personas(fv, [p1, p2, p3])

        names = [s["persona"].name for s in scored]  # type: ignore[union-attr]
        assert names == ["High", "Mid", "Low"]

    def test_dot_product_calculation(self) -> None:
        """Score is dot product of feature vector x trait vector."""
        p = _make_persona("p1", analytical_depth=0.5, creativity=0.3)
        fv = FeatureVector(analytical_depth=0.8, creativity=0.6)

        scored = score_personas(fv, [p])

        # Expected: 0.5*0.8 + 0.3*0.6 = 0.4 + 0.18 = 0.58
        assert float(scored[0]["score"]) == pytest.approx(0.58)

    def test_zero_feature_vector(self) -> None:
        """Zero feature vector gives zero scores."""
        p = _make_persona("p1", analytical_depth=0.9, creativity=0.8)
        fv = FeatureVector()  # all zeros

        scored = score_personas(fv, [p])

        assert float(scored[0]["score"]) == 0.0

    def test_empty_personas_returns_empty(self) -> None:
        """Empty persona list returns empty results."""
        fv = FeatureVector(analytical_depth=1.0)
        scored = score_personas(fv, [])

        assert scored == []

    def test_multi_dimensional_scoring(self) -> None:
        """Scoring uses all dimensions including primitives and safety."""
        p = _make_persona(
            "p1",
            analytical_depth=0.5,
            verification_need=0.8,
            safety_sensitivity=0.3,
        )
        fv = FeatureVector(
            analytical_depth=0.4,
            verification_need=0.6,
            safety_sensitivity=0.2,
        )

        scored = score_personas(fv, [p])

        # 0.5*0.4 + 0.8*0.6 + 0.3*0.2 = 0.2 + 0.48 + 0.06 = 0.74
        assert float(scored[0]["score"]) == pytest.approx(0.74)


@pytest.mark.unit
class TestSelectPersonas:
    """Test persona selection with fallback."""

    def test_standard_selection(self) -> None:
        """Standard selection returns primary persona when score > threshold."""
        p1 = _make_persona("p1", "Primary", analytical_depth=0.9)
        p2 = _make_persona("p2", "Secondary", analytical_depth=0.1)

        fv = FeatureVector(analytical_depth=1.0)
        active = select_personas(fv, [p1, p2])

        assert len(active) >= 1
        assert active[0].name == "Primary"

    def test_secondary_activation(self) -> None:
        """Secondaries activate when score >= 75% of primary."""
        p1 = _make_persona("p1", "Primary", analytical_depth=0.9)
        p2 = _make_persona("p2", "Secondary", analytical_depth=0.8)  # 0.8/0.9 > 0.75

        fv = FeatureVector(analytical_depth=1.0)
        active = select_personas(fv, [p1, p2])

        assert len(active) == 2

    def test_secondary_excluded_below_ratio(self) -> None:
        """Secondaries excluded when score < 75% of primary."""
        p1 = _make_persona("p1", "Primary", analytical_depth=0.9)
        p2 = _make_persona("p2", "Weak", analytical_depth=0.1)  # 0.1/0.9 < 0.75

        fv = FeatureVector(analytical_depth=1.0)
        active = select_personas(fv, [p1, p2])

        assert len(active) == 1
        assert active[0].name == "Primary"

    def test_max_personas_limit(self) -> None:
        """Selection never exceeds max_personas (3)."""
        personas = [_make_persona(f"p{i}", f"P{i}", analytical_depth=0.9 - i * 0.01) for i in range(5)]

        fv = FeatureVector(analytical_depth=1.0)
        active = select_personas(fv, personas)

        assert len(active) <= 3

    def test_low_confidence_fallback(self) -> None:
        """Low confidence triggers composite persona creation."""
        # All personas have very low trait alignment
        p1 = _make_persona("p1", "Weak1", analytical_depth=0.01)
        p2 = _make_persona("p2", "Weak2", creativity=0.01)
        p3 = _make_persona("p3", "Weak3", precision=0.01)

        # Feature vector mostly orthogonal
        fv = FeatureVector(analytical_depth=0.1)
        active = select_personas(fv, [p1, p2, p3])

        # Should get exactly 1 composite persona
        assert len(active) == 1
        assert active[0].is_composite is True

    def test_empty_personas_returns_empty(self) -> None:
        """Empty persona list returns empty results."""
        fv = FeatureVector(analytical_depth=1.0)
        active = select_personas(fv, [])

        assert active == []
