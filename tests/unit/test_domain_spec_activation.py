"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, config, domain-spec, activation]
owner: engine-team
status: active
--- /L9_META ---

Tests for plasticos domain spec with all feature flags enabled.

Covers:
- Spec loads without Pydantic validation errors
- Feedback loop enabled with signal weights
- Causal subgraph enabled with causal edges
- Semantic registry enabled
- Counterfactual enabled
- New fields (confidence_dampening, penalty_threshold, drift_threshold)
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from engine.config.schema import DomainSpec
from engine.config.settings import Settings

_SETTINGS_TARGET = "engine.config.settings.settings"


def _make_settings(**overrides: Any) -> Settings:
    """Create a Settings instance with overrides (avoids .env side effects)."""
    defaults = {
        "neo4j_password": "test-pw",
        "api_secret_key": "test-key",
        "l9_env": "dev",
        "domain_strict_validation": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _relax_strict_validation() -> Generator[None, None, None]:
    """Disable strict validation — plasticos spec has pre-existing weight sum >1.0."""
    s = _make_settings(domain_strict_validation=False)
    with patch(_SETTINGS_TARGET, s):
        yield


@pytest.fixture
def plasticos_spec_data() -> dict:
    """Load the plasticos domain spec YAML."""
    spec_path = Path(__file__).parent.parent.parent / "domains" / "plasticos_domain_spec.yaml"
    with spec_path.open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def plasticos_spec(plasticos_spec_data: dict) -> DomainSpec:
    """Parse the plasticos domain spec into a DomainSpec model."""
    return DomainSpec(**plasticos_spec_data)


class TestPlasticosSpecActivation:
    """Tests that plasticos spec loads with all features enabled."""

    def test_spec_loads_without_errors(self, plasticos_spec: DomainSpec) -> None:
        assert plasticos_spec.domain.id == "plasticos"

    def test_feedback_loop_enabled(self, plasticos_spec: DomainSpec) -> None:
        fl = plasticos_spec.feedbackloop
        assert fl.enabled is True
        assert fl.signal_weights.enabled is True
        assert fl.drift_threshold == 0.15
        assert fl.drift_window_days == 30

    def test_signal_weight_new_fields(self, plasticos_spec: DomainSpec) -> None:
        sw = plasticos_spec.feedbackloop.signal_weights
        assert sw.confidence_dampening is True
        assert sw.penalty_threshold == 0.5
        assert sw.penalty_factor == 0.3

    def test_causal_enabled(self, plasticos_spec: DomainSpec) -> None:
        causal = plasticos_spec.causal
        assert causal.enabled is True
        assert causal.attribution_enabled is True
        assert causal.counterfactual_enabled is True
        assert len(causal.causal_edges) == 2

    def test_causal_edge_types(self, plasticos_spec: DomainSpec) -> None:
        edge_types = {e.edge_type for e in plasticos_spec.causal.causal_edges}
        assert "RESULTED_IN" in edge_types
        assert "CAUSED_BY" in edge_types

    def test_semantic_registry_enabled(self, plasticos_spec: DomainSpec) -> None:
        sr = plasticos_spec.semantic_registry
        assert sr.enabled is True
        assert "Facility" in sr.entity_labels
        assert sr.similarity_threshold == 0.85
        assert sr.max_candidates == 20

    def test_counterfactual_enabled(self, plasticos_spec: DomainSpec) -> None:
        cf = plasticos_spec.counterfactual
        assert cf.enabled is True
        assert cf.max_scenarios_per_outcome == 3
        assert cf.min_confidence == 0.3

    def test_propagation_config(self, plasticos_spec: DomainSpec) -> None:
        fl = plasticos_spec.feedbackloop
        assert fl.propagation_boost_factor == 1.15
        assert fl.propagation_similarity_threshold == 0.4
        assert fl.outcome_edge_type == "RESULTED_IN"
        assert fl.outcome_node_label == "TransactionOutcome"
