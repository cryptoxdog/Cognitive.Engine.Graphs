"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [pareto, weight-discovery, dirichlet, adaptive]
owner: engine-team
status: active
--- /L9_META ---

engine/scoring/weight_discovery.py
Milestone 2.2 — Adaptive Weight Discovery

Async wrapper around ``discover_pareto_weights`` that integrates with the
``OutcomeHistoryStore`` and ``DomainSpec.decision_arbitration`` to provide
a production-ready weight discovery pipeline.

Usage::

    from engine.scoring.weight_discovery import adaptive_weight_discovery

    weight_vectors = await adaptive_weight_discovery(
        dimension_names=["structural", "geo_decay", "price_alignment"],
        outcome_history=outcome_store.get_recent("plasticos", days=90),
        n_samples=50,
    )
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from engine.scoring.pareto import WeightVector, discover_pareto_weights

logger = logging.getLogger(__name__)


async def adaptive_weight_discovery(
    dimension_names: list[str],
    outcome_history: list[dict[str, Any]],
    n_samples: int = 50,
    alpha_init: float = 1.0,
) -> list[WeightVector]:
    """Discover Pareto-optimal weight vectors via adaptive Dirichlet sampling.

    This is an async wrapper that delegates the CPU-bound Pareto computation
    to a thread pool so it does not block the event loop.

    Parameters
    ----------
    dimension_names:
        Scoring dimension names from the DomainSpec.
    outcome_history:
        List of outcome dicts with ``dimension_scores`` and ``was_selected``.
        Obtained from ``OutcomeHistoryStore.get_recent()``.
    n_samples:
        Number of weight vectors to sample (including baseline).
    alpha_init:
        Initial Dirichlet concentration parameter.  ``1.0`` = uniform.
        Future: adaptive alpha based on outcome variance.

    Returns
    -------
    list[WeightVector]
        Pareto-non-dominated weight vectors sorted by ``ndcg_score`` desc.
    """
    if not dimension_names:
        logger.warning("adaptive_weight_discovery called with empty dimension_names")
        return []

    # Build uniform baseline from dimension names
    k = len(dimension_names)
    current_weights = {d: 1.0 / k for d in dimension_names}

    # Delegate CPU-bound work to thread pool
    loop = asyncio.get_running_loop()
    front = await loop.run_in_executor(
        None,
        lambda: discover_pareto_weights(
            dimension_names=dimension_names,
            current_weights=current_weights,
            outcome_history=outcome_history,
            n_samples=n_samples,
            seed=42,
        ),
    )

    logger.info(
        "Adaptive weight discovery: %d Pareto-optimal vectors from %d samples "
        "(pruned %.1f%%)",
        len(front),
        n_samples,
        round((1.0 - len(front) / max(n_samples, 1)) * 100, 1),
    )

    return front
