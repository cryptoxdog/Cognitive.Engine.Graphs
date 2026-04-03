"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [pareto, multi-objective, integration]
owner: engine-team
status: active
--- /L9_META ---

engine/scoring/pareto_integrator.py
Milestone 2.1 — Pareto Core Integration

Convenience wrapper around ``engine.scoring.pareto`` that bridges the
DomainSpec-level ``DecisionArbitrationSpec`` with the low-level Pareto
primitives.  Provides:

1. ``apply_pareto_filter()`` — Pareto-dominance filter for match candidates
2. ``build_pareto_candidates()`` — converts raw Neo4j result dicts to
   ``ParetoCandidate`` instances using dimension names from the spec
3. ``apply_constraint_penalties()`` — enforces hard/soft constraints from
   the ``DecisionArbitrationSpec``
"""

from __future__ import annotations

import logging
from typing import Any

from engine.scoring.pareto import ParetoCandidate, ParetoFront, compute_pareto_front

logger = logging.getLogger(__name__)


# ── Candidate construction ───────────────────────────────────────────────────


def build_pareto_candidates(
    results: list[dict[str, Any]],
    dimension_names: list[str],
    *,
    candidate_id_key: str = "entity_id",
) -> list[ParetoCandidate]:
    """Convert raw Neo4j result dicts into ``ParetoCandidate`` instances.

    Parameters
    ----------
    results:
        List of result dicts from graph query.  Each dict should contain
        a ``"candidate"`` sub-dict with ``entity_id``, plus top-level keys
        matching ``dimension_names`` (e.g. ``structural_score``).
    dimension_names:
        Scoring dimension names from the DomainSpec (e.g. ``["structural",
        "geo_decay", "price_alignment"]``).
    candidate_id_key:
        Key within the ``"candidate"`` sub-dict to use as the candidate ID.

    Returns
    -------
    list[ParetoCandidate]
    """
    candidates: list[ParetoCandidate] = []
    for idx, record in enumerate(results):
        cand_dict = record.get("candidate", {})
        cand_id = str(cand_dict.get(candidate_id_key, idx)) if isinstance(cand_dict, dict) else str(idx)

        dim_scores: dict[str, float] = {}
        for dim in dimension_names:
            # Try both "dim" and "dim_score" keys
            val = record.get(dim) or record.get(f"{dim}_score")
            if val is not None:
                try:
                    dim_scores[dim] = float(val)
                except (TypeError, ValueError):
                    dim_scores[dim] = 0.0
            else:
                # Check inside dimension_scores sub-dict
                ds = record.get("dimension_scores", {})
                if isinstance(ds, dict) and dim in ds:
                    dim_scores[dim] = float(ds[dim])
                else:
                    dim_scores[dim] = 0.0

        candidates.append(ParetoCandidate(candidate_id=cand_id, dimension_scores=dim_scores))

    return candidates


# ── Constraint enforcement ───────────────────────────────────────────────────


def apply_constraint_penalties(
    candidates: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply hard/soft constraint penalties from DecisionArbitrationSpec.

    Parameters
    ----------
    candidates:
        Raw result dicts with dimension scores.
    constraints:
        List of constraint dicts from ``DecisionArbitrationSpec.constraints``.
        Each has: ``dimension``, ``threshold``, ``hard`` (bool), and optional
        ``penalty`` (float, default 0.5).

    Returns
    -------
    Filtered list — hard constraint violations removed, soft penalties applied.
    """
    filtered: list[dict[str, Any]] = []

    for candidate in candidates:
        rejected = False
        ds = candidate.get("dimension_scores", {})
        if not isinstance(ds, dict):
            ds = {}

        for constraint in constraints:
            dim = constraint.get("dimension", "")
            threshold = float(constraint.get("threshold", 0.0))
            is_hard = constraint.get("hard", False)
            penalty = float(constraint.get("penalty", 0.5))

            score = ds.get(dim)
            if score is None:
                # Also check top-level keys
                score = candidate.get(dim) or candidate.get(f"{dim}_score")

            if score is None:
                continue

            score = float(score)

            if score < threshold:
                if is_hard:
                    rejected = True
                    break
                # Apply soft penalty to the overall score
                if "score" in candidate:
                    candidate["score"] = candidate["score"] * penalty

        if not rejected:
            filtered.append(candidate)

    logger.info(
        "Constraint enforcement: %d/%d candidates passed (%d rejected)",
        len(filtered),
        len(candidates),
        len(candidates) - len(filtered),
    )

    return filtered


# ── Pareto filter ────────────────────────────────────────────────────────────


def apply_pareto_filter(
    candidates: list[dict[str, Any]],
    dimension_names: list[str],
    *,
    candidate_id_key: str = "entity_id",
) -> dict[str, Any]:
    """Apply Pareto dominance filtering to a candidate set.

    Parameters
    ----------
    candidates:
        Raw result dicts from graph query.
    dimension_names:
        Scoring dimension names from the DomainSpec.
    candidate_id_key:
        Key within the ``"candidate"`` sub-dict for the ID.

    Returns
    -------
    dict with keys:
        ``nondominated`` — list of non-dominated candidate IDs
        ``dominated`` — list of dominated candidate IDs
        ``frontsize`` — number of non-dominated candidates
        ``pruned_pct`` — percentage of candidates pruned
    """
    pareto_candidates = build_pareto_candidates(candidates, dimension_names, candidate_id_key=candidate_id_key)

    if not pareto_candidates:
        return {
            "nondominated": [],
            "dominated": [],
            "frontsize": 0,
            "pruned_pct": 0.0,
        }

    front: ParetoFront = compute_pareto_front(pareto_candidates)

    nondominated_ids = [c.candidate_id for c in front.non_dominated]
    dominated_ids = [c.candidate_id for c in front.dominated]
    total = len(pareto_candidates)
    pruned_pct = round((1.0 - front.front_size / total) * 100, 1) if total else 0.0

    logger.info(
        "Pareto filter: %d/%d on front (%.1f%% pruned)",
        front.front_size,
        total,
        pruned_pct,
    )

    return {
        "nondominated": nondominated_ids,
        "dominated": dominated_ids,
        "frontsize": front.front_size,
        "pruned_pct": pruned_pct,
    }
