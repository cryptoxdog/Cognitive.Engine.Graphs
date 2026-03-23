"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, hgkr, schema]
owner: engine-team
status: active
--- /L9_META ---

Tests for HGKR-inspired schema extensions.

Validates that all new fields added to GDSJobSpec, ScoringSpec,
and ScoringDimensionSpec are backward compatible (have defaults)
and enforce the constraints identified in the HGKR paper.

Reference:
    Liu et al., "Iterative heterogeneous graph learning for knowledge
    graph-based recommendation", Scientific Reports (2023) 13:6987.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from engine.config.schema import (
    AggregationStrategy,
    ComputationType,
    GDSJobScheduleSpec,
    GDSJobSpec,
    GDSProjectionSpec,
    ScoringDimensionSpec,
    ScoringSource,
    ScoringSpec,
)


def _minimal_gds_job(**overrides: object) -> dict:
    """Return minimal valid raw dict for GDSJobSpec."""
    base = {
        "name": "test_job",
        "algorithm": "louvain",
        "schedule": {"type": "cron", "cron": "0 2 * * *"},
        "projection": {"nodelabels": ["Facility"], "edgetypes": ["SUPPLIES_TO"]},
    }
    base.update(overrides)
    return base


# ============================================================
# GDSJobSpec Extension Tests
# ============================================================


@pytest.mark.unit
class TestGDSJobSpecExtensions:
    """Validate HGKR-inspired GDS schema extensions."""

    def test_depends_on_default_empty(self) -> None:
        """New depends_on field defaults to empty list.

        Backward compatibility: existing domain specs without depends_on
        continue to parse and produce wave-0 (parallel) execution.
        """
        spec = GDSJobSpec(**_minimal_gds_job())
        assert spec.depends_on == []

    def test_depends_on_custom(self) -> None:
        """depends_on accepts a list of algorithm names."""
        spec = GDSJobSpec(**_minimal_gds_job(depends_on=["louvain", "geoproximity"]))
        assert spec.depends_on == ["louvain", "geoproximity"]

    def test_propagation_depth_default_2(self) -> None:
        """HGKR paper ablation (Table 4): L=2 is optimal.

        L=1 underfits (insufficient neighborhood information).
        L=3+ overfits (too much noise from distant neighbors).
        Default must be 2.
        """
        spec = GDSJobSpec(**_minimal_gds_job())
        assert spec.propagation_depth == 2

    def test_propagation_depth_lower_bound(self) -> None:
        """Depth < 1 is rejected by Pydantic ge=1 constraint."""
        with pytest.raises(PydanticValidationError):
            GDSJobSpec(**_minimal_gds_job(propagation_depth=0))

    def test_propagation_depth_upper_bound(self) -> None:
        """Depth > 5 is rejected by Pydantic le=5 constraint."""
        with pytest.raises(PydanticValidationError):
            GDSJobSpec(**_minimal_gds_job(propagation_depth=6))

    def test_propagation_depth_valid_range(self) -> None:
        """Depths 1 through 5 are all accepted."""
        for depth in range(1, 6):
            spec = GDSJobSpec(**_minimal_gds_job(propagation_depth=depth))
            assert spec.propagation_depth == depth

    def test_per_relation_params_default_empty(self) -> None:
        """No per-relation params by default (uniform algorithm params)."""
        spec = GDSJobSpec(**_minimal_gds_job())
        assert spec.per_relation_params == {}

    def test_per_relation_params_custom(self) -> None:
        """Per-relation params override global algorithm settings."""
        params = {
            "SUPPLIES_TO": {"resolution": 1.0},
            "COMPETES_WITH": {"resolution": 0.5},
        }
        spec = GDSJobSpec(**_minimal_gds_job(per_relation_params=params))
        assert spec.per_relation_params["SUPPLIES_TO"]["resolution"] == 1.0
        assert spec.per_relation_params["COMPETES_WITH"]["resolution"] == 0.5

    def test_aggregation_strategy_default_auto(self) -> None:
        """Default aggregation is auto (auto-select based on edge category).

        HGKR uses mixed aggregators (GAT for item-tailed, GraphSAGE for others).
        AUTO lets the engine select the appropriate strategy at runtime.
        """
        spec = GDSJobSpec(**_minimal_gds_job())
        assert spec.aggregation_strategy == AggregationStrategy.AUTO

    def test_aggregation_strategy_values(self) -> None:
        """All strategy values from HGKR mapping are present."""
        assert AggregationStrategy.MEAN == "mean"
        assert AggregationStrategy.ATTENTION_WEIGHTED == "attention_weighted"
        assert AggregationStrategy.MAX_POOL == "max"
        assert AggregationStrategy.SAMPLE_AGGREGATE == "sample_aggregate"

    def test_aggregation_strategy_custom(self) -> None:
        """Custom aggregation strategy is accepted."""
        spec = GDSJobSpec(**_minimal_gds_job(aggregation_strategy="attention_weighted"))
        assert spec.aggregation_strategy == AggregationStrategy.ATTENTION_WEIGHTED

    def test_backward_compat_existing_fields_unchanged(self) -> None:
        """All existing GDSJobSpec fields still work without new fields."""
        spec = GDSJobSpec(
            name="louvain_daily",
            algorithm="louvain",
            schedule=GDSJobScheduleSpec(type="cron", cron="0 2 * * *"),
            projection=GDSProjectionSpec(nodelabels=["Facility"], edgetypes=["SUPPLIES_TO"]),
            writeproperty="community_id",
        )
        assert spec.name == "louvain_daily"
        assert spec.algorithm == "louvain"
        assert spec.writeproperty == "community_id"
        # New fields should have defaults
        assert spec.depends_on == []
        assert spec.propagation_depth == 2
        assert spec.aggregation_strategy == AggregationStrategy.AUTO
        assert spec.per_relation_params == {}


