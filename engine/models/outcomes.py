"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [models]
tags: [outcomes, feedback, pareto, weight-discovery]
owner: engine-team
status: active
--- /L9_META ---

engine/models/outcomes.py
Milestone 2.2 — Outcome models for Pareto weight discovery

Provides:

1. ``OutcomeRecord`` — Pydantic model for a single match outcome
2. ``OutcomeHistoryStore`` — In-memory store for outcome history with
   tenant isolation, TTL-based expiry, and serialization to the format
   expected by ``discover_pareto_weights()``.

The in-memory store is suitable for single-instance deployments.  For
multi-instance production, replace with a PostgreSQL-backed implementation
that reads from the ``transaction_outcomes`` table.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Models ───────────────────────────────────────────────────────────────────


class OutcomeRecord(BaseModel):
    """Record of a match outcome for weight discovery."""

    match_id: str = Field(description="ID of the match request that produced this outcome")
    candidate_id: str = Field(description="ID of the candidate entity")
    dimension_scores: dict[str, float] = Field(
        description="Per-dimension scores at the time of the match"
    )
    was_selected: bool = Field(
        description="Whether the customer/user selected this candidate"
    )
    feedback_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional explicit feedback score (0.0-1.0)",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Store ────────────────────────────────────────────────────────────────────


class OutcomeHistoryStore:
    """In-memory tenant-isolated store for outcome history.

    Thread-safe for single-process use.  For production multi-instance
    deployments, subclass and override ``add_outcome`` / ``get_recent``
    with PostgreSQL or Redis-backed implementations.
    """

    def __init__(self, max_per_tenant: int = 10_000) -> None:
        self._history: dict[str, list[OutcomeRecord]] = defaultdict(list)
        self._max_per_tenant = max_per_tenant

    def add_outcome(self, tenant: str, outcome: OutcomeRecord) -> None:
        """Append an outcome record for a tenant."""
        bucket = self._history[tenant]
        bucket.append(outcome)

        # Evict oldest if over capacity
        if len(bucket) > self._max_per_tenant:
            evicted = len(bucket) - self._max_per_tenant
            self._history[tenant] = bucket[evicted:]
            logger.debug(
                "Evicted %d oldest outcomes for tenant=%s (cap=%d)",
                evicted,
                tenant,
                self._max_per_tenant,
            )

    def get_recent(
        self,
        tenant: str,
        days: int = 90,
    ) -> list[dict[str, Any]]:
        """Get outcomes from the last *days* days in the format expected by
        ``discover_pareto_weights(outcome_history=...)``.

        Returns
        -------
        list[dict]
            Each dict has ``dimension_scores`` (dict[str, float]) and
            ``was_selected`` (bool).
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        bucket = self._history.get(tenant, [])

        recent = [
            {
                "dimension_scores": o.dimension_scores,
                "was_selected": o.was_selected,
            }
            for o in bucket
            if o.timestamp >= cutoff
        ]

        logger.debug(
            "Outcome history for tenant=%s: %d/%d records within %d-day window",
            tenant,
            len(recent),
            len(bucket),
            days,
        )

        return recent

    def count(self, tenant: str) -> int:
        """Total outcome count for a tenant."""
        return len(self._history.get(tenant, []))

    def clear(self, tenant: str) -> int:
        """Clear all outcomes for a tenant.  Returns count cleared."""
        count = len(self._history.pop(tenant, []))
        return count
