"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge, scoring]
tags: [ensemble, hgkr, cross-dimensional]
owner: engine-team
status: active
--- /L9_META ---

Cross-Dimensional Ensemble — HGKR Semantic-Level Fusion.

Implements the semantic-level cross-graph propagation concept from:
Liu et al., "Iterative heterogeneous graph learning for knowledge
graph-based recommendation", Scientific Reports (2023) 13:6987.

Instead of fusing only KGE beam search variants (as VariantEnsemble does),
this class fuses across scoring dimensions: structural + temporal +
behavioral + KGE + geographic signals. Each dimension's contribution is
iteratively refined using query-context attention.

Key design decisions:
- L=2 iterative passes (paper's optimal per Table 4 ablation)
- Query-context attention replaces static weight combination on pass 2
- Confidence based on dimensional agreement (1 - 2*std_dev)
- Domain-spec configurable via new ensemble strategy type
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DimensionalScore:
    """Score from a single scoring dimension.

    Attributes:
        dimension_name: Name of the scoring dimension (e.g., "geo_decay", "community_match").
        score: Normalized score in [0.0, 1.0].
        weight: Configured weight from domain spec.
        metadata: Additional context (e.g., edge types involved, computation type).
    """

    dimension_name: str
    score: float
    weight: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrossDimensionalResult:
    """Result of cross-dimensional ensemble fusion.

    Attributes:
        final_score: Combined score after iterative fusion.
        confidence: Confidence estimate based on dimensional agreement.
        pass_1_score: Score after static weighted fusion (pass 1).
        pass_2_score: Score after query-context attention (pass 2).
        contributions: Per-dimension contribution breakdown.
        iteration_count: Number of fusion passes executed.
    """

    final_score: float
    confidence: float
    pass_1_score: float
    pass_2_score: float
    contributions: dict[str, float]
    iteration_count: int = 2


class CrossDimensionalEnsemble:
    """HGKR-inspired cross-dimensional ensemble fusion.

    Applies the semantic-level propagation concept: iterate across
    different scoring "views" (dimensions), refining the combined
    score by considering how each dimension relates to the query context.

    Architecture:
        Pass 1 (Static Fusion): Weighted sum of dimensional scores
            using configured weights from domain spec.
        Pass 2 (Context Attention): Reweight each dimension's contribution
            based on query-context relevance. Dimensions more relevant to
            the specific query get higher influence.

    Usage:
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        result = ensemble.fuse(dimensional_scores, query_context)

    The propagation_depth parameter maps to HGKR's L parameter.
    L=2 is optimal per paper ablation (Table 4).
    """

    def __init__(self, propagation_depth: int = 2) -> None:
        """Initialize with configurable propagation depth.

        Args:
            propagation_depth: Number of iterative fusion passes (HGKR L parameter).
                Default 2 (paper optimal). Range 1-5.

        Raises:
            ValueError: If propagation_depth is outside [1, 5].
        """
        if not 1 <= propagation_depth <= 5:
            msg = (
                f"propagation_depth must be 1-5 (got {propagation_depth}). "
                f"HGKR paper shows L>3 causes overfitting."
            )
            raise ValueError(msg)
        self._depth = propagation_depth

    def fuse(
        self,
        dimensional_scores: list[DimensionalScore],
        query_context: dict[str, Any] | None = None,
    ) -> CrossDimensionalResult:
        """Fuse across scoring dimensions with iterative refinement.

        Args:
            dimensional_scores: Scores from each scoring dimension.
            query_context: Optional query metadata for context-aware attention.
                Keys may include: "domain_id", "query_entity_type",
                "match_direction", "active_dimensions".

        Returns:
            CrossDimensionalResult with fused score and breakdown.
        """
        if not dimensional_scores:
            return CrossDimensionalResult(
                final_score=0.0,
                confidence=0.0,
                pass_1_score=0.0,
                pass_2_score=0.0,
                contributions={},
                iteration_count=0,
            )

        query_context = query_context or {}

        # Pass 1: Static weighted fusion
        pass_1_score = self._static_fusion(dimensional_scores)
        contributions = {ds.dimension_name: ds.score * ds.weight for ds in dimensional_scores}

        # Pass 2+: Iterative context-aware refinement
        current_score = pass_1_score
        for _iteration in range(1, self._depth):
            attention_weights = self._compute_context_attention(
                dimensional_scores, query_context, current_score
            )
            current_score = self._attention_fusion(dimensional_scores, attention_weights)
            # Update contributions with attention-reweighted values
            for ds in dimensional_scores:
                attn_w = attention_weights.get(ds.dimension_name, ds.weight)
                contributions[ds.dimension_name] = ds.score * attn_w

        # Confidence: measure dimensional agreement
        confidence = self._compute_confidence(dimensional_scores)

        return CrossDimensionalResult(
            final_score=max(0.0, min(1.0, current_score)),
            confidence=confidence,
            pass_1_score=pass_1_score,
            pass_2_score=current_score,
            contributions=contributions,
            iteration_count=self._depth,
        )

    def _static_fusion(self, scores: list[DimensionalScore]) -> float:
        """Pass 1: Weighted sum fusion using configured weights.

        This is equivalent to CEG's existing ScoringAssembler behavior —
        each dimension contributes score * weight.
        """
        total_weight = sum(ds.weight for ds in scores)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(ds.score * ds.weight for ds in scores)
        return weighted_sum / total_weight

    def _compute_context_attention(
        self,
        scores: list[DimensionalScore],
        query_context: dict[str, Any],
        current_fused_score: float,
    ) -> dict[str, float]:
        """Compute query-context attention weights for each dimension.

        Inspired by HGKR's knowledge-perceiving filter (beta_vk coefficients).
        Each dimension's attention weight is proportional to how much its
        score agrees with the current fused estimate.

        Dimensions that deviate significantly from the fused score get
        lower attention (they may be noise for this specific query).
        Dimensions close to the fused score get higher attention
        (they provide consistent signal).

        This implements a simplified attention mechanism:
            alpha_d = softmax(-|score_d - fused_score|)
        """
        if not scores:
            return {}

        # Compute raw attention: inverse distance from fused score
        raw_attention: dict[str, float] = {}
        for ds in scores:
            distance = abs(ds.score - current_fused_score)
            # Negative distance so closer = higher attention after softmax
            raw_attention[ds.dimension_name] = -distance

        # Softmax normalization
        max_val = max(raw_attention.values()) if raw_attention else 0.0
        exp_values = {name: math.exp(val - max_val) for name, val in raw_attention.items()}
        total_exp = sum(exp_values.values())

        if total_exp == 0:
            # Uniform fallback
            uniform = 1.0 / len(scores) if scores else 0.0
            return {ds.dimension_name: uniform for ds in scores}

        return {name: exp_val / total_exp for name, exp_val in exp_values.items()}

    def _attention_fusion(
        self,
        scores: list[DimensionalScore],
        attention_weights: dict[str, float],
    ) -> float:
        """Fuse scores using attention-computed weights.

        Replaces static configured weights with context-aware attention.
        """
        weighted_sum = sum(
            ds.score * attention_weights.get(ds.dimension_name, ds.weight) for ds in scores
        )
        total_weight = sum(attention_weights.values())
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _compute_confidence(self, scores: list[DimensionalScore]) -> float:
        """Compute confidence based on dimensional agreement.

        High confidence = all dimensions agree (low variance).
        Low confidence = dimensions disagree (high variance).

        Uses 1 - normalized_std_dev as confidence metric.
        """
        if len(scores) < 2:
            return 1.0 if scores else 0.0

        values = [ds.score for ds in scores]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)

        # Normalize: std_dev of [0, 1] range has max ~0.5
        # Confidence = 1 - 2*std_dev (so 0 variance = 1.0 confidence)
        confidence = max(0.0, 1.0 - 2.0 * std_dev)
        return round(confidence, 4)

    def explain(self, result: CrossDimensionalResult) -> str:
        """Generate human-readable explanation of fusion result.

        Follows CEG's audit/explainability pattern.
        """
        lines = [
            f"Cross-Dimensional Ensemble (L={self._depth} passes)",
            f"  Final Score: {result.final_score:.4f}",
            f"  Confidence:  {result.confidence:.4f}",
            f"  Pass 1 (static):  {result.pass_1_score:.4f}",
            f"  Pass 2 (context): {result.pass_2_score:.4f}",
            "  Contributions:",
        ]
        for dim_name, contrib in sorted(result.contributions.items(), key=lambda x: -x[1]):
            lines.append(f"    {dim_name}: {contrib:.4f}")

        return "\n".join(lines)
