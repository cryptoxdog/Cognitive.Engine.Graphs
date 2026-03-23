"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, personas, composition, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for algebraic persona composition engine.
Tests composeTraitVectors, blendPersonas, and createCompositePersona.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

import pytest

from engine.personas.composer import blend_personas, compose_trait_vectors, create_composite_persona
from engine.personas.types import FeatureVector, Persona, TraitVector


def _make_persona(
    pid: str = "p1",
    name: str = "TestPersona",
    system_prompt: str = "You are a test persona.",
    forbidden: list[str] | None = None,
    **trait_kwargs: float,
) -> Persona:
    """Helper to build a Persona with custom trait vector dimensions."""
    tv = TraitVector(**trait_kwargs)
    return Persona(
        id=pid,
        name=name,
        system_prompt=system_prompt,
        trait_vector=tv,
        forbidden_behaviors=forbidden or [],
    )


@pytest.mark.unit
class TestComposeTraitVectors:
    """Test algebraic trait vector composition operations."""

    def test_add_operation(self) -> None:
        """Add operation: base + weight * modifier."""
        base = TraitVector(analytical_depth=0.5, creativity=0.3)
        modifier = TraitVector(analytical_depth=0.2, creativity=0.4)

        result = compose_trait_vectors(base, modifier, "add", weight=1.0)

        assert result.analytical_depth == pytest.approx(0.7)
        assert result.creativity == pytest.approx(0.7)

    def test_add_with_weight(self) -> None:
        """Add with weight < 1 scales the modifier."""
        base = TraitVector(precision=0.5)
        modifier = TraitVector(precision=0.4)

        result = compose_trait_vectors(base, modifier, "add", weight=0.5)

        assert result.precision == pytest.approx(0.7)

    def test_subtract_operation(self) -> None:
        """Subtract operation: base - weight * modifier."""
        base = TraitVector(analytical_depth=0.8, creativity=0.6)
        modifier = TraitVector(analytical_depth=0.3, creativity=0.2)

        result = compose_trait_vectors(base, modifier, "subtract", weight=1.0)

        assert result.analytical_depth == pytest.approx(0.5)
        assert result.creativity == pytest.approx(0.4)

    def test_scale_operation(self) -> None:
        """Scale operation: base * weight (modifier is ignored)."""
        base = TraitVector(analytical_depth=0.8, precision=0.6)
        modifier = TraitVector(analytical_depth=1.0, precision=1.0)  # ignored

        result = compose_trait_vectors(base, modifier, "scale", weight=0.5)

        assert result.analytical_depth == pytest.approx(0.4)
        assert result.precision == pytest.approx(0.3)

    def test_clamp_upper_bound(self) -> None:
        """Values exceeding 1.0 are clamped to 1.0."""
        base = TraitVector(analytical_depth=0.9)
        modifier = TraitVector(analytical_depth=0.5)

        result = compose_trait_vectors(base, modifier, "add", weight=1.0)

        assert result.analytical_depth == 1.0

    def test_clamp_lower_bound(self) -> None:
        """Values below 0.0 are clamped to 0.0."""
        base = TraitVector(analytical_depth=0.2)
        modifier = TraitVector(analytical_depth=0.5)

        result = compose_trait_vectors(base, modifier, "subtract", weight=1.0)

        assert result.analytical_depth == 0.0

    def test_all_dimensions_clamped(self) -> None:
        """All dimensions remain in [0, 1] after composition."""
        base = TraitVector(
            analytical_depth=0.9,
            creativity=0.9,
            precision=0.1,
            empathy=0.1,
            verification_need=0.95,
            safety_sensitivity=0.05,
        )
        modifier = TraitVector(
            analytical_depth=0.5,
            creativity=0.5,
            precision=0.5,
            empathy=0.5,
            verification_need=0.5,
            safety_sensitivity=0.5,
        )

        result = compose_trait_vectors(base, modifier, "add", weight=1.0)

        for dim in result.dimensions():
            val = getattr(result, dim)
            assert 0.0 <= val <= 1.0, f"{dim}={val} is out of [0,1]"

    def test_invalid_operation_raises(self) -> None:
        """Invalid operation raises AssertionError via assert_never."""
        base = TraitVector()
        modifier = TraitVector()

        with pytest.raises(AssertionError):
            compose_trait_vectors(base, modifier, "multiply")  # type: ignore[arg-type]

    def test_default_weight_is_one(self) -> None:
        """Default weight=1.0 when not specified."""
        base = TraitVector(analytical_depth=0.3)
        modifier = TraitVector(analytical_depth=0.2)

        result = compose_trait_vectors(base, modifier, "add")

        assert result.analytical_depth == pytest.approx(0.5)


