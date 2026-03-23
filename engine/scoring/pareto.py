"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [pareto, multi-objective, scoring]
owner: engine-team
status: active
--- /L9_META ---

Pareto-optimal scoring utilities for multi-objective candidate filtering
and Dirichlet-sampled weight discovery.

Planned extensions (post-MVP):
- Tchebycheff scalarisation (replaces simple additive weighting)
- Adaptive Dirichlet concentration (replaces uniform alpha=1)
- Graph-space diversity metric
- Two-level hierarchy for multi-objective optimization
- Entropy-as-uncertainty signal (Shannon entropy computed but not used as uncertainty)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class ParetoCandidate:
    """A single candidate with per-dimension scores."""

    candidate_id: str
    dimension_scores: dict[str, float]
    weighted_score: float = 0.0
    is_dominated: bool = False


@dataclass
class ParetoFront:
    """Result of a Pareto dominance computation."""

    non_dominated: list[ParetoCandidate]
    dominated: list[ParetoCandidate]
    dimension_names: list[str]
    front_size: int = 0

    def __post_init__(self) -> None:
        self.front_size = len(self.non_dominated)


@dataclass
class WeightVector:
    """A single weight configuration with evaluated objective scores."""

    weights: dict[str, float]
    ndcg_score: float = 0.0
    diversity_score: float = 0.0
    coverage_score: float = 0.0


# ── Dominance check ─────────────────────────────────────────────────────────


def _dominates(a: dict[str, float], b: dict[str, float], dims: list[str]) -> bool:
    """Strict Pareto dominance: A dominates B iff A[i] >= B[i] for all dims
    and A[i] > B[i] for at least one dim."""
    at_least_one_strict = False
    for d in dims:
        va = a.get(d, 0.0)
        vb = b.get(d, 0.0)
        if va < vb:
            return False
        if va > vb:
            at_least_one_strict = True
    return at_least_one_strict


# ── Core Pareto front computation ────────────────────────────────────────────


def compute_pareto_front(candidates: list[ParetoCandidate]) -> ParetoFront:
    """Compute the rank-0 Pareto front via O(n² · d) pairwise dominance.

    Parameters
    ----------
    candidates : list[ParetoCandidate]
        Candidates with populated ``dimension_scores``.

    Returns
    -------
    ParetoFront
        Partitioned into non-dominated and dominated sets.
    """
    if not candidates:
        return ParetoFront(
            non_dominated=[],
            dominated=[],
            dimension_names=[],
            front_size=0,
        )

    dims = sorted(candidates[0].dimension_scores.keys())
    n = len(candidates)

    dominated_flags = [False] * n
    for i in range(n):
        if dominated_flags[i]:
            continue
        for j in range(n):
            if i == j or dominated_flags[j]:
                continue
            if _dominates(
                candidates[j].dimension_scores,
                candidates[i].dimension_scores,
                dims,
            ):
                dominated_flags[i] = True
                candidates[i].is_dominated = True
                break

    non_dominated: list[ParetoCandidate] = []
    dominated_list: list[ParetoCandidate] = []
    for idx, cand in enumerate(candidates):
        if dominated_flags[idx]:
            dominated_list.append(cand)
        else:
            cand.is_dominated = False
            non_dominated.append(cand)

    return ParetoFront(
        non_dominated=non_dominated,
        dominated=dominated_list,
        dimension_names=dims,
    )


# ── Weight discovery via Dirichlet sampling ──────────────────────────────────


def _shannon_entropy(weights: dict[str, float]) -> float:
    """Normalised Shannon entropy of a weight distribution."""
    vals = np.array(list(weights.values()), dtype=np.float64)
    vals = vals[vals > 0]
    if len(vals) <= 1:
        return 0.0
    total = vals.sum()
    if total == 0:
        return 0.0
    p = vals / total
    raw_h = -float(np.sum(p * np.log(p)))
    max_h = math.log(len(vals))
    if max_h == 0:
        return 0.0
    return raw_h / max_h


def _coverage(weights: dict[str, float], threshold: float = 0.05) -> float:
    """Fraction of dimensions with weight > threshold."""
    if not weights:
        return 0.0
    above = sum(1 for v in weights.values() if v > threshold)
    return above / len(weights)


def _dcg(relevances: list[float], k: int | None = None) -> float:
    """Discounted cumulative gain."""
    if k is None:
        k = len(relevances)
    total = 0.0
    for i, rel in enumerate(relevances[:k]):
        total += rel / math.log2(i + 2)
    return total


