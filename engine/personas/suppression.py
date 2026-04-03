"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [personas]
tags: [suppression, safety, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Forbidden behavior suppression mechanics.

Before LLM calls, injects explicit constraint blocks for each forbidden_behavior
in persona definitions. Wraps constraints in a clearly delimited block within
the system prompt.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

from __future__ import annotations

import logging

from engine.personas.types import Persona

logger = logging.getLogger(__name__)

_CONSTRAINT_BLOCK_START = "=== BEHAVIORAL CONSTRAINTS ==="
_CONSTRAINT_BLOCK_END = "=== END CONSTRAINTS ==="

_CONSTRAINT_TEMPLATE = (
    "CONSTRAINT: You must NOT engage in {behavior}. "
    "If you notice yourself doing this, immediately stop and redirect "
    "your reasoning to your core competency."
)


def build_constraint_block(persona: Persona) -> str:
    """
    Build a delimited constraint block from a persona's forbidden_behaviors.

    Args:
        persona: Persona with forbidden_behaviors list.

    Returns:
        Formatted constraint block string. Empty string if no forbidden behaviors.
    """
    if not persona.forbidden_behaviors:
        return ""

    constraints = [_CONSTRAINT_TEMPLATE.format(behavior=b) for b in persona.forbidden_behaviors]

    block = f"\n\n{_CONSTRAINT_BLOCK_START}\n" + "\n".join(constraints) + f"\n{_CONSTRAINT_BLOCK_END}\n"

    logger.debug(
        "Built %d constraint(s) for persona '%s'",
        len(constraints),
        persona.name,
    )
    return block


def inject_suppression(persona: Persona) -> str:
    """
    Return the persona's system prompt with forbidden behavior constraints injected.

    The constraint block is appended to the end of the system prompt, clearly
    delimited so the LLM treats them as hard boundaries.

    Args:
        persona: Persona whose system prompt needs constraint injection.

    Returns:
        The augmented system prompt with constraint block appended.
    """
    base_prompt = persona.system_prompt or ""
    constraint_block = build_constraint_block(persona)

    if not constraint_block:
        return base_prompt

    return base_prompt + constraint_block
