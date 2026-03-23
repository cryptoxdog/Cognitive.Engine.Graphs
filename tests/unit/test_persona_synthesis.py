"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, personas, synthesis, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for primitive-aware persona synthesis weighting and prompt building.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

import pytest

from engine.personas.synthesis import (
    _compute_primitive_alignment,
    build_synthesis_prompt,
    compute_synthesis_weights,
)
from engine.personas.types import FeatureVector, PersonaOutput, TraitVector


def _make_output(
    pid: str,
    name: str,
    content: str = "test output",
    score: float = 0.5,
    **trait_kwargs: float,
) -> PersonaOutput:
    """Helper to build a PersonaOutput with custom traits."""
    tv = TraitVector(**trait_kwargs)
    return PersonaOutput(
        persona_id=pid,
        persona_name=name,
        content=content,
        score=score,
        trait_vector=tv,
    )


@pytest.mark.unit
class TestComputePrimitiveAlignment:
    """Test primitive dimension alignment scoring."""

    def test_full_alignment(self) -> None:
        """Perfect alignment on a single primitive dimension."""
        output = _make_output("p1", "Verifier", verification_need=1.0)
        fv = FeatureVector(verification_need=1.0)

        score = _compute_primitive_alignment(output, fv)

        assert score == pytest.approx(1.0)

    def test_zero_alignment(self) -> None:
        """No alignment when features are orthogonal to primitives."""
        output = _make_output("p1", "Test", analytical_depth=1.0)
        fv = FeatureVector(analytical_depth=1.0)

        score = _compute_primitive_alignment(output, fv)

        # analytical_depth is NOT a primitive dimension
        assert score == pytest.approx(0.0)

    def test_multi_primitive_alignment(self) -> None:
        """Alignment across multiple primitive dimensions."""
        output = _make_output(
            "p1", "Multi",
            verification_need=0.8,
            comparison_need=0.6,
            generation_need=0.4,
            quantitative_need=0.2,
        )
        fv = FeatureVector(
            verification_need=0.5,
            comparison_need=0.5,
            generation_need=0.5,
            quantitative_need=0.5,
        )

        score = _compute_primitive_alignment(output, fv)

        # 0.8*0.5 + 0.6*0.5 + 0.4*0.5 + 0.2*0.5 = 0.4 + 0.3 + 0.2 + 0.1 = 1.0
        assert score == pytest.approx(1.0)

    def test_partial_alignment(self) -> None:
        """Only matching primitive dimensions contribute."""
        output = _make_output("p1", "Partial", verification_need=0.6, comparison_need=0.0)
        fv = FeatureVector(verification_need=0.5, comparison_need=0.9)

        score = _compute_primitive_alignment(output, fv)

        # 0.6*0.5 + 0.0*0.9 = 0.3
        assert score == pytest.approx(0.3)