def _ndcg(relevances: list[float]) -> float:
    """Normalised DCG."""
    if not relevances:
        return 0.0
    dcg_val = _dcg(relevances)
    ideal = _dcg(sorted(relevances, reverse=True))
    if ideal == 0:
        return 0.0
    return dcg_val / ideal


def _evaluate_weight_vector(
    w: dict[str, float],
    outcome_history: list[dict[str, Any]] | None,
    ema_alpha: float,
) -> tuple[float, float, float]:
    """Return (ndcg_score, diversity_score, coverage_score) for a weight vector."""
    diversity = _shannon_entropy(w)
    coverage = _coverage(w)

    if not outcome_history:
        return 0.0, diversity, coverage

    relevances: list[float] = []
    for outcome in outcome_history:
        dim_scores: dict[str, float] = outcome.get("dimension_scores", {})
        was_selected: bool = outcome.get("was_selected", False)
        scalarised = sum(w.get(d, 0.0) * s for d, s in dim_scores.items())
        if was_selected:
            relevances.append(scalarised)
        else:
            relevances.append(scalarised * ema_alpha)

    relevances.sort(reverse=True)
    ndcg_val = _ndcg(relevances)
    return ndcg_val, diversity, coverage


def discover_pareto_weights(
    dimension_names: list[str],
    current_weights: dict[str, float],
    outcome_history: list[dict[str, Any]] | None = None,
    n_samples: int = 50,
    seed: int = 42,
) -> list[WeightVector]:
    """Discover Pareto-non-dominated weight vectors via Dirichlet sampling.

    Parameters
    ----------
    dimension_names : list[str]
        Names of scoring dimensions.
    current_weights : dict[str, float]
        Baseline weight vector (always included as sample[0]).
    outcome_history : list[dict] | None
        Past outcome dicts with ``dimension_scores`` and ``was_selected``.
    n_samples : int
        Number of weight vectors to sample (including baseline).
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    list[WeightVector]
        Pareto-non-dominated weight vectors sorted by ``ndcg_score`` desc.
    """
    if not dimension_names:
        return []

    rng = np.random.default_rng(seed)
    k = len(dimension_names)
    alpha = np.ones(k, dtype=np.float64)

    raw_samples = rng.dirichlet(alpha, size=max(n_samples - 1, 0))

    baseline_arr = np.array(
        [current_weights.get(d, 1.0 / k) for d in dimension_names],
        dtype=np.float64,
    )
    bsum = baseline_arr.sum()
    if bsum > 0:
        baseline_arr /= bsum
    else:
        baseline_arr = np.ones(k, dtype=np.float64) / k

    all_samples = np.vstack([baseline_arr.reshape(1, -1), raw_samples])

    ema_alpha = 0.1

    weight_vectors: list[WeightVector] = []
    for row in all_samples:
        w = {dim: float(row[i]) for i, dim in enumerate(dimension_names)}
        ndcg_val, div_val, cov_val = _evaluate_weight_vector(w, outcome_history, ema_alpha)
        weight_vectors.append(
            WeightVector(
                weights=w,
                ndcg_score=ndcg_val,
                diversity_score=div_val,
                coverage_score=cov_val,
            )
        )

    # Pareto-filter on (ndcg, diversity, coverage) — all maximised
    n_total = len(weight_vectors)
    dominated_flags = [False] * n_total
    objectives = ["ndcg_score", "diversity_score", "coverage_score"]

    for i in range(n_total):
        if dominated_flags[i]:
            continue
        for j in range(n_total):
            if i == j or dominated_flags[j]:
                continue
            vi = weight_vectors[i]
            vj = weight_vectors[j]
            all_geq = True
            any_strict = False
            for obj in objectives:
                a_val = getattr(vj, obj)
                b_val = getattr(vi, obj)
                if a_val < b_val:
                    all_geq = False
                    break
                if a_val > b_val:
                    any_strict = True
            if all_geq and any_strict:
                dominated_flags[i] = True
                break

    front = [wv for idx, wv in enumerate(weight_vectors) if not dominated_flags[idx]]
    front.sort(key=lambda wv: wv.ndcg_score, reverse=True)

    n_front = len(front)
    pct_pruned = round((1.0 - n_front / n_total) * 100, 1) if n_total else 0.0
    logger.info(
        "Pareto weight discovery: %d/%d vectors on front (%.1f%% pruned)",
        n_front,
        n_total,
        pct_pruned,
    )

    return front
