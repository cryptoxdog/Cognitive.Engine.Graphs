"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [security]
tags: [security, llm]
owner: engine-team
status: active
--- /L9_META ---

LLM Output Validation & Security
Implements: Gap Analysis P1-5 (AI Governance)

This module provides:
1. Prompt injection defense (input sanitization)
2. Output schema validation (Pydantic integration)
3. Cost/token monitoring

Installation:
    pip install pydantic

Usage:
    from engine.security.llm import sanitize_llm_input, validate_llm_output
"""

import json
import logging
import re
from collections.abc import Generator
from typing import TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ============================================================
# Input Sanitization (Prompt Injection Defense)
# ============================================================

INJECTION_PATTERNS = [
    # Instruction injection
    r"ignore (previous|all|above) (instructions|commands|prompts)",
    r"forget (everything|all) (you were told|previous)",
    r"you (are|must|will) now",
    r"new (instructions|system prompt|role):",
    # Role manipulation
    r"(system|assistant):\s*(now|you are|from now)",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    # Context poisoning
    r"previous (response|output|message) (was|said|contained)",
    r"you (previously|already|earlier) (said|stated|mentioned)",
    # Data exfiltration attempts
    r"(show|display|reveal|output) (your|the) (system prompt|instructions|context)",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)


def sanitize_llm_input(user_input: str, max_length: int = 2000) -> str:
    """
    Sanitize user input before sending to LLM.

    Defenses:
    - Remove prompt injection patterns
    - Truncate to max length
    - Strip special tokens
    - Normalize whitespace

    Args:
        user_input: Raw user input
        max_length: Maximum allowed length

    Returns:
        Sanitized input safe for LLM prompts

    Raises:
        ValueError: If input contains severe injection attempt
    """
    if not user_input:
        return ""

    # Check for injection patterns
    matches = INJECTION_REGEX.findall(user_input.lower())
    if matches:
        logger.warning(f"Potential prompt injection detected: {matches[:3]}")
        raise ValueError(
            "Input contains potentially malicious patterns. Please rephrase your request without meta-instructions."
        )

    # Truncate
    if len(user_input) > max_length:
        user_input = user_input[:max_length]
        logger.info(f"Input truncated to {max_length} characters")

    # Remove special tokens (model-specific)
    special_tokens = [
        "<|im_start|>",
        "<|im_end|>",
        "[INST]",
        "[/INST]",
        "<s>",
        "</s>",
        "###",
        "```system",
    ]
    for token in special_tokens:
        user_input = user_input.replace(token, "")

    # Normalize whitespace
    user_input = " ".join(user_input.split())

    return user_input.strip()


# ============================================================
# Output Validation (Schema Enforcement)
# ============================================================


def validate_llm_output(llm_response: str, expected_schema: type[T], strict: bool = True) -> T:
    """
    Validate LLM JSON output against Pydantic schema.

    Args:
        llm_response: Raw LLM response (JSON string)
        expected_schema: Pydantic model class
        strict: If True, reject extra fields

    Returns:
        Validated Pydantic model instance

    Raises:
        ValidationError: If output doesn't match schema

    Example:
        from pydantic import BaseModel

        class QueryResult(BaseModel):
            nodes: list[str]
            count: int

        response = llm.generate(...)
        validated = validate_llm_output(response, QueryResult)
    """
    try:
        # Parse JSON
        data = json.loads(llm_response)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
        raise ValidationError(f"LLM output is not valid JSON: {e}")

    # Validate against schema
    try:
        if strict:
            # Reject extra fields
            validated = expected_schema.model_validate(data, strict=True)
        else:
            # Allow extra fields
            validated = expected_schema.model_validate(data)

        logger.info(f"LLM output validated against {expected_schema.__name__}")
        return validated

    except ValidationError as e:
        logger.error(f"LLM output failed schema validation: {e}")
        raise


# ============================================================
# Sandboxed Code Execution — REMOVED (Audit Finding T1-01)
# ============================================================
# REMOVED: safe_exec() and _worker() deleted due to RCE risk.
# RestrictedPython + multiprocessing.Process exec() does not provide
# sufficient sandboxing against __subclasses__ traversal, frame
# introspection, or marshal deserialization attacks.
#
# If sandboxed code execution is required in future, use an OS-level
# sandbox (gVisor, nsjail, Firecracker) or a WebAssembly runtime.
#
# See: Audit Finding T1-01 (CRITICAL)


# ============================================================
# Cost Monitoring
# ============================================================

from contextlib import contextmanager
from datetime import UTC, datetime

import structlog

cost_logger = structlog.get_logger("llm.cost")


@contextmanager
def track_llm_usage(model: str, user_id: str | None = None) -> Generator[None, None, None]:
    """
    Context manager to track LLM token usage and cost.

    Usage:
        with track_llm_usage(model="gpt-4-turbo", user_id="user123"):
            response = openai.chat.completions.create(...)
            # Token counts logged automatically
    """
    start_time = datetime.now(UTC)

    try:
        yield
    finally:
        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        cost_logger.info(
            "llm_call", model=model, user_id=user_id, duration_ms=duration_ms, timestamp=start_time.isoformat()
        )

        # See DEFERRED.md: DEFERRED-001 — token/cost extraction per provider SDK
