"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [diagnostics]
tags: [diagnostics, dissimilarity, drift]
owner: engine-team
status: active
--- /L9_META ---

engine/diagnostics/dissimilarity.py
Chi-squared dissimilarity and drift detection between AlgorithmicFingerprints.

Compares two fingerprints (baseline vs. current) using the chi-squared
statistic on their score distributions and dimension dominance profiles.
When the dissimilarity exceeds a configurable threshold, a drift alert
is raised.

This implements the "Algorithmic Fingerprinting" diagnostic described
in the CEG Integration Blueprint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from engine.diagnostics.fingerprint import AlgorithmicFingerprint

logger = logging.getLogger(__name__)


# ── Chi-Squared Dissimilarity ────────────────────────────────


def chi_squared_dissimilarity(
    baseline: dict[str, float],
    current: dict[str, float],
    *,
    smoothing: float = 1e-10,
) -> float:
    """
    Compute the chi-squared dissimilarity between two frequency distributions.

    Uses the symmetric chi-squared formula:
        D = sum( (p_i - q_i)^2 / (p_i + q_i) )

    where p_i and q_i are the frequencies for category i in baseline and
    current respectively.

    Args:
        baseline: Baseline frequency distribution (category -> relative freq).
        current: Current frequency distribution (category -> relative freq).
        smoothing: Small constant added to avoid division by zero.

    Returns:
        Non-negative dissimilarity score. 0.0 means identical distributions.
        Higher values indicate greater divergence.
    """
    all_keys = set(baseline) | set(current)
    if not all_keys:
        return 0.0

    total = 0.0
    for key in all_keys:
        p = baseline.get(key, 0.0)
        q = current.get(key, 0.0)
        denom = p + q + smoothing
        total += (p - q) ** 2 / denom

    return total


