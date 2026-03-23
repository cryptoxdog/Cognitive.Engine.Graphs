"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [scoring, calibration, forward-simulation, wave2]
owner: engine-team
status: active
--- /L9_META ---

Score calibration framework — seL4-inspired forward simulation.

Verifies that the concrete scoring implementation satisfies the abstract
calibration spec defined by the domain author. Reports pass/fail per
calibration pair, NDCG ranking quality, Kendall-tau correlation, and
distribution drift (simplified KS test).

This is a MANUAL verification tool — it does NOT auto-adjust weights.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from typing import Any

from engine.config.schema import CalibrationPair, DomainSpec

logger = logging.getLogger(__name__)


def _dcg(relevances: list[float]) -> float:
    """Compute Discounted Cumulative Gain for a relevance list."""
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


@dataclass
class CalibrationResult:
    """Result for a single calibration pair check."""

    pair_label: str
    node_a: str
    node_b: str
    actual_score: float | None
    expected_min: float
    expected_max: float
    passed: bool
    diff: float


@dataclass
class ForwardSimReport:
    """Result of forward simulation: abstract vs concrete ranking comparison."""

    ndcg: float
    kendall_tau: float
    diverged: bool
    misranked_pairs: list[tuple[str, str]]


@dataclass
class DriftReport:
    """Result of score drift detection between baseline and current scores."""

    drift_detected: bool
    delta_mean: float
    ks_statistic: float
    historical_mean: float
    current_mean: float


@dataclass
class CalibrationReport:
    """Full calibration report for a domain."""

    domain_id: str
    total_pairs: int
    passed: int
    failed: int
    results: list[CalibrationResult]
    overall_pass: bool


DRIFT_KS_THRESHOLD = 0.2


