"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [scoring, confidence, ensemble, wave2]
owner: engine-team
status: active
--- /L9_META ---

Ensemble confidence bounds checking.

Detects scoring anomalies:
- Monoculture: a single dimension contributes > threshold of total score
- Ensemble divergence: GDS vs KGE scores differ > threshold (Wave 6 stub)

seL4 analog: state relation R holds across transitions — the confidence
check verifies scoring systems maintain a consistent ranking relation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel value for confidence flags
FLAG_MONOCULTURE = "monoculture"
FLAG_ENSEMBLE_DIVERGENCE = "ensemble_divergence"
FLAG_LOW_DIMENSIONAL_AGREEMENT = "low_dimensional_agreement"  # S2-07


class ConfidenceChecker:
    """Check confidence bounds on scoring results.

    In Wave 2 (GDS-only mode), the checker detects monoculture — where
    a single scoring dimension dominates the total score. When KGE is
    enabled in Wave 6, it will also detect pairwise disagreement.
    """

    def __init__(self, monoculture_threshold: float = 0.70, ensemble_max_divergence: float = 0.30) -> None:
        self.monoculture_threshold = monoculture_threshold
        self.ensemble_max_divergence = ensemble_max_divergence

    def check_monoculture(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flag candidates where one dimension contributes > threshold of total score.

        Each candidate dict must have a 'dimension_scores' key mapping
        dimension names to their score contributions.

        Args:
            candidates: List of candidate dicts with 'dimension_scores'.

        Returns:
            List of flag dicts for candidates that triggered monoculture.
            Each dict: {candidate_index, dominant_dimension, contribution, flag}.
        """
        flags: list[dict[str, Any]] = []
        for idx, candidate in enumerate(candidates):
            dim_scores = candidate.get("dimension_scores", {})
            if not isinstance(dim_scores, dict) or not dim_scores:
                continue

            total = sum(abs(v) for v in dim_scores.values() if isinstance(v, (int, float)))
            if total <= 0:
                continue

            for dim, score in dim_scores.items():
                if not isinstance(score, (int, float)):
                    continue
                contribution = abs(score) / total
                if contribution > self.monoculture_threshold:
                    flags.append(
                        {
                            "candidate_index": idx,
                            "dominant_dimension": dim,
                            "contribution": round(contribution, 4),
                            "flag": FLAG_MONOCULTURE,
                        }
                    )
                    break  # one flag per candidate

        return flags

    def check_ensemble_divergence(
        self,
        gds_scores: list[float],
        kge_scores: list[float],
    ) -> list[dict[str, Any]]:
        """Detect pairwise disagreement between GDS and KGE scores.

        Stub for Wave 6 — KGE is not yet active. When enabled, flags
        candidates where |gds_score - kge_score| > ensemble_max_divergence.

        Args:
            gds_scores: GDS-derived scores per candidate.
            kge_scores: KGE-derived scores per candidate.

        Returns:
            List of flag dicts for candidates that triggered divergence.
        """
        flags: list[dict[str, Any]] = []
        for idx, (gds, kge) in enumerate(zip(gds_scores, kge_scores, strict=False)):
            if not isinstance(gds, (int, float)) or not isinstance(kge, (int, float)):
                continue  # type: ignore[unreachable]
            divergence = abs(gds - kge)
            if divergence > self.ensemble_max_divergence:
                flags.append(
                    {
                        "candidate_index": idx,
                        "gds_score": round(gds, 6),
                        "kge_score": round(kge, 6),
                        "divergence": round(divergence, 6),
                        "flag": FLAG_ENSEMBLE_DIVERGENCE,
                    }
                )

        return flags

    def check_dimensional_agreement(
        self,
        candidates: list[dict[str, Any]],
        agreement_threshold: float = 0.4,
    ) -> list[dict[str, Any]]:
        """S2-07: Flag candidates with low cross-dimensional agreement.

        Wires CrossDimensionalEnsemble confidence (1 - 2*std_dev) into the
        confidence checking pipeline. When confidence is below threshold,
        the candidate's dimensions are in significant disagreement.

        HGKR context: L=2 iterative propagation is designed to resolve
        dimensional disagreement. Low agreement after fusion indicates
        the dimensions are measuring fundamentally different signals.

        Args:
            candidates: List of candidate dicts, optionally with
                        'cross_dimensional_confidence' key.
            agreement_threshold: Minimum confidence to avoid flagging.

        Returns:
            List of flag dicts for candidates that triggered low agreement.
        """
        flags: list[dict[str, Any]] = []
        for idx, candidate in enumerate(candidates):
            # Check for pre-computed cross-dimensional confidence
            cd_conf = candidate.get("cross_dimensional_confidence")
            if cd_conf is not None and isinstance(cd_conf, (int, float)):
                if cd_conf < agreement_threshold:
                    flags.append(
                        {
                            "candidate_index": idx,
                            "confidence": round(cd_conf, 4),
                            "threshold": agreement_threshold,
                            "flag": FLAG_LOW_DIMENSIONAL_AGREEMENT,
                        }
                    )
                continue

            # Fallback: compute agreement from dimension_scores if available
            dim_scores = candidate.get("dimension_scores", {})
            if not isinstance(dim_scores, dict) or len(dim_scores) < 2:
                continue

            values = [v for v in dim_scores.values() if isinstance(v, (int, float))]
            if len(values) < 2:
                continue

            mean_val = sum(values) / len(values)
            std_dev = (sum((v - mean_val) ** 2 for v in values) / len(values)) ** 0.5
            agreement = max(0.0, 1.0 - 2.0 * std_dev)

            if agreement < agreement_threshold:
                flags.append(
                    {
                        "candidate_index": idx,
                        "confidence": round(agreement, 4),
                        "threshold": agreement_threshold,
                        "flag": FLAG_LOW_DIMENSIONAL_AGREEMENT,
                    }
                )

        return flags

    def annotate_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run monoculture + dimensional agreement checks and annotate candidates.

        Mutates candidates in-place by adding 'confidence_flag' key where
        monoculture or low dimensional agreement is detected.

        Args:
            candidates: List of candidate result dicts.

        Returns:
            The same list, with flags added where applicable.
        """
        mono_flags = self.check_monoculture(candidates)
        flag_map: dict[int, dict[str, Any]] = {f["candidate_index"]: f for f in mono_flags}

        # S2-07: Also check dimensional agreement
        agreement_flags = self.check_dimensional_agreement(candidates)
        agreement_map: dict[int, dict[str, Any]] = {
            f["candidate_index"]: f for f in agreement_flags
        }

        for idx, candidate in enumerate(candidates):
            flags_list: list[str] = []
            detail: dict[str, Any] = {}

            if idx in flag_map:
                flags_list.append(flag_map[idx]["flag"])
                detail["dominant_dimension"] = flag_map[idx]["dominant_dimension"]
                detail["contribution"] = flag_map[idx]["contribution"]

            if idx in agreement_map:
                flags_list.append(agreement_map[idx]["flag"])
                detail["dimensional_agreement"] = agreement_map[idx]["confidence"]

            if flags_list:
                candidate["confidence_flag"] = flags_list[0] if len(flags_list) == 1 else flags_list
                candidate["confidence_detail"] = detail

        return candidates