@pytest.mark.unit
class TestBlendPersonas:
    """Test normalized weighted sum blending."""

    def test_equal_weights(self) -> None:
        """Equal weights produce average of trait vectors."""
        p1 = _make_persona("p1", analytical_depth=0.8, creativity=0.2)
        p2 = _make_persona("p2", analytical_depth=0.4, creativity=0.6)

        result = blend_personas([
            {"persona": p1, "weight": 1.0},
            {"persona": p2, "weight": 1.0},
        ])

        assert result.analytical_depth == pytest.approx(0.6)
        assert result.creativity == pytest.approx(0.4)

    def test_weighted_blend(self) -> None:
        """Weighted blend favors higher-weight persona."""
        p1 = _make_persona("p1", precision=1.0)
        p2 = _make_persona("p2", precision=0.0)

        result = blend_personas([
            {"persona": p1, "weight": 3.0},
            {"persona": p2, "weight": 1.0},
        ])

        assert result.precision == pytest.approx(0.75)

    def test_single_persona(self) -> None:
        """Single persona blend returns its own trait vector."""
        p1 = _make_persona("p1", analytical_depth=0.7, creativity=0.3)

        result = blend_personas([{"persona": p1, "weight": 1.0}])

        assert result.analytical_depth == pytest.approx(0.7)
        assert result.creativity == pytest.approx(0.3)

    def test_empty_list_raises(self) -> None:
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            blend_personas([])

    def test_all_zero_weights_raises(self) -> None:
        """All-zero weights raises ValueError."""
        p1 = _make_persona("p1")

        with pytest.raises(ValueError, match="all-zero"):
            blend_personas([{"persona": p1, "weight": 0.0}])

    def test_output_clamped(self) -> None:
        """All output dimensions are clamped to [0, 1]."""
        p1 = _make_persona("p1", analytical_depth=1.0, creativity=1.0)
        p2 = _make_persona("p2", analytical_depth=1.0, creativity=1.0)

        result = blend_personas([
            {"persona": p1, "weight": 5.0},
            {"persona": p2, "weight": 5.0},
        ])

        for dim in result.dimensions():
            val = getattr(result, dim)
            assert 0.0 <= val <= 1.0


@pytest.mark.unit
class TestCreateCompositePersona:
    """Test dynamic hybrid persona creation."""

    def test_creates_composite(self) -> None:
        """Composite persona is created from top-3."""
        p1 = _make_persona("p1", "Analyst", analytical_depth=0.9, forbidden=["speculation"])
        p2 = _make_persona("p2", "Creative", creativity=0.9, forbidden=["overconfidence"])
        p3 = _make_persona("p3", "Skeptic", skepticism=0.8)

        fv = FeatureVector(analytical_depth=0.7, creativity=0.3)

        top = [
            {"persona": p1, "score": 0.8},
            {"persona": p2, "score": 0.5},
            {"persona": p3, "score": 0.3},
        ]
        composite = create_composite_persona(fv, top)

        assert composite.is_composite is True
        assert "p1" in composite.source_persona_ids
        assert "p2" in composite.source_persona_ids
        assert "p3" in composite.source_persona_ids

    def test_composite_merges_forbidden_behaviors(self) -> None:
        """Composite persona merges forbidden_behaviors from all sources."""
        p1 = _make_persona("p1", forbidden=["speculation", "hedging"])
        p2 = _make_persona("p2", forbidden=["overconfidence", "speculation"])

        fv = FeatureVector()
        composite = create_composite_persona(fv, [
            {"persona": p1, "score": 0.5},
            {"persona": p2, "score": 0.3},
        ])

        assert "speculation" in composite.forbidden_behaviors
        assert "hedging" in composite.forbidden_behaviors
        assert "overconfidence" in composite.forbidden_behaviors
        # No duplicates
        assert composite.forbidden_behaviors.count("speculation") == 1

    def test_composite_blended_trait_vector(self) -> None:
        """Composite trait vector is score-weighted blend."""
        p1 = _make_persona("p1", analytical_depth=1.0, creativity=0.0)
        p2 = _make_persona("p2", analytical_depth=0.0, creativity=1.0)

        fv = FeatureVector(analytical_depth=0.5, creativity=0.5)
        composite = create_composite_persona(fv, [
            {"persona": p1, "score": 0.6},
            {"persona": p2, "score": 0.4},
        ])

        # Weighted: (0.6*1.0 + 0.4*0.0) / 1.0 = 0.6
        assert composite.trait_vector.analytical_depth == pytest.approx(0.6)
        # Weighted: (0.6*0.0 + 0.4*1.0) / 1.0 = 0.4
        assert composite.trait_vector.creativity == pytest.approx(0.4)

    def test_composite_system_prompt_includes_source_names(self) -> None:
        """Composite system prompt references source persona names."""
        p1 = _make_persona("p1", "Analyst", system_prompt="Analyze deeply.")
        p2 = _make_persona("p2", "Creative", system_prompt="Think creatively.")

        fv = FeatureVector(analytical_depth=0.8, creativity=0.8)
        composite = create_composite_persona(fv, [
            {"persona": p1, "score": 0.6},
            {"persona": p2, "score": 0.4},
        ])

        assert "Analyst" in composite.system_prompt
        assert "Creative" in composite.system_prompt

    def test_empty_list_raises(self) -> None:
        """Empty persona list raises ValueError."""
        fv = FeatureVector()
        with pytest.raises(ValueError, match="empty"):
            create_composite_persona(fv, [])

    def test_composite_id_format(self) -> None:
        """Composite ID has expected prefix format."""
        p1 = _make_persona("alpha")
        p2 = _make_persona("beta")

        fv = FeatureVector()
        composite = create_composite_persona(fv, [
            {"persona": p1, "score": 0.5},
            {"persona": p2, "score": 0.3},
        ])

        assert composite.id.startswith("composite_")
        assert "alpha" in composite.id
