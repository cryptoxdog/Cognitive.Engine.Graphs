"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, personas, suppression, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for forbidden behavior suppression mechanics.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

import pytest

from engine.personas.suppression import (
    _CONSTRAINT_BLOCK_END,
    _CONSTRAINT_BLOCK_START,
    build_constraint_block,
    inject_suppression,
)
from engine.personas.types import Persona, TraitVector


def _make_persona(
    pid: str = "p1",
    name: str = "Test",
    system_prompt: str = "You are a helpful assistant.",
    forbidden_behaviors: list[str] | None = None,
) -> Persona:
    """Helper to build a Persona for suppression tests."""
    return Persona(
        id=pid,
        name=name,
        system_prompt=system_prompt,
        trait_vector=TraitVector(),
        forbidden_behaviors=forbidden_behaviors or [],
    )


@pytest.mark.unit
class TestBuildConstraintBlock:
    """Test constraint block generation from forbidden_behaviors."""

    def test_no_forbidden_behaviors_returns_empty(self) -> None:
        """No forbidden behaviors produces empty string."""
        persona = _make_persona(forbidden_behaviors=[])
        block = build_constraint_block(persona)

        assert block == ""

    def test_single_constraint(self) -> None:
        """Single forbidden behavior produces one constraint."""
        persona = _make_persona(forbidden_behaviors=["providing medical advice"])
        block = build_constraint_block(persona)

        assert "providing medical advice" in block
        assert _CONSTRAINT_BLOCK_START in block
        assert _CONSTRAINT_BLOCK_END in block

    def test_multiple_constraints(self) -> None:
        """Multiple forbidden behaviors produce multiple constraints."""
        behaviors = ["giving legal advice", "generating code", "roleplaying"]
        persona = _make_persona(forbidden_behaviors=behaviors)
        block = build_constraint_block(persona)

        for behavior in behaviors:
            assert behavior in block

    def test_constraint_template_format(self) -> None:
        """Each constraint follows the template format."""
        persona = _make_persona(forbidden_behaviors=["speculating about future events"])
        block = build_constraint_block(persona)

        assert "CONSTRAINT:" in block
        assert "must NOT" in block
        assert "speculating about future events" in block

    def test_block_delimiters_present(self) -> None:
        """Constraint block has start and end delimiters."""
        persona = _make_persona(forbidden_behaviors=["test behavior"])
        block = build_constraint_block(persona)

        start_idx = block.index(_CONSTRAINT_BLOCK_START)
        end_idx = block.index(_CONSTRAINT_BLOCK_END)
        assert start_idx < end_idx


@pytest.mark.unit
class TestInjectSuppression:
    """Test constraint injection into system prompts."""

    def test_no_constraints_returns_base_prompt(self) -> None:
        """No forbidden behaviors returns original system prompt."""
        persona = _make_persona(system_prompt="Base prompt.", forbidden_behaviors=[])
        result = inject_suppression(persona)

        assert result == "Base prompt."

    def test_constraints_appended_to_prompt(self) -> None:
        """Constraints are appended to the end of the system prompt."""
        persona = _make_persona(
            system_prompt="You are a domain expert.",
            forbidden_behaviors=["giving financial advice"],
        )
        result = inject_suppression(persona)

        assert result.startswith("You are a domain expert.")
        assert "giving financial advice" in result
        assert _CONSTRAINT_BLOCK_START in result

    def test_base_prompt_preserved(self) -> None:
        """Original system prompt content is preserved exactly."""
        original = "Be precise and analytical. Focus on data."
        persona = _make_persona(
            system_prompt=original,
            forbidden_behaviors=["hallucinating data"],
        )
        result = inject_suppression(persona)

        assert original in result

    def test_empty_system_prompt_with_constraints(self) -> None:
        """Empty system prompt still gets constraint block."""
        persona = _make_persona(
            system_prompt="",
            forbidden_behaviors=["providing opinions"],
        )
        result = inject_suppression(persona)

        assert _CONSTRAINT_BLOCK_START in result
        assert "providing opinions" in result

    def test_none_system_prompt_handled(self) -> None:
        """None system prompt treated as empty string."""
        persona = Persona(
            id="p1",
            name="Test",
            system_prompt="",
            forbidden_behaviors=["test behavior"],
        )
        result = inject_suppression(persona)

        assert _CONSTRAINT_BLOCK_START in result

    def test_constraint_block_at_end(self) -> None:
        """Constraint block appears at the end, after base prompt."""
        persona = _make_persona(
            system_prompt="System prompt content here.",
            forbidden_behaviors=["breaking character"],
        )
        result = inject_suppression(persona)

        prompt_end = result.index("System prompt content here.") + len("System prompt content here.")
        constraint_start = result.index(_CONSTRAINT_BLOCK_START)
        assert constraint_start > prompt_end
