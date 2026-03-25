"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [scoring, hgkr, calibration, density, auto-tune]
owner: engine-team
status: active
--- /L9_META ---

HGKR Pass 2 utility functions.

Implements second-order enhancements extracted from Liu et al. (2023)
"Iterative heterogeneous graph learning for knowledge graph-based recommendation"
(Scientific Reports 13:6987, DOI: 10.1038/s41598-023-33984-5).

Contains:
- S2-08: Auto-generation of calibration pairs from TransactionOutcome history
- S2-09: Score drift detection between GDS refresh cycles
- S2-10: EdgeCategory-driven GDS default configuration generator
- S2-13: Adaptive K-parameter computation from graph density
- S2-21: Sparsity-aware performance guidance / domain density report
- S2-23: Auto-tune admin subaction (automated aggregation strategy optimization)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.config.schema import (
    AggregationStrategy,
    CalibrationPair,
    DomainSpec,
    EdgeCategory,
    GDSJobSpec,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# S2-08: Auto-generate calibration pairs from TransactionOutcome history
# ══════════════════════════════════════════════════════════════════════


@dataclass
class GeneratedCalibrationPair:
    """A calibration pair auto-generated from outcome history."""

    node_a: str
    node_b: str
    expected_score_min: float
    expected_score_max: float
    label: str
    source_outcome: str  # "success" or "failure"


def generate_calibration_pairs(
    outcome_records: list[dict[str, Any]],
    *,
    positive_margin: float = 0.1,
    negative_ceiling: float = 0.5,
) -> list[CalibrationPair]:
    """Auto-generate CalibrationPairs from historical TransactionOutcome data.

    HGKR evaluation methodology: use ground truth labels (positive/negative)
    to validate the model. CEG has ground truth (TransactionOutcome) but
    no automated calibration generation — until now.

    For success outcomes: expected_score_min = actual_score - margin
    For failure outcomes: expected_score_max = negative_ceiling

    Args:
        outcome_records: List of outcome dicts with keys:
            match_id, candidate_id, outcome (success/failure), score (float).
        positive_margin: Score margin below actual for success pairs.
        negative_ceiling: Maximum expected score for failure pairs.

    Returns:
        List of CalibrationPair objects suitable for domain spec injection.
    """
    pairs: list[CalibrationPair] = []

    for record in outcome_records:
        outcome = record.get("outcome")
        score = record.get("score")
        match_id = record.get("match_id", "unknown")
        candidate_id = record.get("candidate_id", "unknown")

        if score is None or not isinstance(score, (int, float)):
            continue

        score = float(score)

        if outcome == "success":
            pairs.append(
                CalibrationPair(
                    node_a=match_id,
                    node_b=candidate_id,
                    expected_score_min=max(0.0, score - positive_margin),
                    expected_score_max=min(1.0, score + positive_margin),
                    label=f"auto_success_{match_id}_{candidate_id}",
                )
            )
        elif outcome == "failure":
            pairs.append(
                CalibrationPair(
                    node_a=match_id,
                    node_b=candidate_id,
                    expected_score_min=0.0,
                    expected_score_max=min(1.0, negative_ceiling),
                    label=f"auto_failure_{match_id}_{candidate_id}",
                )
            )

    logger.info("Generated %d calibration pairs from %d outcomes", len(pairs), len(outcome_records))
    return pairs


# ══════════════════════════════════════════════════════════════════════
# S2-09: Score drift detection between GDS refresh cycles
# ══════════════════════════════════════════════════════════════════════


@dataclass
class DriftCheckResult:
    """Result of score drift check after GDS refresh."""

    drift_detected: bool
    delta_mean: float
    pre_scores: list[float]
    post_scores: list[float]
    job_name: str
    threshold: float = 0.05

    @property
    def summary(self) -> str:
        direction = "increased" if self.delta_mean > 0 else "decreased"
        return f"Job '{self.job_name}': scores {direction} by {abs(self.delta_mean):.4f} (threshold={self.threshold})"


def check_score_drift(
    pre_scores: list[float],
    post_scores: list[float],
    job_name: str,
    threshold: float = 0.05,
) -> DriftCheckResult:
    """Detect score drift between pre- and post-GDS-refresh score samples.

    HGKR's ablation shows L=3+ causes overfitting — drift detection
    catches this in production by comparing score distributions before
    and after each GDS job.

    Args:
        pre_scores: Match scores sampled before GDS job execution.
        post_scores: Match scores sampled after GDS job execution.
        job_name: Name of the GDS job for logging.
        threshold: Maximum acceptable mean score change.

    Returns:
        DriftCheckResult with drift detection flag and metrics.
    """
    if not pre_scores or not post_scores:
        return DriftCheckResult(
            drift_detected=False,
            delta_mean=0.0,
            pre_scores=pre_scores,
            post_scores=post_scores,
            job_name=job_name,
            threshold=threshold,
        )

    pre_mean = sum(pre_scores) / len(pre_scores)
    post_mean = sum(post_scores) / len(post_scores)
    delta = post_mean - pre_mean

    drift_detected = abs(delta) > threshold

    if drift_detected:
        logger.warning(
            "Score drift detected after GDS job '%s': delta_mean=%.4f (threshold=%.4f)",
            job_name,
            delta,
            threshold,
        )

    return DriftCheckResult(
        drift_detected=drift_detected,
        delta_mean=round(delta, 6),
        pre_scores=pre_scores,
        post_scores=post_scores,
        job_name=job_name,
        threshold=threshold,
    )


# ══════════════════════════════════════════════════════════════════════
# S2-10: EdgeCategory-driven GDS auto-configuration
# ══════════════════════════════════════════════════════════════════════


def default_gds_config_for_category(category: EdgeCategory | str) -> dict[str, str]:
    """Return recommended GDS algorithm + aggregation strategy for an edge category.

    HGKR: each relation type maps to one bipartite graph with specific
    aggregation. CEG's EdgeCategory enum is a richer semantic taxonomy.
    This function maps EdgeCategory → recommended (algorithm, aggregation).

    Args:
        category: EdgeCategory enum value or string.

    Returns:
        Dict with 'algorithm' and 'aggregation' keys.
    """
    from engine.gds.scheduler import _EDGE_CATEGORY_DEFAULTS

    cat: str = category if isinstance(category, str) else category.value  # type: ignore[union-attr]
    return _EDGE_CATEGORY_DEFAULTS.get(
        cat,
        {"algorithm": "louvain", "aggregation": "mean"},
    )


def suggest_gds_jobs_for_domain(domain_spec: DomainSpec) -> list[dict[str, Any]]:
    """Generate recommended GDSJobSpec configurations based on domain edge types.

    Analyzes the domain's ontology edges, maps each to a recommended GDS
    configuration via EdgeCategory, and returns suggested job specs.

    Args:
        domain_spec: Complete domain specification.

    Returns:
        List of dicts suitable for GDSJobSpec construction.
    """
    suggestions: list[dict[str, Any]] = []
    seen_configs: set[tuple[str, str]] = set()

    for edge in domain_spec.ontology.edges:
        config = default_gds_config_for_category(edge.category)
        key = (config["algorithm"], edge.type)
        if key in seen_configs:
            continue
        seen_configs.add(key)

        suggestions.append(
            {
                "name": f"auto_{edge.type.lower()}_{config['algorithm']}",
                "algorithm": config["algorithm"],
                "aggregation_strategy": config["aggregation"],
                "edge_type": edge.type,
                "edge_category": edge.category.value,
                "source_node": edge.from_,
                "target_node": edge.to,
                "rationale": (
                    f"EdgeCategory '{edge.category.value}' → "
                    f"algorithm='{config['algorithm']}', "
                    f"aggregation='{config['aggregation']}'"
                ),
            }
        )

    return suggestions


# ══════════════════════════════════════════════════════════════════════
# S2-13: Adaptive K-parameter from graph density
# ══════════════════════════════════════════════════════════════════════


def compute_adaptive_sample_size(
    avg_edges_per_node: float,
    min_k: int = 16,
    max_k: int = 48,
) -> int:
    """Compute optimal preference_sample_size from graph density.

    HGKR Table 5: optimal K varies by dataset density:
    - K=24 for ml-latest (sparser, ~165 interactions/user)
    - K=32 for MOOCCube (denser, ~73 interactions/user)

    Formula: K = clamp(round(avg_edges_per_node * 1.5), min_k, max_k)

    Args:
        avg_edges_per_node: Average edge count per node in the graph.
        min_k: Minimum sample size (default 16).
        max_k: Maximum sample size (default 48).

    Returns:
        Computed K value clamped to [min_k, max_k].
    """
    raw_k = round(avg_edges_per_node * 1.5)
    return max(min_k, min(max_k, raw_k))


# ══════════════════════════════════════════════════════════════════════
# S2-21: Sparsity-aware performance guidance
# ══════════════════════════════════════════════════════════════════════


@dataclass
class DensityReport:
    """Domain graph density analysis and HGKR feature recommendations."""

    domain_id: str
    total_nodes: int = 0
    total_edges: int = 0
    avg_degree: float = 0.0
    edge_type_distribution: dict[str, int] = field(default_factory=dict)
    density_class: str = "unknown"  # "sparse", "moderate", "dense"
    recommended_sample_size: int = 28
    recommendations: list[str] = field(default_factory=list)


def generate_density_report(
    domain_id: str,
    total_nodes: int,
    total_edges: int,
    edge_type_counts: dict[str, int] | None = None,
) -> DensityReport:
    """Generate a density analysis report with HGKR feature recommendations.

    HGKR paper: benefits vary with data density.
    - Sparse graphs: +0.92% AUC improvement
    - Dense graphs: +2.21% AUC improvement

    Compares against HGKR benchmarks:
    - ml-latest: 610 users, 9742 items, 100K interactions → ~165/user
    - MOOCCube: denser, ~73 interactions/user

    Args:
        domain_id: Domain identifier.
        total_nodes: Total node count.
        total_edges: Total edge count.
        edge_type_counts: Optional per-edge-type counts.

    Returns:
        DensityReport with classification and recommendations.
    """
    avg_degree = total_edges / total_nodes if total_nodes > 0 else 0.0

    # Classify density against HGKR benchmarks
    if avg_degree < 5.0:
        density_class = "sparse"
    elif avg_degree < 20.0:
        density_class = "moderate"
    else:
        density_class = "dense"

    recommended_k = compute_adaptive_sample_size(avg_degree)
    recommendations: list[str] = []

    if density_class == "sparse":
        recommendations.extend(
            [
                f"Reduce preference_sample_size to {recommended_k} (graph is sparse).",
                "Enable cold_start_fallback=structural_similarity on preference dimensions.",
                "HGKR features yield moderate improvement (+0.9% AUC) on sparse graphs.",
                "Consider enabling null_strategy=inherit_prior to preserve partial signals.",
            ]
        )
    elif density_class == "moderate":
        recommendations.extend(
            [
                f"Recommended preference_sample_size: {recommended_k}.",
                "Enable preference_attention and community_bridge for best results.",
                "Consider stability_runs=3 on Louvain jobs for consistent community detection.",
            ]
        )
    else:
        recommendations.extend(
            [
                f"Set preference_sample_size to {recommended_k} (graph is dense).",
                "Enable all HGKR features — maximum benefit expected (+2.2% AUC).",
                "Enable soft_match=True on community dimensions for graduated scoring.",
                "Consider bilinear scoring aggregation for cross-dimensional interactions.",
            ]
        )

    return DensityReport(
        domain_id=domain_id,
        total_nodes=total_nodes,
        total_edges=total_edges,
        avg_degree=round(avg_degree, 2),
        edge_type_distribution=edge_type_counts or {},
        density_class=density_class,
        recommended_sample_size=recommended_k,
        recommendations=recommendations,
    )


# ══════════════════════════════════════════════════════════════════════
# S2-14: Aggregator ablation test harness
# ══════════════════════════════════════════════════════════════════════


@dataclass
class AblationResult:
    """Result of a single ablation configuration run."""

    config_name: str
    overrides: dict[str, Any]
    metrics: dict[str, float]  # e.g. {"auc": 0.85, "ndcg": 0.92}


def build_ablation_configs(
    base_gds_jobs: list[GDSJobSpec],
    strategies_to_test: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build ablation test configurations for aggregation strategy comparison.

    HGKR Table 3: HGKR (mixed) > HGKR_GAT > HGKR_SAGE > HGKR_GCN.
    This function generates the configuration matrix for systematic testing.

    Args:
        base_gds_jobs: Current GDS job specifications.
        strategies_to_test: List of AggregationStrategy values to test.
            Defaults to all available strategies.

    Returns:
        List of ablation config dicts with 'name', 'gds_overrides', 'description'.
    """
    if strategies_to_test is None:
        strategies_to_test = [s.value for s in AggregationStrategy if s != AggregationStrategy.AUTO]

    configs: list[dict[str, Any]] = []

    # Baseline: current configuration
    configs.append(
        {
            "name": "baseline",
            "gds_overrides": {},
            "description": "Current domain configuration (no overrides)",
        }
    )

    # Per-strategy uniform configurations (matching HGKR ablation Table 3)
    for strategy in strategies_to_test:
        overrides = {job.name: {"aggregation_strategy": strategy} for job in base_gds_jobs}
        configs.append(
            {
                "name": f"uniform_{strategy}",
                "gds_overrides": overrides,
                "description": f"All GDS jobs using {strategy} aggregation (HGKR ablation)",
            }
        )

    # Auto-resolved configuration
    configs.append(
        {
            "name": "auto_resolved",
            "gds_overrides": {job.name: {"aggregation_strategy": "auto"} for job in base_gds_jobs},
            "description": "All GDS jobs using auto-resolved aggregation (S2-03)",
        }
    )

    return configs


# ══════════════════════════════════════════════════════════════════════
# S2-23: Auto-tune admin subaction
# ══════════════════════════════════════════════════════════════════════


@dataclass
class AutoTuneResult:
    """Result of automated aggregation strategy optimization."""

    domain_id: str
    tested_configs: int
    best_config: str
    best_metrics: dict[str, float]
    all_results: list[AblationResult]
    recommended_overrides: dict[str, Any]


def select_best_ablation(
    results: list[AblationResult],
    primary_metric: str = "auc",
) -> AblationResult:
    """Select the best configuration from ablation results.

    Implements HGKR's stated future work: automatic matching of GNN
    to bipartite graph. Uses calibration set AUC as the primary metric.

    Args:
        results: List of AblationResult from each configuration run.
        primary_metric: Metric to optimize (default: AUC).

    Returns:
        The AblationResult with the highest primary_metric value.
    """
    if not results:
        raise ValueError("No ablation results to select from")

    return max(results, key=lambda r: r.metrics.get(primary_metric, 0.0))
