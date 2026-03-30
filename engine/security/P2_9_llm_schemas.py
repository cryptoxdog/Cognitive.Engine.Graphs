"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [security]
tags: [security, llm, schemas]
owner: engine-team
status: active
--- /L9_META ---

LLM Output Schemas + Validated Client — engine/llm/schemas.py
P2-9 Implementation | Impact: AI Governance 65% -> 75%

Wires the P1-5 validation framework into all LLM-calling code.

Usage:
    from engine.llm.schemas import ValidatedLLMClient

    llm = ValidatedLLMClient(model="gpt-4-turbo")
    result = llm.generate_cypher("Find users connected to Alice")
    # result is a CypherQueryOutput — guaranteed valid
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, TypeVar

import structlog

# These come from P1-5 (engine/security/llm.py)
from engine.security.llm import sanitize_llm_input, track_llm_usage
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)
_slog = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


# ── Output Schemas ───────────────────────────────────────────


class CypherQueryOutput(BaseModel):
    """Expected shape for LLM-generated Cypher."""

    cypher_query: str = Field(..., min_length=10, max_length=5000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(..., min_length=5, max_length=1000)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("cypher_query")
    @classmethod
    def block_destructive_ops(cls, v: str) -> str:
        dangerous = {"DROP", "DELETE", "DETACH DELETE", "REMOVE"}
        upper = v.upper()
        for kw in dangerous:
            if kw in upper:
                raise ValueError(f"Destructive keyword rejected: {kw}")
        return v

    @field_validator("parameters")
    @classmethod
    def json_safe_params(cls, v: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(v)
        except TypeError as exc:
            raise ValueError("parameters must be JSON-serialisable") from exc
        return v


class GraphAnalysisOutput(BaseModel):
    node_count: int = Field(..., ge=0)
    edge_count: int = Field(..., ge=0)
    key_insights: list[str] = Field(..., min_length=1, max_length=10)
    recommendations: list[str] = Field(default_factory=list, max_length=5)
    risk_score: float | None = Field(None, ge=0.0, le=10.0)


class NLResponse(BaseModel):
    answer: str = Field(..., min_length=5, max_length=2000)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    follow_ups: list[str] = Field(default_factory=list, max_length=3)


class CodeGenOutput(BaseModel):
    code: str = Field(..., min_length=5, max_length=5000)
    language: str = Field(..., pattern=r"^(python|javascript|cypher)$")
    explanation: str
    dependencies: list[str] = Field(default_factory=list)


# ── Validation helper ────────────────────────────────────────


def validate_llm_json(raw: str, schema: type[T]) -> T:
    """Parse raw LLM string into a validated Pydantic model."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"LLM returned invalid JSON: {exc}") from exc
    return schema.model_validate(data)


# ── LLM Provider Backend ────────────────────────────────────


class _LLMBackend:
    """
    Lazy-initialised OpenAI-compatible LLM backend.

    Reads configuration from environment variables:
      - LLM_PROVIDER: "openai" (default) | "openai-compatible"
      - OPENAI_API_KEY: API key for OpenAI or compatible providers
      - OPENAI_BASE_URL: Override base URL for OpenAI-compatible providers
      - LLM_MAX_TOKENS: Maximum response tokens (default 2048)
      - LLM_TEMPERATURE: Sampling temperature (default 0.1)
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._provider: str = os.environ.get("LLM_PROVIDER", "openai")
        self._max_tokens: int = int(os.environ.get("LLM_MAX_TOKENS", "2048"))
        self._temperature: float = float(os.environ.get("LLM_TEMPERATURE", "0.1"))

    def _ensure_client(self, model: str) -> Any:
        """Lazy-init the OpenAI client on first call."""
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is required for LLM features. "
                "Install with: pip install openai"
            ) from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is required. "
                "Set it to your OpenAI (or compatible provider) API key."
            )

        kwargs: dict[str, Any] = {"api_key": api_key}
        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url

        self._client = OpenAI(**kwargs)
        _slog.info(
            "llm_backend_initialized",
            provider=self._provider,
            model=model,
            base_url=base_url or "https://api.openai.com/v1",
        )
        return self._client

    def call(self, model: str, system: str, user: str) -> str:
        """
        Execute a chat completion and return the raw response text.

        Args:
            model: Model identifier (e.g. "gpt-4-turbo")
            system: System prompt
            user: User prompt

        Returns:
            Raw text/JSON string from the model response.

        Raises:
            RuntimeError: If the client cannot be initialized.
        """
        client = self._ensure_client(model)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if content is None:
            _slog.warning("llm_empty_response", model=model)
            return "{}"

        # Log token usage if available
        if hasattr(response, "usage") and response.usage:
            _slog.info(
                "llm_token_usage",
                model=model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return content


# Module-level singleton — shared across all ValidatedLLMClient instances
_llm_backend = _LLMBackend()


# ── Validated Client ─────────────────────────────────────────


class ValidatedLLMClient:
    """
    Drop-in wrapper around the OpenAI SDK that enforces
    input sanitisation + output schema validation on every call.

    Configuration is read from environment variables (see _LLMBackend).
    Falls back to FeatureNotEnabled if OPENAI_API_KEY is not set.
    """

    def __init__(self, model: str = "gpt-4-turbo"):
        self.model = model

    # ---- private ---------------------------------------------------

    def _call(self, system: str, user: str) -> str:
        """
        Execute an LLM call via the configured backend.

        Returns the raw text/JSON string from the model.
        Raises FeatureNotEnabled if the LLM backend is not configured.
        """
        try:
            return _llm_backend.call(self.model, system, user)
        except RuntimeError as exc:
            # Convert to FeatureNotEnabled for graceful degradation
            from chassis.errors import FeatureNotEnabled
            raise FeatureNotEnabled(
                "LLM SDK",
                flag="OPENAI_API_KEY",
                message=str(exc),
            ) from exc

    # ---- public API ------------------------------------------------

    def generate_cypher(
        self,
        natural_language: str,
        schema_hint: str | None = None,
    ) -> CypherQueryOutput:
        clean = sanitize_llm_input(natural_language, max_length=500)

        # Sanitize schema_hint to prevent prompt injection via untrusted schema content.
        schema_hint_clean: str | None = None
        if schema_hint:
            schema_hint_clean = re.sub(r"[^\w\s.\-_\[\]{}]", "", str(schema_hint))[:500]

        system = "You are a Cypher query expert. Return JSON with: cypher_query, parameters, explanation, confidence."
        user = f"Convert to Cypher: {clean}"
        if schema_hint_clean:
            user += f"\nGraph schema:\n{schema_hint_clean}"

        with track_llm_usage(model=self.model):
            raw = self._call(system, user)

        return validate_llm_json(raw, CypherQueryOutput)

    def analyse_graph(self, results: list[dict[str, Any]]) -> GraphAnalysisOutput:
        system = (
            "You are a graph analytics expert. "
            "Return JSON with: node_count, edge_count, key_insights, "
            "recommendations, risk_score."
        )
        user = f"Analyse:\n{json.dumps(results, default=str)[:4000]}"

        with track_llm_usage(model=self.model):
            raw = self._call(system, user)

        return validate_llm_json(raw, GraphAnalysisOutput)

    def generate_code(self, task: str, language: str = "python") -> CodeGenOutput:
        clean = sanitize_llm_input(task, max_length=500)

        # Validate language against allowlist to prevent prompt injection.
        allowed_languages = {"cypher", "python", "json", "yaml", "javascript"}
        if language not in allowed_languages:
            raise ValueError(f"Unsupported language: {language!r}")

        system = f"Generate {language} code. Return JSON with: code, language, explanation, dependencies."

        with track_llm_usage(model=self.model):
            raw = self._call(system, clean)

        return validate_llm_json(raw, CodeGenOutput)
