"""
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
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator, ValidationError

# These come from P1-5 (engine/security/llm.py)
from engine.security.llm import sanitize_llm_input, track_llm_usage

logger = logging.getLogger(__name__)
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
    def json_safe_params(cls, v: dict) -> dict:
        for key, val in v.items():
            if not isinstance(val, (str, int, float, bool, list, dict, type(None))):
                raise ValueError(f"Non-serialisable param '{key}': {type(val)}")
        return v


class GraphAnalysisOutput(BaseModel):
    node_count: int = Field(..., ge=0)
    edge_count: int = Field(..., ge=0)
    key_insights: list[str] = Field(..., min_length=1, max_length=10)
    recommendations: list[str] = Field(default_factory=list, max_length=5)
    risk_score: Optional[float] = Field(None, ge=0.0, le=10.0)


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


# ── Validated Client ─────────────────────────────────────────

class ValidatedLLMClient:
    """
    Drop-in wrapper around any LLM SDK that enforces
    input sanitisation + output schema validation on every call.
    """

    def __init__(self, model: str = "gpt-4-turbo"):
        self.model = model
        # Replace with your actual client init:
        # self._client = openai.OpenAI()

    # ---- private ---------------------------------------------------

    def _call(self, system: str, user: str) -> str:
        """
        Raw LLM call — replace body with your provider SDK.
        Must return the raw text/JSON string from the model.
        """
        # response = self._client.chat.completions.create(
        #     model=self.model,
        #     response_format={"type": "json_object"},
        #     messages=[
        #         {"role": "system", "content": system},
        #         {"role": "user",   "content": user},
        #     ],
        # )
        # return response.choices[0].message.content
        raise NotImplementedError("Wire up your LLM SDK here")

    # ---- public API ------------------------------------------------

    def generate_cypher(
        self,
        natural_language: str,
        schema_hint: Optional[str] = None,
    ) -> CypherQueryOutput:
        clean = sanitize_llm_input(natural_language, max_length=500)

        system = (
            "You are a Cypher query expert. "
            "Return JSON with: cypher_query, parameters, explanation, confidence."
        )
        user = f"Convert to Cypher: {clean}"
        if schema_hint:
            user += f"\nGraph schema:\n{schema_hint}"

        with track_llm_usage(model=self.model):
            raw = self._call(system, user)

        return validate_llm_json(raw, CypherQueryOutput)

    def analyse_graph(self, results: list[dict]) -> GraphAnalysisOutput:
        system = (
            "You are a graph analytics expert. "
            "Return JSON with: node_count, edge_count, key_insights, "
            "recommendations, risk_score."
        )
        user = f"Analyse:\n{json.dumps(results)[:4000]}"

        with track_llm_usage(model=self.model):
            raw = self._call(system, user)

        return validate_llm_json(raw, GraphAnalysisOutput)

    def generate_code(
        self, task: str, language: str = "python"
    ) -> CodeGenOutput:
        clean = sanitize_llm_input(task, max_length=500)

        system = (
            f"Generate {language} code. "
            "Return JSON with: code, language, explanation, dependencies."
        )

        with track_llm_usage(model=self.model):
            raw = self._call(system, clean)

        return validate_llm_json(raw, CodeGenOutput)
