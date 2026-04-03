"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [diagnostics]
tags: [diagnostics, fingerprint, persona]
owner: engine-team
status: active
--- /L9_META ---

engine/diagnostics/fingerprint.py
Algorithmic Fingerprinting — computes a category frequency distribution
from persona scoring outputs to create a unique "fingerprint" that can
be compared across time windows for drift detection.

A fingerprint captures *what kinds of results* a persona produces:
  - Which score buckets candidates fall into (low/mid/high)
  - Which dimensions dominate the scoring
  - The entropy of the output distribution (uniformity vs. concentration)

This is the foundation for the dissimilarity module which detects
when a persona's behavior has changed significantly.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Score Buckets ────────────────────────────────────────────

# Configurable bucket boundaries for score categorization
DEFAULT_BUCKET_BOUNDARIES = (0.0, 0.25, 0.50, 0.75, 1.0)
DEFAULT_BUCKET_LABELS = ("very_low", "low", "medium", "high")


def _bucket_label(score: float, boundaries: tuple[float, ...], labels: tuple[str, ...]) -> str:
    """Assign a score to a bucket label based on boundaries."""
    for i in range(len(labels)):
        if score < boundaries[i + 1]:
            return labels[i]
    return labels[-1]


# ── Fingerprint Data Structure ───────────────────────────────


@dataclass(frozen=True)
class AlgorithmicFingerprint:
    """
    Immutable fingerprint of a persona's scoring output distribution.

    Attributes:
        persona_id: Identifier of the persona that produced this fingerprint.
        window_id: Time window or batch identifier.
        sample_count: Number of candidates in the sample.
        score_distribution: Mapping of bucket label -> relative frequency.
        dimension_dominance: Mapping of dimension name -> fraction of candidates
            where this dimension contributed the highest score.
        entropy: Shannon entropy of the score distribution (higher = more uniform).
        top_dimension: The dimension that most frequently dominates.
        concentration_ratio: Fraction of candidates in the single most common bucket.
    """

    persona_id: str
    window_id: str
    sample_count: int
    score_distribution: dict[str, float]
    dimension_dominance: dict[str, float]
    entropy: float
    top_dimension: str
    concentration_ratio: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """Convert fingerprint to a fixed-length numeric vector for comparison.

        Vector layout: [bucket_freqs..., dimension_freqs..., entropy, concentration]
        Bucket frequencies are ordered by DEFAULT_BUCKET_LABELS.
        Dimension frequencies are ordered alphabetically by dimension name.
        """
        bucket_vec = [self.score_distribution.get(label, 0.0) for label in DEFAULT_BUCKET_LABELS]
        dim_vec = [v for _, v in sorted(self.dimension_dominance.items())]
        return bucket_vec + dim_vec + [self.entropy, self.concentration_ratio]


# ── Computation ──────────────────────────────────────────────


def compute_fingerprint(
    persona_id: str,
    window_id: str,
    candidates: list[dict[str, Any]],
    *,
    score_key: str = "total_score",
    dimension_scores_key: str = "dimension_scores",
    bucket_boundaries: tuple[float, ...] = DEFAULT_BUCKET_BOUNDARIES,
    bucket_labels: tuple[str, ...] = DEFAULT_BUCKET_LABELS,
) -> AlgorithmicFingerprint:
    """
    Compute an algorithmic fingerprint from a batch of scored candidates.

    Args:
        persona_id: Identifier of the persona.
        window_id: Time window or batch identifier.
        candidates: List of candidate dicts, each containing at minimum
            a total score and optionally per-dimension scores.
        score_key: Key in candidate dict for the total score.
        dimension_scores_key: Key in candidate dict for per-dimension scores.
        bucket_boundaries: Tuple of boundary values for score bucketing.
        bucket_labels: Tuple of labels for each bucket.

    Returns:
        An AlgorithmicFingerprint capturing the distribution characteristics.
    """
    if len(bucket_boundaries) != len(bucket_labels) + 1:
        raise ValueError(
            f"bucket_boundaries ({len(bucket_boundaries)}) must have exactly "
            f"one more element than bucket_labels ({len(bucket_labels)})"
        )

    if not candidates:
        return AlgorithmicFingerprint(
            persona_id=persona_id,
            window_id=window_id,
            sample_count=0,
            score_distribution=dict.fromkeys(bucket_labels, 0.0),
            dimension_dominance={},
            entropy=0.0,
            top_dimension="none",
            concentration_ratio=0.0,
        )

    n = len(candidates)

    # Score distribution
    bucket_counts: Counter[str] = Counter()
    dimension_wins: Counter[str] = Counter()

    for candidate in candidates:
        score = candidate.get(score_key, 0.0)
        if not isinstance(score, (int, float)):
            score = 0.0
        # Clamp to [0, 1] for bucketing
        score = max(0.0, min(1.0, float(score)))
        bucket = _bucket_label(score, bucket_boundaries, bucket_labels)
        bucket_counts[bucket] += 1

        # Dimension dominance
        dim_scores = candidate.get(dimension_scores_key, {})
        if isinstance(dim_scores, dict) and dim_scores:
            numeric_dims = {k: v for k, v in dim_scores.items() if isinstance(v, (int, float))}
            if numeric_dims:
                top_dim = max(numeric_dims, key=lambda k: abs(numeric_dims[k]))
                dimension_wins[top_dim] += 1

    # Normalize to relative frequencies
    score_distribution = {label: bucket_counts.get(label, 0) / n for label in bucket_labels}

    total_dim_wins = sum(dimension_wins.values()) or 1
    dimension_dominance = {dim: count / total_dim_wins for dim, count in dimension_wins.most_common()}

    # Shannon entropy of score distribution
    entropy = 0.0
    for freq in score_distribution.values():
        if freq > 0:
            entropy -= freq * math.log2(freq)

    # Top dimension and concentration
    top_dimension = dimension_wins.most_common(1)[0][0] if dimension_wins else "none"
    concentration_ratio = max(score_distribution.values()) if score_distribution else 0.0

    fingerprint = AlgorithmicFingerprint(
        persona_id=persona_id,
        window_id=window_id,
        sample_count=n,
        score_distribution=score_distribution,
        dimension_dominance=dimension_dominance,
        entropy=round(entropy, 6),
        top_dimension=top_dimension,
        concentration_ratio=round(concentration_ratio, 6),
    )

    logger.info(
        "Computed fingerprint: persona=%s window=%s n=%d entropy=%.4f top_dim=%s",
        persona_id,
        window_id,
        n,
        entropy,
        top_dimension,
    )

    return fingerprint
