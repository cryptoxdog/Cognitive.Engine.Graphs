"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [pareto, multi-objective, kge, ensemble]
owner: engine-team
status: active
--- /L9_META ---

Multi-objective Pareto-front ensemble controller extending
``engine.kge.ensemble.EnsembleController``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

from engine.kge.ensemble import (
    EnsembleController,
    EnsembleResult,
    FusionStrategy,
    VariantScore,
)
from engine.scoring.pareto import _dominates

logger = logging.getLogger(__name__)

# Strategy identifiers — must match the StrEnum values in ensemble.py
_STRATEGIES: tuple[FusionStrategy, ...] = (
    FusionStrategy.WEIGHTED_MEAN,
    FusionStrategy.RANK_AGGREGATION,
    FusionStrategy.MIXTURE_EXPERTS,
)

# Objective keys used for dominance comparison
_OBJ_KEYS = ("final_score", "min_confidence", "weight_entropy")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _min_confidence(result: EnsembleResult) -> float:
    """Minimum confidence across component variant scores."""
    if not result.component_scores:
        return 0.0
    return min(vs.confidence for vs in result.component_scores)


def _weight_entropy(result: EnsembleResult) -> float:
    """Normalised Shannon entropy of the result's weight dict."""
    vals = np.array(list(result.weights.values()), dtype=np.float64)
    vals = vals[vals > 0]
    if len(vals) <= 1:
        return 0.0
    total = vals.sum()
    if total == 0:
        return 0.0
    p = vals / total
    raw_h = -float(np.sum(p * np.log(p)))
    max_h = math.log(len(vals))
    return raw_h / max_h if max_h > 0 else 0.0


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class ParetoEnsembleResult:
    """Pareto-front result across multiple ensemble strategies."""

    all_results: list[EnsembleResult]
    pareto_front: list[EnsembleResult]

    def select_by_priority(self, priority: str = "accuracy") -> EnsembleResult:
        """Select a single result from the Pareto front.

        Parameters
        ----------
        priority : str
            ``"accuracy"``   - max ``final_score``
            ``"robustness"`` - max(min(confidence)) across component scores
            ``"diversity"``  - max Shannon entropy of weight distribution
        """
        candidates = self.pareto_front if self.pareto_front else self.all_results
        if not candidates:
            raise ValueError("No ensemble results available for selection")

        if priority == "accuracy":
            return max(candidates, key=lambda r: r.final_score)
        if priority == "robustness":
            return max(candidates, key=_min_confidence)
        if priority == "diversity":
            return max(candidates, key=_weight_entropy)

        raise ValueError(f"Unknown priority: {priority!r}")


# ── Controller ───────────────────────────────────────────────────────────────


class ParetoEnsembleController(EnsembleController):
    """Extends ``EnsembleController`` to produce a Pareto front across all
    fusion strategies rather than routing to a single strategy."""

    def predict_pareto(self, scores: list[VariantScore]) -> ParetoEnsembleResult:
        """Run all ensemble strategies and build a Pareto front.

        1. Execute each strategy via ``self.predict(scores, strategy=...)``.
        2. Build a 3-objective vector per result: ``(final_score,
           min_confidence, weight_entropy)``.
        3. Apply O(n²) strict Pareto dominance to identify non-dominated
           results.

        Returns
        -------
        ParetoEnsembleResult
        """
        all_results: list[EnsembleResult] = []
        for strategy in _STRATEGIES:
            try:
                result = self.predict(scores, strategy=strategy)
                all_results.append(result)
            except Exception:
                logger.warning(
                    "Strategy %s failed during Pareto ensemble; skipping",
                    strategy,
                    exc_info=True,
                )

        if not all_results:
            return ParetoEnsembleResult(all_results=[], pareto_front=[])

        # Build objective dicts for dominance comparison
        obj_dicts: list[dict[str, float]] = []
        for r in all_results:
            obj_dicts.append(
                {
                    "final_score": r.final_score,
                    "min_confidence": _min_confidence(r),
                    "weight_entropy": _weight_entropy(r),
                }
            )

        dims = list(_OBJ_KEYS)
        n = len(all_results)
        dominated_flags = [False] * n

        for i in range(n):
            if dominated_flags[i]:
                continue
            for j in range(n):
                if i == j or dominated_flags[j]:
                    continue
                if _dominates(obj_dicts[j], obj_dicts[i], dims):
                    dominated_flags[i] = True
                    break

        pareto_front = [r for idx, r in enumerate(all_results) if not dominated_flags[idx]]

        logger.info(
            "Pareto ensemble: %d/%d strategies on front",
            len(pareto_front),
            n,
        )

        return ParetoEnsembleResult(
            all_results=all_results,
            pareto_front=pareto_front,
        )
