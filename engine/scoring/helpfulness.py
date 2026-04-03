"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [hoprag, helpfulness, scoring]
owner: engine-team
status: active
--- /L9_META ---

HopRAG Helpfulness scoring dimension.

Implements the Helpfulness metric H from HopRAG (ACL 2025, §3.3.3 Eq. 3):

    H_i = alpha * SIM(v_i, q) + (1 - alpha) * IMP(v_i, C_count)

where SIM is the cosine similarity between vertex embedding and query,
and IMP is the normalized visit count from multi-hop BFS traversal.

Consumes:
- Pre-computed similarity_score on candidate nodes
- Pre-computed visit_count_normalized on candidate nodes (from MultiHopTraverser)
- Alpha parameter from domain-spec or HopRAGConfig

Integrates with:
- engine.scoring.assembler.ScoringAssembler (via ComputationType.HELPFULNESS dispatch)
- engine.traversal.multihop.MultiHopTraverser (writes visit counts consumed here)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HelpfulnessResult:
    """Result of a helpfulness computation.

    Attributes:
        score: The computed helpfulness score in [0.0, 1.0].
        similarity: The input similarity component.
        importance: The input importance component.
        alpha: The balance parameter used.
    """

    score: float
    similarity: float
    importance: float
    alpha: float


class HelpfulnessScorer:
    """Computes HopRAG Helpfulness scores.

    The Helpfulness metric combines query-vertex similarity (SIM) with
    traversal-derived importance (IMP) into a single ranking signal.

    The alpha parameter controls the balance:
        - alpha=1.0: pure similarity (no traversal signal)
        - alpha=0.5: equal balance (paper default)
        - alpha=0.0: pure importance (traversal signal only)

    Usage::

        scorer = HelpfulnessScorer(alpha=0.5)
        result = scorer.compute(similarity=0.82, importance=0.45)
        score = result.score  # 0.635
    """

    def __init__(self, alpha: float = 0.5) -> None:
        """Initialize HelpfulnessScorer.

        Args:
            alpha: Balance between similarity and importance.
                   Must be in [0.0, 1.0]. Default 0.5 per HopRAG paper.

        Raises:
            ValueError: If alpha is outside [0.0, 1.0].
        """
        if not 0.0 <= alpha <= 1.0:
            msg = f"alpha must be in [0.0, 1.0], got {alpha}"
            raise ValueError(msg)
        self._alpha = alpha

    @property
    def alpha(self) -> float:
        """Current alpha balance parameter."""
        return self._alpha

    def compute(self, similarity: float, importance: float) -> HelpfulnessResult:
        """Compute the Helpfulness score.

        Args:
            similarity: Cosine similarity between vertex and query, in [0.0, 1.0].
            importance: Normalized visit count from BFS traversal, in [0.0, 1.0].

        Returns:
            HelpfulnessResult with the computed score and input values.

        Raises:
            ValueError: If similarity or importance is outside [0.0, 1.0].
        """
        if not 0.0 <= similarity <= 1.0:
            msg = f"similarity must be in [0.0, 1.0], got {similarity}"
            raise ValueError(msg)
        if not 0.0 <= importance <= 1.0:
            msg = f"importance must be in [0.0, 1.0], got {importance}"
            raise ValueError(msg)

        score = self._alpha * similarity + (1.0 - self._alpha) * importance
        return HelpfulnessResult(
            score=score,
            similarity=similarity,
            importance=importance,
            alpha=self._alpha,
        )

    def compute_batch(
        self,
        candidates: list[dict[str, float]],
    ) -> list[HelpfulnessResult]:
        """Compute Helpfulness for a batch of candidates.

        Args:
            candidates: List of dicts with keys 'similarity' and 'importance'.

        Returns:
            List of HelpfulnessResult, one per candidate.
        """
        results: list[HelpfulnessResult] = []
        for candidate in candidates:
            sim = candidate.get("similarity", 0.0)
            imp = candidate.get("importance", 0.0)
            results.append(self.compute(similarity=sim, importance=imp))
        return results

    def rank(
        self,
        candidates: list[dict[str, float]],
        top_k: int | None = None,
    ) -> list[tuple[int, HelpfulnessResult]]:
        """Compute and rank candidates by Helpfulness score.

        Args:
            candidates: List of dicts with keys 'similarity' and 'importance'.
            top_k: Return only top-k results (None = all).

        Returns:
            List of (original_index, HelpfulnessResult) sorted by score descending.
        """
        results = self.compute_batch(candidates)
        indexed = list(enumerate(results))
        indexed.sort(key=lambda x: -x[1].score)
        if top_k is not None:
            indexed = indexed[:top_k]
        return indexed


def compute_helpfulness(
    similarity: float,
    importance: float,
    alpha: float = 0.5,
) -> float:
    """Convenience function for single-shot Helpfulness computation.

    Args:
        similarity: Cosine similarity between vertex and query, in [0.0, 1.0].
        importance: Normalized visit count, in [0.0, 1.0].
        alpha: Balance parameter, in [0.0, 1.0]. Default 0.5.

    Returns:
        Helpfulness score in [0.0, 1.0].
    """
    scorer = HelpfulnessScorer(alpha=alpha)
    return scorer.compute(similarity=similarity, importance=importance).score


def compile_helpfulness_cypher(
    similarity_prop: str = "similarity_score",
    importance_prop: str = "visit_count_normalized",
    alpha: float = 0.5,
    default_when_null: float = 0.0,
) -> str:
    """Generate Cypher expression for Helpfulness scoring dimension.

    This produces a Cypher expression suitable for use in ScoringAssembler's
    WITH clause. It reads pre-computed properties from candidate nodes.

    Args:
        similarity_prop: Node property name for similarity score.
        importance_prop: Node property name for normalized visit count.
        alpha: Balance parameter for SIM/IMP weighting.
        default_when_null: Fallback value when properties are NULL.

    Returns:
        Cypher expression string.
    """
    return (
        f"CASE WHEN candidate.{similarity_prop} IS NULL THEN {default_when_null} "
        f"ELSE ({alpha} * coalesce(candidate.{similarity_prop}, 0) + "
        f"{1.0 - alpha} * coalesce(candidate.{importance_prop}, 0)) END"
    )
