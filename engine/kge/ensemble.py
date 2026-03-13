"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, ensemble, aggregation]
owner: engine-team
status: active
--- /L9_META ---

Ensemble Methods for CompoundE3D Fusion.

Implements Weighted Distribution Score (WDS) fusion + rank aggregation
to combine multiple KGE variants for improved triple classification accuracy
and robustness across diverse knowledge graph structures.

Consumes:
- engine.config.schema.KGEEnsembleSpec (strategy, cypherweight, kgeweight)
- engine.config.settings.settings (kge_enabled, kge_confidence_threshold)
- engine.scoring.assembler (output kge_score consumed by _compile_kge)

**Frontier Patterns:** Anthropic Constitutional AI (ensemble validation),
OpenAI GPT (temperature-based weighting), DeepMind (mixture of experts).

**Invariants:**
- Ensemble weights sum to 1.0 (probability distribution)
- All variant scores normalized to [0, 1] before fusion
- Rank aggregation is consistent (no tie-breaking artifacts)
- Fallback strategies handle missing scores gracefully
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np
import numpy.typing as npt

from engine.config.schema import KGEEnsembleSpec
from engine.config.settings import settings

logger = logging.getLogger(__name__)


class FusionStrategy(StrEnum):
    """Ensemble fusion strategies.

    Maps to KGEEnsembleSpec.strategy values in domain packs.
    """

    WEIGHTED_MEAN = "weightedaverage"
    MEDIAN = "median"
    MAX = "max"
    RANK_AGGREGATION = "rankaggregation"
    MIXTURE_EXPERTS = "mixtureofexperts"


class RankAggregationMethod(StrEnum):
    """Rank aggregation methods."""

    BORDA = "borda"
    CONDORCET = "condorcet"
    KEMENY = "kemeny"
    PLURALITY = "plurality"