# ============================================================
# ScoringSpec Extension Tests
# ============================================================


@pytest.mark.unit
class TestScoringSpecExtensions:
    """Validate HGKR-inspired scoring schema extensions."""

    def test_preference_sample_size_default_28(self) -> None:
        """HGKR paper (Table 6): K=24-32 optimal range.

        Midpoint = 28 is the safest default.
        """
        spec = ScoringSpec(dimensions=[])
        assert spec.preference_sample_size == 28

    def test_preference_sample_size_int(self) -> None:
        """K can be an integer."""
        spec = ScoringSpec(dimensions=[], preference_sample_size=50)
        assert spec.preference_sample_size == 50

    def test_preference_sample_size_auto(self) -> None:
        """K can be 'auto' for adaptive sample size."""
        spec = ScoringSpec(dimensions=[], preference_sample_size="auto")
        assert spec.preference_sample_size == "auto"

    def test_preference_sample_size_default(self) -> None:
        """K defaults to 28."""
        spec = ScoringSpec(dimensions=[])
        assert spec.preference_sample_size == 28

    def test_edge_type_strategy_default_empty(self) -> None:
        """No per-edge computation overrides by default."""
        dim = ScoringDimensionSpec(
            name="test_dim",
            source=ScoringSource.CANDIDATEPROPERTY,
            computation=ComputationType.CANDIDATEPROPERTY,
            weightkey="w",
            defaultweight=1.0,
        )
        assert dim.edge_type_strategy == {}

    def test_edge_type_strategy_custom(self) -> None:
        """Per-edge computation type mapping works."""
        strategy = {
            "WORKS_AT": ComputationType.COMMUNITYMATCH,
            "COMPETES_WITH": ComputationType.INVERSELINEAR,
        }
        dim = ScoringDimensionSpec(
            name="test_dim",
            source=ScoringSource.CANDIDATEPROPERTY,
            computation=ComputationType.CANDIDATEPROPERTY,
            weightkey="w",
            defaultweight=1.0,
            edge_type_strategy=strategy,
        )
        assert dim.edge_type_strategy["WORKS_AT"] == ComputationType.COMMUNITYMATCH


# ============================================================
# New Computation Type Tests
# ============================================================


@pytest.mark.unit
class TestNewComputationTypes:
    """Validate new HGKR-inspired computation types are registered."""

    def test_preference_attention_type_exists(self) -> None:
        """preference_attention computation type is available."""
        assert ComputationType.PREFERENCEATTENTION == "preference_attention"

    def test_community_bridge_type_exists(self) -> None:
        """community_bridge computation type is available."""
        assert ComputationType.COMMUNITYBRIDGE == "community_bridge"

    def test_total_computation_types(self) -> None:
        """15 total computation types (13 existing + 2 new)."""
        all_types = list(ComputationType)
        assert len(all_types) == 15

    def test_new_types_in_enum(self) -> None:
        """New types are valid enum members."""
        pref_attn = ComputationType("preference_attention")
        assert pref_attn == ComputationType.PREFERENCEATTENTION

        comm_bridge = ComputationType("community_bridge")
        assert comm_bridge == ComputationType.COMMUNITYBRIDGE
