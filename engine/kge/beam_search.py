"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, beam-search, link-prediction]
owner: engine-team
status: active
--- /L9_META ---

Beam Search for CompoundE3D Variant Discovery.

Implements efficient beam search over 3D transformation space to discover
novel KGE variants and geometric embeddings with constraint satisfaction.

Consumes:
- engine.config.schema.KGEBeamSearchSpec (beamwidth, maxdepth)
- engine.config.settings.settings (kge_enabled gate)
- engine.kge.compound_e3d.CompoundE3D (model scoring)
- engine.kge.transformations.* (3D operations)

**Frontier Patterns:** DeepMind AlphaGo (beam width tuning), OpenAI GPT
(nucleus sampling adapted for geometric space), Anthropic Constitutional
AI (constraint satisfaction).

**Invariants:**
- Beam width >= 1 (single-path degenerates to greedy)
- Depth <= max_hops ensures termination
- All candidates scored consistently (no tie-breaking bias)
- Pruned candidates logged for audit trail
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

from engine.config.schema import KGEBeamSearchSpec
from engine.config.settings import settings
from engine.kge.compound_e3d import CompoundE3D
from engine.kge.transformations import (
    Flip,
    Hyperplane,
    Rotation,
    Scale,
    Transformation3D,
    Translation,
)

logger = logging.getLogger(__name__)


@dataclass
class CascadeVariant:
    """Represents a discovered CompoundE3D operator cascade.

    Stores the ordered list of transformation class names for
    head and tail operators, plus validation MRR achieved.

    Ge et al. (2023) Algorithm 1: each variant is a candidate
    in the beam search over the design space.
    """

    head_ops: list[str]  # e.g. ["Scaling", "Translation"]
    tail_ops: list[str]  # e.g. ["Translation", "Rotation", "Scaling"]
    val_mrr: float = 0.0  # Mean Reciprocal Rank on validation set
    param_count: int = 0  # Number of learnable parameters in cascade

    def __post_init__(self) -> None:
        if not (0.0 <= self.val_mrr <= 1.0):
            msg = f"CascadeVariant.val_mrr must be in [0, 1], got {self.val_mrr}"
            raise ValueError(msg)
        if self.param_count < 0:
            msg = f"CascadeVariant.param_count must be >= 0, got {self.param_count}"
            raise ValueError(msg)


class PruneStrategy(StrEnum):
    """Pruning strategies for beam search."""

    SCORE_THRESHOLD = "score_threshold"
    DIVERSITY = "diversity"
    CONSTRAINT = "constraint"
    COMBINED = "combined"


@dataclass
class BeamCandidate:
    """Represents a candidate variant in beam search."""

    transformation_id: str
    transformation_type: str
    params: dict[str, float]
    score: float
    depth: int
    parent_id: str | None = None

    def __lt__(self, other: BeamCandidate) -> bool:
        """Enable min-heap ordering (negated for max-heap)."""
        return (-self.score, self.transformation_id) < (
            -other.score,
            other.transformation_id,
        )

    def to_dict(self) -> dict:
        """Serialize candidate for PacketEnvelope / audit trail."""
        return {
            "id": self.transformation_id,
            "type": self.transformation_type,
            "params": self.params,
            "score": float(self.score),
            "depth": self.depth,
            "parent_id": self.parent_id,
        }


@dataclass
class BeamSearchConfig:
    """Configuration for beam search.

    Can be constructed from KGEBeamSearchSpec in a domain pack::

        config = BeamSearchConfig.from_spec(domain_spec.kge.beamsearch)
    """

    beam_width: int = 5
    max_depth: int = 3
    prune_strategy: PruneStrategy = PruneStrategy.COMBINED
    score_threshold: float = 0.3
    diversity_threshold: float = 0.8
    constraint_validators: list[Callable[[Transformation3D], bool]] = field(default_factory=list)
    log_pruned: bool = True

    @classmethod
    def from_spec(cls, spec: KGEBeamSearchSpec | None) -> BeamSearchConfig:
        """Construct from domain-pack KGEBeamSearchSpec."""
        if spec is None:
            return cls()
        return cls(
            beam_width=spec.beamwidth,
            max_depth=spec.maxdepth,
        )