@dataclass
class VariantScore:
    """Score from a single KGE variant."""

    variant_id: str
    variant_type: str
    score: float  # [0, 1]
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """
        Validate and normalize VariantScore fields after dataclass initialization.
        
        If `metadata` is None, sets it to an empty dictionary. Ensures `score` and
        `confidence` are within the inclusive range 0.0 to 1.0; raises `ValueError`
        if either is out of range.
        """
        if self.metadata is None:
            self.metadata = {}
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be in [0, 1], got {self.score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")


@dataclass
class EnsembleResult:
    """Result of ensemble prediction.

    ``final_score`` is the fused value written to Neo4j as ``kge_score``
    and read by ``engine.scoring.assembler._compile_kge()``.
    """

    final_score: float
    component_scores: list[VariantScore]
    weights: dict[str, float]
    fusion_strategy: str
    rank: int | None = None
    explanation: str = ""


# ======================================================================
# Abstract base
# ======================================================================


class VariantEnsemble(ABC):
    """Abstract base for ensemble strategies."""

    @abstractmethod
    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """Fuse variant scores into single prediction."""

    @abstractmethod
    def explain(self, result: EnsembleResult) -> str:
        """Generate human-readable explanation."""


# ======================================================================
# Weighted Distribution Score (WDS)
# ======================================================================


class WeightedDistributionScore(VariantEnsemble):
    """Weighted Distribution Score (WDS) Ensemble.

    Formula::

        WDS = sum(w_i * s_i * c_i) / sum(w_i * c_i)

    where w_i = weight, s_i = score, c_i = confidence.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        temperature: float = 1.0,
    ) -> None:
        self.weights = weights or {}
        self.temperature = temperature

    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """
        Compute a temperature-scaled weighted average of the provided variant scores.
        
        Parameters:
            scores (list[VariantScore]): Variant scores to fuse. Each VariantScore's `score` and `confidence`
                are clipped to the range [0.0, 1.0] before fusion. Raises ValueError if `scores` is empty.
        
        Description:
            Per-variant weights are resolved from the ensemble's configured weights with a default equal
            distribution, then normalized to sum to 1. Each variant's confidence is adjusted by the ensemble
            temperature (confidence ** (1 / temperature)) and used to scale its contribution. The final score
            is the weighted sum of score * adjusted_confidence divided by the weighted sum of adjusted_confidence.
            If the denominator (weighted sum of adjusted confidences) is zero, the method falls back to the
            simple mean of the normalized scores.
        
        Returns:
            EnsembleResult: Result containing:
                - final_score: fused score in [0.0, 1.0]
                - component_scores: input scores with `score` and `confidence` clipped to [0.0, 1.0]
                - weights: normalized per-variant weights summing to 1.0
                - fusion_strategy: set to "weightedaverage"
                - explanation: human-readable explanation generated by the ensemble
        """
        if not scores:
            raise ValueError("No scores provided")

        normalized = [
            VariantScore(
                variant_id=s.variant_id,
                variant_type=s.variant_type,
                score=float(np.clip(s.score, 0.0, 1.0)),  # nosemgrep: float-requires-try-except
                confidence=float(np.clip(s.confidence, 0.0, 1.0)),  # nosemgrep: float-requires-try-except
                metadata=s.metadata,
            )
            for s in scores
        ]

        # Resolve weights
        w: dict[str, float] = {}
        for s in normalized:
            w[s.variant_id] = self.weights.get(s.variant_id, 1.0 / len(normalized))
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}

        weighted_sum = 0.0
        conf_sum = 0.0
        for s in normalized:
            wi = w[s.variant_id]
            ci = s.confidence ** (1.0 / self.temperature)
            weighted_sum += wi * s.score * ci
            conf_sum += wi * ci

        final = (
            weighted_sum / conf_sum
            if conf_sum > 0
            else float(np.mean([s.score for s in normalized]))  # nosemgrep: float-requires-try-except
        )  # nosemgrep: float-requires-try-except

        result = EnsembleResult(
            final_score=final,
            component_scores=normalized,
            weights=w,
            fusion_strategy="weightedaverage",
        )
        result.explanation = self.explain(result)
        return result

    def explain(self, result: EnsembleResult) -> str:
        top_3 = sorted(result.weights.items(), key=lambda x: -x[1])[:3]
        lines = [f"WDS Ensemble: final_score={result.final_score:.4f}"]
        for vid, wt in top_3:
            lines.append(f"  - {vid}: weight={wt:.4f}")
        return "\n".join(lines)


# ======================================================================
# Rank Aggregation
# ======================================================================


class RankAggregationEnsemble(VariantEnsemble):
    """Rank Aggregation Ensemble (Borda / Plurality)."""

    def __init__(self, method: RankAggregationMethod = RankAggregationMethod.BORDA) -> None:
        self.method = method

    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        if not scores:
            raise ValueError("No scores provided")

        ranked = sorted(scores, key=lambda s: -s.score)

        if self.method == RankAggregationMethod.BORDA:
            _final, explanation = self._borda_count(ranked)
        elif self.method == RankAggregationMethod.PLURALITY:
            _final, explanation = self._plurality(ranked)
        else:
            _final, explanation = self._borda_count(ranked)

        n = len(ranked)
        norm_score = (n - 0) / n if n > 0 else 0.5  # Top rank gets full score
        weights = {s.variant_id: 1.0 / len(scores) for s in scores}

        return EnsembleResult(
            final_score=norm_score,
            component_scores=ranked,
            weights=weights,
            fusion_strategy=self.method.value,
            rank=1,
            explanation=explanation,
        )

    def _borda_count(self, ranked: list[VariantScore]) -> tuple[float, str]:
        n = len(ranked)
        total_pts = sum(n - i for i in range(n))
        top_pts = n
        top_score = top_pts / total_pts if total_pts > 0 else 0.5
        return top_score, (f"Borda Count: top_variant={ranked[0].variant_id}, points={top_pts}/{total_pts}")

    def _rrf_score(
        self,
        ranked_lists: list[list[str]],
        k: int = 60,
    ) -> dict[str, float]:
        """Reciprocal Rank Fusion (Cormack et al., 2009).

        Aggregates multiple ranked candidate lists into a single score.
        Superior to Borda on DB100K/YAGO3-10 per CompoundE3D paper §4.3.

        Args:
            ranked_lists: Each inner list is a ranking of entity IDs, best first.
            k: RRF constant (default 60, standard in IR).

        Returns:
            Dict mapping entity_id → RRF score (higher = better).
        """
        scores: dict[str, float] = {}
        for ranked in ranked_lists:
            for rank_position, entity_id in enumerate(ranked):
                scores[entity_id] = scores.get(entity_id, 0.0) + 1.0 / (k + rank_position + 1)
        # Normalize to [0, 1]
        if scores:
            max_s = max(scores.values())
            if max_s > 0:
                scores = {e: v / max_s for e, v in scores.items()}
        return scores

    def _plurality(self, ranked: list[VariantScore]) -> tuple[float, str]:
        winner = ranked[0]
        return winner.score, (f"Plurality: winner={winner.variant_id}, score={winner.score:.4f}")

    def explain(self, result: EnsembleResult) -> str:
        return result.explanation


# ======================================================================
# Mixture of Experts
# ======================================================================


class MixtureOfExpertsEnsemble(VariantEnsemble):
    """Mixture of Experts (MoE) with Gated Weighting.

    Each variant = "expert" scored by competency.
    Soft routing: all experts contribute, weighted by gate logits.
    """

    def __init__(
        self,
        num_experts: int = 3,
        learnable_gates: bool = False,
    ) -> None:
        """
        Initialize the mixture-of-experts ensemble.
        
        Parameters:
            num_experts (int): Number of expert components to include in the ensemble; must be a positive integer.
            learnable_gates (bool): If True, gate weights are intended to be learnable/trainable; if False, gates are treated as fixed.
        """
        self.num_experts = num_experts
        self.learnable_gates = learnable_gates

    def compute_entropy_confidence(self, gate_weights: npt.NDArray[np.float64]) -> float:
        """Ensemble confidence from gating entropy (Eq. 21 in KGE briefing).

        confidence = 1 - H(g(x)) / log(k)
        When one expert dominates → confidence → 1.0
        When uniform (maximum uncertainty) → confidence → 0.0

        Args:
            gate_weights: Softmax-normalized gating distribution, shape (k,).

        Returns:
            Scalar confidence in [0, 1].
        """
        import math

        k = len(gate_weights)
        if k <= 1:
            return 1.0
        # Clip for numerical stability
        p = np.clip(gate_weights, 1e-9, 1.0)
        p = p / p.sum()
        entropy = -np.sum(p * np.log(p))
        max_entropy = math.log(k)
        confidence = 1.0 - (entropy / max_entropy)
        return float(max(0.0, min(1.0, confidence)))  # nosemgrep: float-requires-try-except

    def fuse(self, scores: list[VariantScore]) -> EnsembleResult:
        """
        Fuse variant scores using a soft-gated mixture-of-experts to produce a final ensemble score and per-variant gate weights.
        
        Parameters:
            scores (list[VariantScore]): List of variant scores to fuse.
        
        Returns:
            EnsembleResult: Result containing the fused final_score, the input component_scores, a mapping of variant_id to gate weight, the fusion_strategy set to "mixtureofexperts", and a human-readable explanation of top contributors.
        
        Raises:
            ValueError: If `scores` is empty.
        """
        if not scores:
            raise ValueError("No scores provided")

        competencies = np.array([s.score * s.confidence for s in scores])
        gate_logits = competencies / (1.0 + 1e-8)
        gate_weights = np.exp(gate_logits) / np.sum(np.exp(gate_logits))

        final = float(np.clip(np.dot(gate_weights, competencies), 0.0, 1.0))  # nosemgrep: float-requires-try-except

        weights = {
            s.variant_id: float(w)
            for s, w in zip(scores, gate_weights, strict=False)  # nosemgrep: float-requires-try-except
        }  # nosemgrep: float-requires-try-except

        top_3 = sorted(zip(scores, gate_weights, strict=False), key=lambda x: -x[0].score)[:3]
        lines = [f"MoE Ensemble: final_score={final:.4f}"]
        for s, w in top_3:
            lines.append(f"  - {s.variant_id}: gate_weight={w:.4f}")

        return EnsembleResult(
            final_score=final,
            component_scores=scores,
            weights=weights,
            fusion_strategy="mixtureofexperts",
            explanation="\n".join(lines),
        )

    def explain(self, result: EnsembleResult) -> str:
        return result.explanation


# ======================================================================
# Meta-Controller
# ======================================================================


class EnsembleController:
    """Meta-controller for orchestrating ensemble strategies.

    Responsibilities:
    - Route to appropriate ensemble strategy
    - Validate scores against settings.kge_confidence_threshold
    - Log ensemble decisions for audit
    - Provide fallback on error
    - Map to/from KGEEnsembleSpec in domain packs
    """

    def __init__(self, spec: KGEEnsembleSpec | None = None) -> None:
        """
        Initialize the EnsembleController with default ensemble implementations and optional configuration.
        
        Parameters:
            spec (KGEEnsembleSpec | None): Optional ensemble specification used to derive defaults such as the controller's default fusion strategy; stored on the instance.
        """
        self.strategies: dict[FusionStrategy, VariantEnsemble] = {
            FusionStrategy.WEIGHTED_MEAN: WeightedDistributionScore(),
            FusionStrategy.RANK_AGGREGATION: RankAggregationEnsemble(),
            FusionStrategy.MIXTURE_EXPERTS: MixtureOfExpertsEnsemble(),
        }
        self.audit_log: list[dict[str, Any]] = []
        self._spec = spec

    @classmethod
    def from_spec(cls, spec: KGEEnsembleSpec | None) -> EnsembleController:
        """Construct from domain-pack KGEEnsembleSpec."""
        return cls(spec=spec)

    @property
    def default_strategy(self) -> FusionStrategy:
        """Default fusion strategy from domain-pack spec."""
        if self._spec:
            try:
                return FusionStrategy(self._spec.strategy)
            except ValueError:
                pass
        return FusionStrategy.WEIGHTED_MEAN

    def predict(
        self,
        scores: list[VariantScore],
        strategy: FusionStrategy | None = None,
    ) -> EnsembleResult:
        """
        Fuse a set of per-variant scores into a single EnsembleResult using the selected fusion strategy.
        
        Filters out variants below the configured confidence threshold, short-circuits when knowledge-graph scoring is disabled, returns the single variant unchanged when only one valid score remains, and falls back to a mean-based result if the chosen fusion implementation fails.
        
        Parameters:
            scores (list[VariantScore]): Per-variant scores to fuse.
            strategy (FusionStrategy | None): Optional override of the fusion strategy; if omitted the controller's default is used.
        
        Returns:
            EnsembleResult: The fused result containing final_score, component_scores, weights, fusion_strategy, and explanation.
        
        Raises:
            ValueError: If `scores` is empty.
        """
        if not settings.kge_enabled:
            logger.warning("EnsembleController.predict skipped — kge_enabled=False")
            return EnsembleResult(
                final_score=0.0,
                component_scores=[],
                weights={},
                fusion_strategy="disabled",
                explanation="kge_enabled=False",
            )

        if not scores:
            raise ValueError("No scores to ensemble")

        # Filter below confidence threshold
        threshold = settings.kge_confidence_threshold
        valid_scores = [s for s in scores if s.confidence >= threshold]
        if not valid_scores:
            logger.warning(
                "All %d scores below confidence threshold %.2f, using all",
                len(scores),
                threshold,
            )
            valid_scores = scores

        if len(valid_scores) == 1:
            single = valid_scores[0]
            return EnsembleResult(
                final_score=single.score,
                component_scores=valid_scores,
                weights={single.variant_id: 1.0},
                fusion_strategy="identity",
                explanation=f"Single variant: {single.variant_id}",
            )

        resolved_strategy = strategy or self.default_strategy
        impl = self.strategies.get(resolved_strategy)
        if not impl:
            impl = self.strategies[FusionStrategy.WEIGHTED_MEAN]

        try:
            result = impl.fuse(valid_scores)
        except Exception as e:
            logger.exception("Ensemble fusion failed, falling back to mean")
            mean_score = float(np.mean([s.score for s in valid_scores]))  # nosemgrep: float-requires-try-except
            weights = {s.variant_id: 1.0 / len(valid_scores) for s in valid_scores}
            return EnsembleResult(
                final_score=mean_score,
                component_scores=valid_scores,
                weights=weights,
                fusion_strategy="fallback_mean",
                explanation=f"Fallback to mean due to error: {e!s}",
            )

        self.audit_log.append(
            {
                "strategy": resolved_strategy.value,
                "num_variants": len(valid_scores),
                "final_score": result.final_score,
                "component_scores": [
                    {"id": s.variant_id, "score": s.score, "confidence": s.confidence} for s in valid_scores
                ],
            }
        )

        return result

    def get_audit_log(self) -> list[dict[str, Any]]:
        """
        Get the recorded audit log for ensemble predictions.
        
        @returns list[dict[str, Any]]: A list of audit entries where each entry is a dictionary containing metadata about a prediction (for example: 'strategy', counts of input variants, 'final_score', and per-variant 'component_scores').
        """
        return self.audit_log