def _euclidean_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute Euclidean distance between two vectors of equal length."""
    if len(vec_a) != len(vec_b):
        # Pad shorter vector with zeros
        max_len = max(len(vec_a), len(vec_b))
        vec_a = vec_a + [0.0] * (max_len - len(vec_a))
        vec_b = vec_b + [0.0] * (max_len - len(vec_b))

    return sum((a - b) ** 2 for a, b in zip(vec_a, vec_b, strict=True)) ** 0.5


# ── Drift Detection ─────────────────────────────────────────


@dataclass(frozen=True)
class DriftReport:
    """
    Result of comparing a baseline fingerprint against a current one.

    Attributes:
        persona_id: Persona being monitored.
        baseline_window: Window ID of the baseline fingerprint.
        current_window: Window ID of the current fingerprint.
        score_dissimilarity: Chi-squared dissimilarity of score distributions.
        dimension_dissimilarity: Chi-squared dissimilarity of dimension dominance.
        vector_distance: Euclidean distance between full fingerprint vectors.
        entropy_delta: Change in entropy (current - baseline).
        concentration_delta: Change in concentration ratio.
        drift_detected: True if any metric exceeds its threshold.
        drift_reasons: List of human-readable reasons for drift detection.
        severity: "none" | "low" | "medium" | "high" based on magnitude.
    """

    persona_id: str
    baseline_window: str
    current_window: str
    score_dissimilarity: float
    dimension_dissimilarity: float
    vector_distance: float
    entropy_delta: float
    concentration_delta: float
    drift_detected: bool
    drift_reasons: list[str]
    severity: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "persona_id": self.persona_id,
            "baseline_window": self.baseline_window,
            "current_window": self.current_window,
            "score_dissimilarity": round(self.score_dissimilarity, 6),
            "dimension_dissimilarity": round(self.dimension_dissimilarity, 6),
            "vector_distance": round(self.vector_distance, 6),
            "entropy_delta": round(self.entropy_delta, 6),
            "concentration_delta": round(self.concentration_delta, 6),
            "drift_detected": self.drift_detected,
            "drift_reasons": self.drift_reasons,
            "severity": self.severity,
        }


def detect_drift(
    baseline: AlgorithmicFingerprint,
    current: AlgorithmicFingerprint,
    *,
    score_threshold: float = 0.15,
    dimension_threshold: float = 0.20,
    vector_threshold: float = 0.30,
    entropy_threshold: float = 0.50,
    concentration_threshold: float = 0.25,
) -> DriftReport:
    """
    Compare a baseline fingerprint against a current one and detect drift.

    Drift is detected when any of the following conditions are met:
      - Score distribution chi-squared dissimilarity > score_threshold
      - Dimension dominance chi-squared dissimilarity > dimension_threshold
      - Full vector Euclidean distance > vector_threshold
      - Absolute entropy change > entropy_threshold
      - Absolute concentration ratio change > concentration_threshold

    Args:
        baseline: The reference fingerprint (e.g. from last week).
        current: The current fingerprint (e.g. from today).
        score_threshold: Max allowed score distribution dissimilarity.
        dimension_threshold: Max allowed dimension dominance dissimilarity.
        vector_threshold: Max allowed Euclidean distance between vectors.
        entropy_threshold: Max allowed absolute entropy change.
        concentration_threshold: Max allowed absolute concentration change.

    Returns:
        A DriftReport summarizing the comparison and any detected drift.
    """
    if baseline.persona_id != current.persona_id:
        logger.warning(
            "Comparing fingerprints from different personas: %s vs %s",
            baseline.persona_id,
            current.persona_id,
        )

    # Compute metrics
    score_dissim = chi_squared_dissimilarity(baseline.score_distribution, current.score_distribution)
    dim_dissim = chi_squared_dissimilarity(baseline.dimension_dominance, current.dimension_dominance)

    vec_a = baseline.to_vector()
    vec_b = current.to_vector()
    vec_dist = _euclidean_distance(vec_a, vec_b)

    entropy_delta = current.entropy - baseline.entropy
    concentration_delta = current.concentration_ratio - baseline.concentration_ratio

    # Check thresholds
    reasons: list[str] = []

    if score_dissim > score_threshold:
        reasons.append(f"Score distribution shifted: chi2={score_dissim:.4f} > {score_threshold}")

    if dim_dissim > dimension_threshold:
        reasons.append(f"Dimension dominance shifted: chi2={dim_dissim:.4f} > {dimension_threshold}")

    if vec_dist > vector_threshold:
        reasons.append(f"Full vector distance: {vec_dist:.4f} > {vector_threshold}")

    if abs(entropy_delta) > entropy_threshold:
        direction = "increased" if entropy_delta > 0 else "decreased"
        reasons.append(f"Entropy {direction}: delta={entropy_delta:.4f}, |delta| > {entropy_threshold}")

    if abs(concentration_delta) > concentration_threshold:
        direction = "increased" if concentration_delta > 0 else "decreased"
        reasons.append(
            f"Concentration {direction}: delta={concentration_delta:.4f}, |delta| > {concentration_threshold}"
        )

    drift_detected = len(reasons) > 0

    # Severity classification
    if not drift_detected:
        severity = "none"
    elif len(reasons) >= 3:
        severity = "high"
    elif len(reasons) >= 2:
        severity = "medium"
    else:
        severity = "low"

    report = DriftReport(
        persona_id=current.persona_id,
        baseline_window=baseline.window_id,
        current_window=current.window_id,
        score_dissimilarity=score_dissim,
        dimension_dissimilarity=dim_dissim,
        vector_distance=vec_dist,
        entropy_delta=entropy_delta,
        concentration_delta=concentration_delta,
        drift_detected=drift_detected,
        drift_reasons=reasons,
        severity=severity,
    )

    if drift_detected:
        logger.warning(
            "Drift detected for persona=%s severity=%s reasons=%d",
            current.persona_id,
            severity,
            len(reasons),
        )
    else:
        logger.info(
            "No drift detected for persona=%s (score_chi2=%.4f dim_chi2=%.4f)",
            current.persona_id,
            score_dissim,
            dim_dissim,
        )

    return report
