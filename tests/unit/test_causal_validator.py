"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, causal, validation]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for R3 causal edge runtime validation.
"""

from __future__ import annotations

import pytest

from engine.causal.causal_validator import (
    _REJECTION_CONFIDENCE,
    _REJECTION_EDGE_TYPE,
    _REJECTION_TEMPORAL,
    CausalEdgeRuntimeValidator,
)
from engine.config.schema import CausalEdgeTypeSpec, CausalSpec


def _make_causal_spec(
    enforce_temporal: bool = True,
    edge_types: list[dict] | None = None,
) -> CausalSpec:
    """Create a CausalSpec for testing."""
    edges = edge_types or [
        {"edge_type": "RESULTED_IN", "confidence_threshold": 0.5},
        {"edge_type": "CAUSED_BY", "confidence_threshold": 0.7},
    ]
    return CausalSpec(
        enabled=True,
        causal_edges=[CausalEdgeTypeSpec(**e) for e in edges],
        enforce_temporal_precedence=enforce_temporal,
    )


@pytest.mark.unit
class TestCausalEdgeRuntimeValidator:
    """Test causal edge validation."""

    def test_valid_batch_passes(self) -> None:
        """Records with correct temporal precedence and confidence pass."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-02T00:00:00", "confidence": 0.8},
            {"source_ts": "2026-02-01T00:00:00", "target_ts": "2026-03-01T00:00:00", "confidence": 0.6},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 2
        assert len(rejected) == 0

    def test_temporal_precedence_violation(self) -> None:
        """Records where source_ts >= target_ts are rejected."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-03-01T00:00:00", "target_ts": "2026-01-01T00:00:00", "confidence": 0.8},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 0
        assert len(rejected) == 1
        assert rejected[0]["rejection_reason"] == _REJECTION_TEMPORAL

    def test_equal_timestamps_rejected(self) -> None:
        """Records with equal timestamps violate strict precedence."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-01T00:00:00", "confidence": 0.8},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 0
        assert len(rejected) == 1
        assert rejected[0]["rejection_reason"] == _REJECTION_TEMPORAL

    def test_confidence_below_threshold(self) -> None:
        """Records with confidence below edge type threshold are rejected."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-02T00:00:00", "confidence": 0.3},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 0
        assert len(rejected) == 1
        assert rejected[0]["rejection_reason"] == _REJECTION_CONFIDENCE

    def test_invalid_edge_type_all_rejected(self) -> None:
        """All records rejected when edge_type is not declared in spec."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-02T00:00:00", "confidence": 0.8},
        ]

        valid, rejected = validator.validate_batch(batch, "UNKNOWN_EDGE")

        assert len(valid) == 0
        assert len(rejected) == 1
        assert rejected[0]["rejection_reason"] == _REJECTION_EDGE_TYPE

    def test_none_timestamps_pass_lenient(self) -> None:
        """Records with None timestamps pass temporal check (lenient mode)."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": None, "target_ts": "2026-01-02T00:00:00", "confidence": 0.8},
            {"source_ts": "2026-01-01T00:00:00", "target_ts": None, "confidence": 0.6},
            {"source_ts": None, "target_ts": None, "confidence": 0.9},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 3
        assert len(rejected) == 0

    def test_temporal_precedence_disabled(self) -> None:
        """Temporal check skipped when enforce_temporal_precedence=False."""
        spec = _make_causal_spec(enforce_temporal=False)
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-03-01T00:00:00", "target_ts": "2026-01-01T00:00:00", "confidence": 0.8},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 1
        assert len(rejected) == 0

    def test_mixed_batch_partial_rejection(self) -> None:
        """Batch with mix of valid and invalid records is correctly split."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-02T00:00:00", "confidence": 0.8},
            {"source_ts": "2026-03-01T00:00:00", "target_ts": "2026-01-01T00:00:00", "confidence": 0.8},
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-02T00:00:00", "confidence": 0.2},
        ]

        valid, rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 1
        assert len(rejected) == 2

    def test_different_edge_type_thresholds(self) -> None:
        """Different edge types use their own confidence thresholds."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "2026-01-01T00:00:00", "target_ts": "2026-01-02T00:00:00", "confidence": 0.6},
        ]

        # RESULTED_IN threshold = 0.5, should pass
        valid1, _rejected1 = validator.validate_batch(batch, "RESULTED_IN")
        assert len(valid1) == 1

        # CAUSED_BY threshold = 0.7, should fail
        valid2, rejected2 = validator.validate_batch(batch, "CAUSED_BY")
        assert len(valid2) == 0
        assert rejected2[0]["rejection_reason"] == _REJECTION_CONFIDENCE

    def test_empty_batch(self) -> None:
        """Empty batch returns empty results."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        valid, rejected = validator.validate_batch([], "RESULTED_IN")

        assert len(valid) == 0
        assert len(rejected) == 0

    def test_invalid_timestamp_format_passes(self) -> None:
        """Invalid timestamp format is treated leniently (passes)."""
        spec = _make_causal_spec()
        validator = CausalEdgeRuntimeValidator(spec)

        batch = [
            {"source_ts": "not_a_date", "target_ts": "also_not_a_date", "confidence": 0.8},
        ]

        valid, _rejected = validator.validate_batch(batch, "RESULTED_IN")

        assert len(valid) == 1
