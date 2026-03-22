"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, validation, temporal-precedence]
owner: engine-team
status: active
--- /L9_META ---

Causal edge runtime validation.
Enforces temporal precedence and confidence thresholds at write time.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from engine.config.schema import CausalSpec, CausalSubgraphSpec

logger = logging.getLogger(__name__)

_REJECTION_TEMPORAL = "temporal_precedence_violated"
_REJECTION_CONFIDENCE = "below_confidence_threshold"
_REJECTION_EDGE_TYPE = "invalid_edge_type"


class CausalEdgeRuntimeValidator:
    """Validates causal edge constraints at write time.

    Three validations:
    1. Temporal precedence: source.timestamp < target.timestamp
    2. Confidence threshold: edge.confidence >= spec threshold
    3. Edge type validity: edge_type is declared in domain spec
    """

    def __init__(self, causal_spec: CausalSpec | CausalSubgraphSpec) -> None:
        self._causal_spec = causal_spec
        self._valid_types: dict[str, float] = {e.edge_type: e.confidence_threshold for e in causal_spec.causal_edges}

    def validate_batch(
        self,
        batch: list[dict[str, Any]],
        edge_type: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Validate a batch of edge records.

        Args:
            batch: List of edge records with source_ts, target_ts, confidence.
            edge_type: The causal edge type being created.

        Returns:
            Tuple of (valid_records, rejected_records).
            Rejected records include a 'rejection_reason' field.
        """
        valid: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        if edge_type not in self._valid_types:
            for record in batch:
                rejected.append({**record, "rejection_reason": _REJECTION_EDGE_TYPE})
            return valid, rejected

        confidence_threshold = self._valid_types[edge_type]

        for record in batch:
            rejection = self._validate_record(record, confidence_threshold)
            if rejection is not None:
                rejected.append({**record, "rejection_reason": rejection})
            else:
                valid.append(record)

        if rejected:
            logger.info(
                "Causal validation: %d valid, %d rejected (edge_type=%s)",
                len(valid),
                len(rejected),
                edge_type,
            )

        return valid, rejected

    def _validate_record(
        self,
        record: dict[str, Any],
        confidence_threshold: float,
    ) -> str | None:
        """Validate a single record. Returns rejection reason or None."""
        enforce_temporal = getattr(self._causal_spec, "enforce_temporal_precedence", False)
        if not enforce_temporal:
            edge_spec = next(
                (e for e in self._causal_spec.causal_edges if e.edge_type == record.get("edge_type")), None
            )
            enforce_temporal = (
                edge_spec.temporal_validation if edge_spec and hasattr(edge_spec, "temporal_validation") else False
            )
        if enforce_temporal:
            source_ts = record.get("source_ts")
            target_ts = record.get("target_ts")
            if not self._check_temporal_precedence(source_ts, target_ts):
                return _REJECTION_TEMPORAL

        confidence = record.get("confidence")
        if confidence is not None and confidence < confidence_threshold:
            return _REJECTION_CONFIDENCE

        return None

    @staticmethod
    def _check_temporal_precedence(
        source_ts: str | None,
        target_ts: str | None,
    ) -> bool:
        """Returns True if source timestamp strictly precedes target timestamp.

        If either timestamp is None, validation passes (lenient mode).
        """
        if source_ts is None or target_ts is None:
            return True
        try:
            src = datetime.fromisoformat(str(source_ts))
            tgt = datetime.fromisoformat(str(target_ts))
        except (ValueError, TypeError):
            return True
        return src < tgt