class BeamSearchEngine:
    """
    Beam search engine for discovering CompoundE3D variants.

    Algorithm:
        1. Initialize beam with identity + base transformations.
        2. For each depth level:
            a. Generate successors (apply 3D ops to each beam candidate).
            b. Score candidates using CompoundE3D model.
            c. Prune by strategy (threshold, diversity, constraints).
            d. Keep top-K by score.
        3. Return final beam (best variants + audit trail).
    """

    def __init__(
        self,
        model: CompoundE3D,
        config: BeamSearchConfig,
    ) -> None:
        self.model = model
        self.config = config
        self.search_history: list[dict] = []
        self.pruned_candidates: list[BeamCandidate] = []
        self._next_id = 0

    def _gen_id(self) -> str:
        self._next_id += 1
        return f"var_{self._next_id:04d}"

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_candidate(
        self,
        transformation: Transformation3D,
        entity_ids: list[str] | None = None,
    ) -> float:
        """Score a candidate transformation.

        Score by:
        1. Applying the transformation to sample entity embeddings.
        2. Evaluating constraint satisfaction.

        Falls back to random scoring ONLY if no model embeddings are
        available (bootstrap phase), with a clear warning.

        This replaces the previous random.uniform() stub which produced
        non-deterministic, meaningless beam search results.
        """
        import warnings

        rng = np.random.default_rng()

        # Check if model has trained embeddings
        if not self.model._entity_embeddings:
            warnings.warn(
                "_score_candidate: no model embeddings available. "
                "Returning random score (bootstrap only — not for production).",
                RuntimeWarning,
                stacklevel=2,
            )
            return float(rng.uniform(0.0, 0.3))

        # Sample entities for evaluation
        sample_ids = entity_ids or list(self.model._entity_embeddings.keys())[:100]
        if not sample_ids:
            return float(rng.uniform(0.0, 0.3))

        # Compute quality score based on transformation consistency
        quality_scores = []
        for eid in sample_ids:
            emb = self.model._entity_embeddings.get(eid)
            if emb is None:
                continue
            transformed = transformation.apply(emb)
            # Quality: inverse of transformation magnitude (prefer small changes)
            diff = np.linalg.norm(transformed - emb)
            quality_scores.append(1.0 / (1.0 + diff))

        quality_score = float(np.mean(quality_scores)) if quality_scores else 0.5

        # Constraint satisfaction
        constraint_score = 1.0
        for validator in self.config.constraint_validators:
            try:
                if not validator(transformation):
                    constraint_score *= 0.5
            except Exception:
                constraint_score *= 0.7

        return float(quality_score * constraint_score)

    def _stopping_criterion(
        self,
        beam: list[CascadeVariant],
        gamma: float = 0.005,
        max_params: int | None = None,
    ) -> bool:
        """Adaptive stopping for beam search (Algorithm 1, Ge et al. 2023).

        Terminates when marginal MRR gain per added parameter falls below
        gamma, OR when max_params is exceeded.

        Args:
            beam:       Current top-k CascadeVariants sorted by val_mrr desc.
            gamma:      Minimum MRR/param improvement threshold (default 0.005).
            max_params: Hard cap on parameter count (None = no cap).

        Returns:
            True if search should stop, False to continue.
        """
        if len(beam) < 2:
            return False
        best = beam[0]
        second = beam[1]
        if best.param_count <= second.param_count:
            return False
        delta_mrr = best.val_mrr - second.val_mrr
        delta_params = best.param_count - second.param_count
        efficiency = delta_mrr / max(delta_params, 1)
        if max_params is not None and best.param_count >= max_params:
            return True
        return efficiency < gamma

    # ------------------------------------------------------------------
    # Successor Generation
    # ------------------------------------------------------------------

    def _generate_successors(
        self,
        candidate: BeamCandidate,
    ) -> list[BeamCandidate]:
        """Generate successor candidates by applying 3D transformations."""
        successors: list[BeamCandidate] = []

        transform_factories = [
            ("rotation", self._make_rotation_variants),
            ("scale", self._make_scale_variants),
            ("translation", self._make_translation_variants),
            ("flip", self._make_flip_variants),
            ("hyperplane", self._make_hyperplane_variants),
        ]

        for tx_type, factory in transform_factories:
            for params in factory():
                tx = self._build_transformation(tx_type, params)
                score = self._score_candidate(tx)
                successor = BeamCandidate(
                    transformation_id=self._gen_id(),
                    transformation_type=tx_type,
                    params=params,
                    score=score,
                    depth=candidate.depth + 1,
                    parent_id=candidate.transformation_id,
                )
                successors.append(successor)

        return successors

    def _make_rotation_variants(self) -> list[dict[str, float]]:
        variants: list[dict[str, float]] = []
        for angle in [15, 30, 45, 60, 90]:
            for axis in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
                variants.append(
                    {
                        "angle": float(angle),
                        "axis_x": float(axis[0]),
                        "axis_y": float(axis[1]),
                        "axis_z": float(axis[2]),
                    }
                )
        return variants

    def _make_scale_variants(self) -> list[dict[str, float]]:
        return [{"factor": f} for f in [0.5, 0.75, 1.25, 1.5, 2.0]]

    def _make_translation_variants(self) -> list[dict[str, float]]:
        variants: list[dict[str, float]] = []
        for delta in [0.1, 0.25, 0.5]:
            for axis_idx in range(3):
                offset = [0.0, 0.0, 0.0]
                offset[axis_idx] = delta
                variants.append(
                    {
                        "offset_x": offset[0],
                        "offset_y": offset[1],
                        "offset_z": offset[2],
                    }
                )
        return variants

    def _make_flip_variants(self) -> list[dict[str, float]]:
        return [{"axis": float(axis)} for axis in [0, 1, 2]]

    def _make_hyperplane_variants(self) -> list[dict[str, float]]:
        variants: list[dict[str, float]] = []
        for a, b, c in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]:
            for d in [-1.0, -0.5, 0.0, 0.5, 1.0]:
                variants.append(
                    {
                        "a": float(a),
                        "b": float(b),
                        "c": float(c),
                        "d": float(d),
                    }
                )
        return variants

    def _build_transformation(
        self,
        tx_type: str,
        params: dict[str, float],
    ) -> Transformation3D:
        """Build Transformation3D from type + params."""
        if tx_type == "rotation":
            return Rotation(
                angle=params["angle"],
                axis=(params["axis_x"], params["axis_y"], params["axis_z"]),
            )
        if tx_type == "scale":
            return Scale(factor=params["factor"])
        if tx_type == "translation":
            return Translation(
                offset=(params["offset_x"], params["offset_y"], params["offset_z"]),
            )
        if tx_type == "flip":
            return Flip(axis=int(params["axis"]))
        if tx_type == "hyperplane":
            return Hyperplane(
                normal=(params["a"], params["b"], params["c"]),
                d=params["d"],
            )
        raise ValueError(f"Unknown transformation type: {tx_type}")

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------

    def _prune_candidates(
        self,
        candidates: list[BeamCandidate],
    ) -> list[BeamCandidate]:
        """Prune candidates by configured strategy."""
        if self.config.prune_strategy == PruneStrategy.SCORE_THRESHOLD:
            return self._prune_by_threshold(candidates)
        if self.config.prune_strategy == PruneStrategy.DIVERSITY:
            return self._prune_by_diversity(candidates)
        if self.config.prune_strategy == PruneStrategy.CONSTRAINT:
            return self._prune_by_constraint(candidates)
        # PruneStrategy.COMBINED
        candidates = self._prune_by_threshold(candidates)
        candidates = self._prune_by_diversity(candidates)
        candidates = self._prune_by_constraint(candidates)
        return candidates

    def _prune_by_threshold(self, candidates: list[BeamCandidate]) -> list[BeamCandidate]:
        kept: list[BeamCandidate] = []
        pruned: list[BeamCandidate] = []
        for c in candidates:
            (kept if c.score >= self.config.score_threshold else pruned).append(c)
        if self.config.log_pruned and pruned:
            self.pruned_candidates.extend(pruned)
        return kept

    def _prune_by_diversity(self, candidates: list[BeamCandidate]) -> list[BeamCandidate]:
        if not candidates:
            return candidates
        sorted_cands = sorted(candidates, key=lambda c: -c.score)
        kept = [sorted_cands[0]]
        pruned: list[BeamCandidate] = []

        for candidate in sorted_cands[1:]:
            min_sim = min(self._param_similarity(candidate.params, k.params) for k in kept)
            if min_sim < self.config.diversity_threshold:
                kept.append(candidate)
            else:
                pruned.append(candidate)

        if self.config.log_pruned and pruned:
            self.pruned_candidates.extend(pruned)
        return kept

    def _prune_by_constraint(self, candidates: list[BeamCandidate]) -> list[BeamCandidate]:
        if not self.config.constraint_validators:
            return candidates
        kept: list[BeamCandidate] = []
        pruned: list[BeamCandidate] = []
        for candidate in candidates:
            tx = self._build_transformation(candidate.transformation_type, candidate.params)
            valid = all(v(tx) for v in self.config.constraint_validators)
            (kept if valid else pruned).append(candidate)
        if self.config.log_pruned and pruned:
            self.pruned_candidates.extend(pruned)
        return kept

    @staticmethod
    def _param_similarity(
        params1: dict[str, float],
        params2: dict[str, float],
    ) -> float:
        """Similarity in [0, 1] between parameter dicts.  1 = identical."""
        all_keys = set(params1.keys()) | set(params2.keys())
        if not all_keys:
            return 1.0
        distances = [(params1.get(k, 0.0) - params2.get(k, 0.0)) ** 2 for k in all_keys]
        return float(1.0 / (1.0 + np.sqrt(sum(distances))))

    # ------------------------------------------------------------------
    # Main search
    # ------------------------------------------------------------------

    def search(self) -> dict:
        """Execute beam search for variant discovery.

        Returns::

            {
                "variants": [best candidates by score],
                "depth_levels": {depth: [candidates]},
                "pruned": [pruned candidates for audit],
                "audit_trail": detailed search log,
                "search_config": config snapshot,
            }
        """
        if not settings.kge_enabled:
            logger.warning("BeamSearchEngine.search skipped — kge_enabled=False")
            return {"variants": [], "status": "skipped", "reason": "kge_enabled=False"}

        # E-02 Guard: ensure model is set before running search
        if self.model is None:
            msg = (  # type: ignore[unreachable]  # kge_enabled is runtime-configurable
                "BeamSearch: config.model must be set before running search. "
                "Assign a trained CompoundE3D instance to config.model."
            )
            raise ValueError(msg)

        initial = BeamCandidate(
            transformation_id=self._gen_id(),
            transformation_type="identity",
            params={},
            score=1.0,
            depth=0,
        )

        beam = [initial]
        depth_levels: dict[int, list[BeamCandidate]] = {0: [initial]}

        for depth in range(1, self.config.max_depth + 1):
            all_successors: list[BeamCandidate] = []
            for candidate in beam:
                all_successors.extend(self._generate_successors(candidate))

            all_successors.sort(key=lambda c: -c.score)
            pruned_successors = self._prune_candidates(all_successors)
            beam = pruned_successors[: self.config.beam_width]
            depth_levels[depth] = beam

            self.search_history.append(
                {
                    "depth": depth,
                    "generated": len(all_successors),
                    "after_pruning": len(pruned_successors),
                    "beam_size": len(beam),
                    "top_score": beam[0].score if beam else 0.0,
                }
            )

        return {
            "variants": [c.to_dict() for c in beam],
            "depth_levels": {d: [c.to_dict() for c in cands] for d, cands in depth_levels.items()},
            "pruned": [c.to_dict() for c in self.pruned_candidates],
            "audit_trail": self.search_history,
            "search_config": {
                "beam_width": self.config.beam_width,
                "max_depth": self.config.max_depth,
                "prune_strategy": self.config.prune_strategy.value,
                "score_threshold": self.config.score_threshold,
            },
        }