class ScoreCalibrator:
    """Calibrates scoring against domain-spec calibration pairs.

    seL4 analog: forward simulation — the abstract spec defines expected
    score ranges; this class verifies the implementation satisfies them.
    """

    def __init__(self, domain_spec: DomainSpec) -> None:
        self.domain_spec = domain_spec

    def run_calibration(
        self,
        calibration_pairs: list[CalibrationPair],
        actual_scores: dict[tuple[str, str], float],
    ) -> CalibrationReport:
        """Run calibration against actual scores.

        Args:
            calibration_pairs: Expected score ranges from domain spec.
            actual_scores: Map of (node_a, node_b) -> actual score from engine.

        Returns:
            CalibrationReport with pass/fail per pair and overall status.
        """
        results: list[CalibrationResult] = []
        for pair in calibration_pairs:
            key = (pair.node_a, pair.node_b)
            actual = actual_scores.get(key)
            if actual is not None:
                passed = pair.expected_score_min <= actual <= pair.expected_score_max
                diff = 0.0
                if actual < pair.expected_score_min:
                    diff = pair.expected_score_min - actual
                elif actual > pair.expected_score_max:
                    diff = actual - pair.expected_score_max
            else:
                passed = False
                diff = -1.0  # sentinel: score not available

            results.append(
                CalibrationResult(
                    pair_label=pair.label or f"{pair.node_a}->{pair.node_b}",
                    node_a=pair.node_a,
                    node_b=pair.node_b,
                    actual_score=actual,
                    expected_min=pair.expected_score_min,
                    expected_max=pair.expected_score_max,
                    passed=passed,
                    diff=round(diff, 6),
                )
            )

        passed_count = sum(1 for r in results if r.passed)
        domain_id = self.domain_spec.domain.id

        return CalibrationReport(
            domain_id=domain_id,
            total_pairs=len(results),
            passed=passed_count,
            failed=len(results) - passed_count,
            results=results,
            overall_pass=passed_count == len(results),
        )

    def forward_simulate(
        self,
        abstract_ranking: list[str],
        concrete_ranking: list[str],
    ) -> ForwardSimReport:
        """Compare abstract intent vs concrete scoring ranking.

        Computes NDCG and Kendall-tau to quantify ranking divergence.

        Args:
            abstract_ranking: Ideal ordering by domain author (most preferred first).
            concrete_ranking: Actual ordering produced by scoring engine.
        """
        if not abstract_ranking or not concrete_ranking:
            return ForwardSimReport(ndcg=0.0, kendall_tau=0.0, diverged=True, misranked_pairs=[])

        n = len(abstract_ranking)
        abstract_pos: dict[str, int] = {cid: i for i, cid in enumerate(abstract_ranking)}

        # NDCG: relevance based on position in abstract ranking
        relevances_actual = [float(n - abstract_pos[cid]) if cid in abstract_pos else 0.0 for cid in concrete_ranking]
        ideal_relevances = sorted(relevances_actual, reverse=True)
        idcg = _dcg(ideal_relevances)
        ndcg = min(1.0, _dcg(relevances_actual) / idcg) if idcg > 0 else 0.0

        # Kendall-tau on common elements
        common = [cid for cid in concrete_ranking if cid in abstract_pos]
        concordant = discordant = 0
        for i in range(len(common)):
            for j in range(i + 1, len(common)):
                if abstract_pos[common[i]] < abstract_pos[common[j]]:
                    concordant += 1
                elif abstract_pos[common[i]] > abstract_pos[common[j]]:
                    discordant += 1
        total_pairs = concordant + discordant
        tau = (concordant - discordant) / total_pairs if total_pairs > 0 else 0.0

        # Misranked pairs
        concrete_pos: dict[str, int] = {cid: i for i, cid in enumerate(concrete_ranking)}
        misranked: list[tuple[str, str]] = []
        for i, a in enumerate(abstract_ranking):
            for b in abstract_ranking[i + 1 :]:
                if a in concrete_pos and b in concrete_pos and concrete_pos[a] > concrete_pos[b]:
                    misranked.append((a, b))

        drift_threshold = 0.05
        return ForwardSimReport(
            ndcg=round(ndcg, 6),
            kendall_tau=round(tau, 6),
            diverged=ndcg < (1.0 - drift_threshold),
            misranked_pairs=misranked[:20],
        )

    def detect_score_drift(
        self,
        baseline_scores: list[float],
        current_scores: list[float],
    ) -> DriftReport:
        """Detect scoring distribution drift via simplified KS test.

        Args:
            baseline_scores: Historical final scores.
            current_scores: Current period final scores.
        """
        if not baseline_scores or not current_scores:
            return DriftReport(
                drift_detected=True,
                delta_mean=0.0,
                ks_statistic=1.0,
                historical_mean=0.0,
                current_mean=0.0,
            )

        hist_mean = statistics.mean(baseline_scores)
        curr_mean = statistics.mean(current_scores)
        delta_mean = curr_mean - hist_mean

        # Simplified KS statistic: max |CDF_h - CDF_c|
        all_points = sorted(set(baseline_scores + current_scores))
        n_h, n_c = len(baseline_scores), len(current_scores)
        hist_sorted = sorted(baseline_scores)
        curr_sorted = sorted(current_scores)

        ks_stat = 0.0
        for p in all_points:
            cdf_h = sum(1 for v in hist_sorted if v <= p) / n_h
            cdf_c = sum(1 for v in curr_sorted if v <= p) / n_c
            ks_stat = max(ks_stat, abs(cdf_h - cdf_c))

        drift_threshold = 0.05
        drift_detected = abs(delta_mean) > drift_threshold or ks_stat > DRIFT_KS_THRESHOLD

        return DriftReport(
            drift_detected=drift_detected,
            delta_mean=round(delta_mean, 6),
            ks_statistic=round(ks_stat, 6),
            historical_mean=round(hist_mean, 6),
            current_mean=round(curr_mean, 6),
        )

    def generate_calibration_report(self, domain_id: str) -> dict[str, Any]:
        """Generate a summary calibration report dict for a domain.

        Reads calibration pairs from the domain spec and returns a structured
        report suitable for admin API responses.
        """
        cal_spec = self.domain_spec.calibration
        if not cal_spec or not cal_spec.pairs:
            return {
                "domain_id": domain_id,
                "status": "no_calibration_spec",
                "total_pairs": 0,
                "message": "No calibration pairs defined in domain spec",
            }

        return {
            "domain_id": domain_id,
            "status": "calibration_spec_loaded",
            "total_pairs": len(cal_spec.pairs),
            "weight_set": cal_spec.weight_set,
            "pairs": [
                {
                    "label": p.label or f"{p.node_a}->{p.node_b}",
                    "node_a": p.node_a,
                    "node_b": p.node_b,
                    "expected_range": [p.expected_score_min, p.expected_score_max],
                }
                for p in cal_spec.pairs
            ],
            "message": "Calibration spec loaded. Run calibration_run to verify scores.",
        }
