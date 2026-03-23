"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [hoprag, config]
tags: [hoprag, configuration, settings]
owner: engine-team
status: active
--- /L9_META ---

HopRAG configuration dataclass.

Defines all tunable parameters for the HopRAG subsystem, including:
- Traversal depth (n_hop)
- Retrieval width (top_k)
- Edge density control
- Reasoning mode and model selection
- Helpfulness alpha balance
- Cost control limits

Loaded from domain-spec YAML ``hoprag:`` section::

    hoprag:
      enabled: true
      n_hop: 4
      top_k: 12
      edge_density_factor: 1.0
      traversal_model: "none"
      reasoning_mode: "similarity"
      alpha: 0.5

All parameters have safe defaults matching the HopRAG paper's
experimental findings (n_hop=4, top_k=12, alpha=0.5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class TraversalModel(StrEnum):
    """Supported traversal model options."""

    NONE = "none"
    GPT_4O_MINI = "gpt-4o-mini"
    QWEN_1_5B = "qwen-1.5b"
    CUSTOM = "custom"


class ReasoningMode(StrEnum):
    """Reasoning mode for multi-hop traversal."""

    NONE = "none"
    SIMILARITY = "similarity"
    LLM = "llm"


@dataclass
class HopRAGConfig:
    """Configuration for the HopRAG subsystem.

    Attributes:
        enabled: Master switch for HopRAG features. Default False.
        n_hop: Maximum BFS depth. Default 4 (paper optimal).
        top_k: Number of initial retrieval results. Default 12.
        edge_density_factor: Multiplier on n*log(n) edge limit. Default 1.0.
        max_edges_per_vertex: Hard cap on outgoing edges. Default 10.
        traversal_model: LLM model for reasoning. Default "none".
        reasoning_mode: Edge selection strategy. Default "similarity".
        alpha: Helpfulness balance (SIM/IMP). Default 0.5.
        min_queue_size: BFS stops when queue drops below this. Default 0.
        max_llm_calls_per_query: Hard cap on LLM calls. Default 50.
        llm_timeout_ms: Per-call LLM timeout in milliseconds. Default 2000.
        min_similarity_threshold: Minimum hybrid similarity for edges. Default 0.0.
        n_incoming_questions: In-coming questions per passage. Default 2.
        m_outgoing_questions: Out-coming questions per passage. Default 4.
        index_batch_size: Passages processed per indexing batch. Default 100.
        custom_model_endpoint: URL for custom traversal model. Default "".
    """

    enabled: bool = False
    n_hop: int = 4
    top_k: int = 12
    edge_density_factor: float = 1.0  # nosemgrep: float-requires-try-except
    max_edges_per_vertex: int = 10
    traversal_model: str = TraversalModel.NONE
    reasoning_mode: str = ReasoningMode.SIMILARITY
    alpha: float = 0.5  # nosemgrep: float-requires-try-except
    min_queue_size: int = 0
    max_llm_calls_per_query: int = 50
    llm_timeout_ms: int = 2000
    min_similarity_threshold: float = 0.0  # nosemgrep: float-requires-try-except
    n_incoming_questions: int = 2
    m_outgoing_questions: int = 4
    index_batch_size: int = 100
    custom_model_endpoint: str = ""

    def __post_init__(self) -> None:
        """Validate configuration bounds."""
        if self.n_hop < 1:
            msg = f"n_hop must be >= 1, got {self.n_hop}"
            raise ValueError(msg)
        if self.top_k < 1:
            msg = f"top_k must be >= 1, got {self.top_k}"
            raise ValueError(msg)
        if not 0.0 <= self.alpha <= 1.0:
            msg = f"alpha must be in [0.0, 1.0], got {self.alpha}"
            raise ValueError(msg)
        if self.edge_density_factor <= 0:
            msg = f"edge_density_factor must be > 0, got {self.edge_density_factor}"
            raise ValueError(msg)
        if self.max_llm_calls_per_query < 0:
            msg = f"max_llm_calls_per_query must be >= 0, got {self.max_llm_calls_per_query}"
            raise ValueError(msg)
        if self.n_incoming_questions < 1:
            msg = f"n_incoming_questions must be >= 1, got {self.n_incoming_questions}"
            raise ValueError(msg)
        if self.m_outgoing_questions < 1:
            msg = f"m_outgoing_questions must be >= 1, got {self.m_outgoing_questions}"
            raise ValueError(msg)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HopRAGConfig:
        """Construct from dictionary (e.g., parsed from domain-spec YAML).

        Args:
            data: Configuration dictionary.

        Returns:
            HopRAGConfig instance.

        Raises:
            ValueError: If any field is invalid.
        """
        # Only pass known fields to avoid TypeError on extra keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_domain_spec(cls, domain_spec: Any) -> HopRAGConfig:
        """Extract HopRAGConfig from a DomainSpec object.

        Looks for a ``hoprag`` attribute or section in the domain spec.
        Returns default config if not found.

        Args:
            domain_spec: DomainSpec object (Pydantic model).

        Returns:
            HopRAGConfig instance.
        """
        hoprag_data = getattr(domain_spec, "hoprag", None)
        if hoprag_data is None:
            logger.debug("No 'hoprag' section in domain spec, using defaults")
            return cls()

        if isinstance(hoprag_data, dict):
            return cls.from_dict(hoprag_data)

        # Assume it's a Pydantic model with model_dump()
        if hasattr(hoprag_data, "model_dump"):
            return cls.from_dict(hoprag_data.model_dump())

        logger.warning("Unrecognized hoprag config type: %s, using defaults", type(hoprag_data))
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of this config.
        """
        from dataclasses import asdict

        return asdict(self)

    def effective_reasoning_mode(self) -> ReasoningMode:
        """Resolve effective reasoning mode considering model availability.

        If reasoning_mode is 'llm' but traversal_model is 'none',
        falls back to 'similarity'.

        Returns:
            The effective ReasoningMode.
        """
        if self.reasoning_mode == ReasoningMode.LLM and self.traversal_model == TraversalModel.NONE:
            logger.warning(
                "reasoning_mode='llm' but traversal_model='none', "
                "falling back to 'similarity'"
            )
            return ReasoningMode.SIMILARITY
        return ReasoningMode(self.reasoning_mode)