@pytest.mark.unit
class TestComputeSynthesisWeights:
    """Test synthesis weight computation and normalization."""

    def test_empty_outputs_returns_empty(self) -> None:
        """Empty outputs returns empty weights."""
        fv = FeatureVector(verification_need=1.0)
        result = compute_synthesis_weights([], fv)

        assert result == []

    def test_single_output_gets_weight_one(self) -> None:
        """Single persona output always gets weight 1.0."""
        output = _make_output("p1", "Solo", verification_need=0.8)
        fv = FeatureVector(verification_need=1.0)

        result = compute_synthesis_weights([output], fv)

        assert len(result) == 1
        assert float(result[0]["weight"]) == pytest.approx(1.0)

    def test_weights_sum_to_one(self) -> None:
        """Weights normalize to sum to 1.0."""
        o1 = _make_output("p1", "A", verification_need=0.8)
        o2 = _make_output("p2", "B", verification_need=0.4)
        fv = FeatureVector(verification_need=1.0)

        result = compute_synthesis_weights([o1, o2], fv)

        total = sum(float(r["weight"]) for r in result)
        assert total == pytest.approx(1.0)

    def test_higher_alignment_gets_higher_weight(self) -> None:
        """Persona with higher primitive alignment gets higher weight."""
        o1 = _make_output("p1", "Strong", verification_need=0.9)
        o2 = _make_output("p2", "Weak", verification_need=0.1)
        fv = FeatureVector(verification_need=1.0)

        result = compute_synthesis_weights([o1, o2], fv)

        weights = {r["output"].persona_name: float(r["weight"]) for r in result}  # type: ignore[union-attr]
        assert weights["Strong"] > weights["Weak"]

    def test_zero_alignment_gives_equal_weights(self) -> None:
        """Zero total alignment falls back to equal weights."""
        o1 = _make_output("p1", "A", analytical_depth=0.9)
        o2 = _make_output("p2", "B", creativity=0.8)
        # Feature vector has no primitive signals
        fv = FeatureVector(analytical_depth=1.0)

        result = compute_synthesis_weights([o1, o2], fv)

        w1 = float(result[0]["weight"])
        w2 = float(result[1]["weight"])
        assert w1 == pytest.approx(0.5)
        assert w2 == pytest.approx(0.5)

    def test_minimum_weight_floor(self) -> None:
        """No persona weight drops below minimum floor (0.10)."""
        o1 = _make_output("p1", "Dominant", verification_need=0.99)
        o2 = _make_output("p2", "Tiny", verification_need=0.001)
        fv = FeatureVector(verification_need=1.0)

        result = compute_synthesis_weights([o1, o2], fv)

        for r in result:
            assert float(r["weight"]) >= 0.09  # slightly below floor after renormalization is ok


@pytest.mark.unit
class TestBuildSynthesisPrompt:
    """Test synthesis prompt construction."""

    def test_empty_outputs_returns_empty(self) -> None:
        """Empty persona outputs produce empty prompt."""
        fv = FeatureVector(verification_need=1.0)
        prompt = build_synthesis_prompt([], fv)

        assert prompt == ""

    def test_prompt_contains_persona_names(self) -> None:
        """Synthesis prompt includes persona names."""
        o1 = _make_output("p1", "Analyst", content="Analysis result", verification_need=0.8)
        o2 = _make_output("p2", "Creator", content="Creative result", generation_need=0.7)
        fv = FeatureVector(verification_need=0.6, generation_need=0.4)

        prompt = build_synthesis_prompt([o1, o2], fv)

        assert "Analyst" in prompt
        assert "Creator" in prompt

    def test_prompt_contains_content(self) -> None:
        """Synthesis prompt includes persona output content."""
        o1 = _make_output("p1", "Test", content="This is the specific output text")
        fv = FeatureVector(verification_need=0.5)

        prompt = build_synthesis_prompt([o1], fv)

        assert "This is the specific output text" in prompt

    def test_prompt_contains_relevance_percentages(self) -> None:
        """Synthesis prompt includes relevance percentage markers."""
        o1 = _make_output("p1", "Solo", content="output", verification_need=0.8)
        fv = FeatureVector(verification_need=1.0)

        prompt = build_synthesis_prompt([o1], fv)

        assert "relevance:" in prompt
        assert "%" in prompt

    def test_prompt_includes_original_query(self) -> None:
        """Original query is included in prompt when provided."""
        o1 = _make_output("p1", "Test", content="output")
        fv = FeatureVector()

        prompt = build_synthesis_prompt([o1], fv, original_query="What is recursion?")

        assert "What is recursion?" in prompt

    def test_prompt_omits_query_when_empty(self) -> None:
        """Original query section is absent when not provided."""
        o1 = _make_output("p1", "Test", content="output")
        fv = FeatureVector()

        prompt = build_synthesis_prompt([o1], fv, original_query="")

        assert "Original query:" not in prompt

    def test_prompt_includes_synthesis_instructions(self) -> None:
        """Prompt includes instructions about synthesis and persona removal."""
        o1 = _make_output("p1", "Test", content="output")
        fv = FeatureVector(verification_need=0.5)

        prompt = build_synthesis_prompt([o1], fv)

        assert "synthesiz" in prompt.lower()
        assert "persona" in prompt.lower()
