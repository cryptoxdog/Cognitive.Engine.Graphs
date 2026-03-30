"""
Tests for the algorithmic upgrade PR:
  - engine/diagnostics/fingerprint.py
  - engine/diagnostics/dissimilarity.py
  - engine/packet/packet_store.py (unit-level, no DB)
  - engine/security/P2_9_llm_schemas.py (unit-level, no LLM)
  - chassis/audit.py (PostgresSink, LogSink)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Diagnostics: Fingerprint ─────────────────────────────────

from engine.diagnostics.fingerprint import (
    AlgorithmicFingerprint,
    compute_fingerprint,
    DEFAULT_BUCKET_LABELS,
)


class TestComputeFingerprint:
    """Tests for compute_fingerprint()."""

    def test_empty_candidates(self):
        fp = compute_fingerprint("persona_a", "w1", [])
        assert fp.sample_count == 0
        assert fp.entropy == 0.0
        assert fp.top_dimension == "none"
        assert all(v == 0.0 for v in fp.score_distribution.values())

    def test_single_candidate(self):
        candidates = [{"total_score": 0.8, "dimension_scores": {"geo": 0.9, "rev": 0.3}}]
        fp = compute_fingerprint("persona_a", "w1", candidates)
        assert fp.sample_count == 1
        assert fp.score_distribution["high"] == 1.0
        assert fp.top_dimension == "geo"
        assert fp.concentration_ratio == 1.0

    def test_uniform_distribution(self):
        """Four candidates, one in each bucket -> high entropy."""
        candidates = [
            {"total_score": 0.1, "dimension_scores": {"a": 0.1}},
            {"total_score": 0.3, "dimension_scores": {"b": 0.3}},
            {"total_score": 0.6, "dimension_scores": {"c": 0.6}},
            {"total_score": 0.9, "dimension_scores": {"d": 0.9}},
        ]
        fp = compute_fingerprint("persona_b", "w2", candidates)
        assert fp.sample_count == 4
        # Each bucket has 0.25 frequency -> entropy = 2.0
        assert abs(fp.entropy - 2.0) < 0.001
        assert fp.concentration_ratio == 0.25

    def test_concentrated_distribution(self):
        """All candidates in same bucket -> low entropy."""
        candidates = [
            {"total_score": 0.9, "dimension_scores": {"geo": 0.9}},
            {"total_score": 0.85, "dimension_scores": {"geo": 0.85}},
            {"total_score": 0.95, "dimension_scores": {"geo": 0.95}},
        ]
        fp = compute_fingerprint("persona_c", "w3", candidates)
        assert fp.sample_count == 3
        assert fp.entropy == 0.0  # All in one bucket
        assert fp.concentration_ratio == 1.0
        assert fp.top_dimension == "geo"

    def test_to_vector(self):
        fp = compute_fingerprint(
            "p1", "w1",
            [{"total_score": 0.5, "dimension_scores": {"a": 0.5, "b": 0.3}}],
        )
        vec = fp.to_vector()
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        # 4 bucket labels + N dimension freqs + entropy + concentration
        assert len(vec) >= len(DEFAULT_BUCKET_LABELS) + 2

    def test_missing_score_key(self):
        """Candidates without total_score default to 0.0."""
        candidates = [{"dimension_scores": {"a": 0.5}}]
        fp = compute_fingerprint("p1", "w1", candidates)
        assert fp.score_distribution["very_low"] == 1.0

    def test_missing_dimension_scores(self):
        """Candidates without dimension_scores still produce a fingerprint."""
        candidates = [{"total_score": 0.5}]
        fp = compute_fingerprint("p1", "w1", candidates)
        assert fp.top_dimension == "none"
        assert fp.dimension_dominance == {}

    def test_bucket_boundary_validation(self):
        with pytest.raises(ValueError, match="bucket_boundaries"):
            compute_fingerprint(
                "p1", "w1", [{"total_score": 0.5}],
                bucket_boundaries=(0.0, 1.0),
                bucket_labels=("low", "mid", "high"),
            )


# ── Diagnostics: Dissimilarity ───────────────────────────────

from engine.diagnostics.dissimilarity import (
    chi_squared_dissimilarity,
    detect_drift,
    DriftReport,
)


class TestChiSquaredDissimilarity:
    def test_identical_distributions(self):
        d = {"a": 0.5, "b": 0.5}
        assert chi_squared_dissimilarity(d, d) == 0.0

    def test_completely_different(self):
        a = {"a": 1.0, "b": 0.0}
        b = {"a": 0.0, "b": 1.0}
        result = chi_squared_dissimilarity(a, b)
        assert result > 0.0

    def test_empty_distributions(self):
        assert chi_squared_dissimilarity({}, {}) == 0.0

    def test_partial_overlap(self):
        a = {"x": 0.5, "y": 0.5}
        b = {"x": 0.5, "z": 0.5}
        result = chi_squared_dissimilarity(a, b)
        assert result > 0.0

    def test_symmetry(self):
        a = {"a": 0.3, "b": 0.7}
        b = {"a": 0.6, "b": 0.4}
        assert abs(chi_squared_dissimilarity(a, b) - chi_squared_dissimilarity(b, a)) < 1e-10


class TestDetectDrift:
    def _make_fp(self, persona_id: str, window_id: str, score_dist: dict, dim_dom: dict, entropy: float, concentration: float):
        return AlgorithmicFingerprint(
            persona_id=persona_id,
            window_id=window_id,
            sample_count=100,
            score_distribution=score_dist,
            dimension_dominance=dim_dom,
            entropy=entropy,
            top_dimension=max(dim_dom, key=dim_dom.get) if dim_dom else "none",
            concentration_ratio=concentration,
        )

    def test_no_drift_identical(self):
        fp = self._make_fp("p1", "w1", {"low": 0.5, "high": 0.5}, {"geo": 0.6, "rev": 0.4}, 1.0, 0.5)
        report = detect_drift(fp, fp)
        assert not report.drift_detected
        assert report.severity == "none"
        assert report.drift_reasons == []

    def test_drift_score_shift(self):
        baseline = self._make_fp("p1", "w1", {"low": 0.8, "high": 0.2}, {"geo": 0.5}, 0.7, 0.8)
        current = self._make_fp("p1", "w2", {"low": 0.2, "high": 0.8}, {"geo": 0.5}, 0.7, 0.8)
        report = detect_drift(baseline, current, score_threshold=0.1)
        assert report.drift_detected
        assert any("Score distribution" in r for r in report.drift_reasons)

    def test_drift_entropy_change(self):
        baseline = self._make_fp("p1", "w1", {"low": 0.5, "high": 0.5}, {"geo": 0.5}, 0.5, 0.5)
        current = self._make_fp("p1", "w2", {"low": 0.5, "high": 0.5}, {"geo": 0.5}, 1.5, 0.5)
        report = detect_drift(baseline, current, entropy_threshold=0.3)
        assert report.drift_detected
        assert any("Entropy" in r for r in report.drift_reasons)

    def test_high_severity_multiple_reasons(self):
        baseline = self._make_fp("p1", "w1", {"low": 0.9, "high": 0.1}, {"geo": 0.9}, 0.3, 0.9)
        current = self._make_fp("p1", "w2", {"low": 0.1, "high": 0.9}, {"rev": 0.9}, 1.5, 0.1)
        report = detect_drift(baseline, current)
        assert report.drift_detected
        assert report.severity == "high"
        assert len(report.drift_reasons) >= 3

    def test_to_dict(self):
        baseline = self._make_fp("p1", "w1", {"low": 0.5}, {"geo": 0.5}, 1.0, 0.5)
        report = detect_drift(baseline, baseline)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "persona_id" in d
        assert "drift_detected" in d


# ── PacketStore (unit-level, no DB) ──────────────────────────

from engine.packet.packet_store import PacketStore, _extract_packet_row


class TestPacketStoreDisabled:
    """Test PacketStore behavior when PACKET_STORE_ENABLED=false (default)."""

    def test_persist_is_noop_when_disabled(self):
        store = PacketStore()
        # Should not raise, just log debug
        asyncio.get_event_loop().run_until_complete(
            store.persist(MagicMock(), MagicMock())
        )


# ── LLM Client (unit-level, no LLM) ─────────────────────────

from engine.security.P2_9_llm_schemas import (
    ValidatedLLMClient,
    CypherQueryOutput,
    validate_llm_json,
)


class TestValidateLlmJson:
    def test_valid_json(self):
        raw = json.dumps({
            "cypher_query": "MATCH (n) RETURN n LIMIT 10",
            "parameters": {},
            "explanation": "Returns first 10 nodes",
            "confidence": 0.9,
        })
        result = validate_llm_json(raw, CypherQueryOutput)
        assert isinstance(result, CypherQueryOutput)
        assert result.confidence == 0.9

    def test_invalid_json(self):
        with pytest.raises(Exception):
            validate_llm_json("not json", CypherQueryOutput)

    def test_destructive_cypher_rejected(self):
        raw = json.dumps({
            "cypher_query": "MATCH (n) DELETE n",
            "parameters": {},
            "explanation": "Delete all",
            "confidence": 0.5,
        })
        with pytest.raises(Exception):
            validate_llm_json(raw, CypherQueryOutput)


class TestValidatedLLMClientNoProvider:
    """Test that the client raises FeatureNotEnabled when no API key is set."""

    def test_call_without_api_key_raises(self):
        # Ensure no API key is set for this test
        env_backup = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from engine.security.P2_9_llm_schemas import _LLMBackend
            backend = _LLMBackend()
            backend._client = None  # Force re-init
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                backend._ensure_client("gpt-4-turbo")
        finally:
            if env_backup:
                os.environ["OPENAI_API_KEY"] = env_backup

    def test_generate_cypher_unsupported_language(self):
        client = ValidatedLLMClient()
        with pytest.raises(ValueError, match="Unsupported language"):
            client.generate_code("hello", language="brainfuck")


# ── Audit Sinks ──────────────────────────────────────────────

from chassis.audit import (
    AuditAction,
    AuditEntry,
    AuditLogger,
    AuditSeverity,
    LogSink,
    PostgresSink,
)


class TestLogSink:
    def test_write_batch(self):
        sink = LogSink()
        entries = [
            AuditEntry(
                action=AuditAction.ACCESS,
                actor="test_user",
                tenant="test_tenant",
            ),
            AuditEntry(
                action=AuditAction.MUTATION,
                actor="test_user",
                tenant="test_tenant",
            ),
        ]
        count = asyncio.get_event_loop().run_until_complete(sink.write_batch(entries))
        assert count == 2

    def test_write_empty_batch(self):
        sink = LogSink()
        count = asyncio.get_event_loop().run_until_complete(sink.write_batch([]))
        assert count == 0


class TestPostgresSink:
    def test_write_batch_calls_executemany(self):
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        sink = PostgresSink(mock_pool)
        entries = [
            AuditEntry(
                action=AuditAction.ACCESS,
                actor="test_user",
                tenant="test_tenant",
            ),
        ]
        count = asyncio.get_event_loop().run_until_complete(sink.write_batch(entries))
        assert count == 1
        mock_conn.executemany.assert_called_once()

    def test_write_empty_batch_skips_db(self):
        mock_pool = MagicMock()
        sink = PostgresSink(mock_pool)
        count = asyncio.get_event_loop().run_until_complete(sink.write_batch([]))
        assert count == 0
        mock_pool.acquire.assert_not_called()


class TestAuditLoggerWithSink:
    def test_flush_to_log_sink(self):
        sink = LogSink()
        audit_logger = AuditLogger(sinks=[sink])
        audit_logger.log(AuditAction.ACCESS, actor="user1", tenant="t1")
        audit_logger.log(AuditAction.MUTATION, actor="user2", tenant="t2")
        assert audit_logger.buffer_count == 2
        count = asyncio.get_event_loop().run_until_complete(audit_logger.flush())
        assert count == 2
        assert audit_logger.buffer_count == 0
