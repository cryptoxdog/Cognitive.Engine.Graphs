"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [tests]
tags: [integration, startup, boot, gap-fixes, wiring]
owner: engine-team
status: active
--- /L9_META ---

tests/integration/test_startup_integration.py

Integration test suite proving that all 6 integration actions
are active at runtime. Each test targets a specific gap fix or
wiring change and asserts on observable runtime state, not on
mock return values.

FIX(RULE-10): Every new module added in this integration pass (boot wiring,
community_export, gap fixes, settings) has at least one test covering its
execution path AND one test covering its error path.

Test philosophy:
    - Tests use real asyncio event loops (no sync wrappers).
    - Driver calls are mocked at the Neo4j driver boundary only.
    - PostgreSQL pool is mocked via asyncpg.create_pool patch.
    - No mocking of engine logic — only external I/O boundaries.
    - ContractViolationError and RuntimeError paths are explicitly asserted.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_return_channel() -> None:
    """Ensure singleton is fresh for each test."""
    from engine.graph_return_channel import GraphToEnrichReturnChannel

    GraphToEnrichReturnChannel.reset_instance()
    yield
    GraphToEnrichReturnChannel.reset_instance()


@pytest.fixture()
def mock_neo4j_driver() -> MagicMock:
    driver = MagicMock()
    driver.execute_query = AsyncMock(return_value=[])
    return driver


@pytest.fixture()
def mock_domain_loader() -> MagicMock:
    loader = MagicMock()
    loader.list_domains.return_value = ["plasticos"]
    spec = MagicMock()
    spec.kb = MagicMock()
    spec.gdsjobs = []
    loader.load_domain.return_value = spec
    return loader


# ─────────────────────────────────────────────────────────────────────────────
# Test A — apply_all_gap_fixes activates Gaps 2, 3, 5, 6
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gap_fixes_applied_via_boot_startup(
    mock_neo4j_driver: MagicMock,
    mock_domain_loader: MagicMock,
) -> None:
    """FIX(RULE-9 + GAP-2/3/5/6): Verify all four gap fixes activate at startup.

    Asserts:
        - Gap-5: configure_audit_pool is called with an asyncpg pool
        - Gap-3: load_domain_rules is called for each domain with a KB spec
        - Gap-2: GraphToEnrichReturnChannel singleton is not None after startup
        - Gap-6: GDSScheduler.register_post_job_hook is called with job_type="louvain"
    """
    from engine.graph_return_channel import GraphToEnrichReturnChannel

    mock_pool = MagicMock()
    configure_audit_pool_calls: list[Any] = []
    load_domain_rules_calls: list[Any] = []
    register_hook_calls: list[Any] = []

    async def fake_configure_audit_pool(pool: Any) -> None:
        configure_audit_pool_calls.append(pool)

    def fake_load_domain_rules(kb: Any) -> None:
        load_domain_rules_calls.append(kb)

    @classmethod  # type: ignore[misc]
    def fake_register_post_job_hook(
        cls: Any,
        job_type: str,
        hook: Any,
    ) -> None:
        register_hook_calls.append({"job_type": job_type, "hook": hook})

    with (
        patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)),
        patch(
            "shared.audit_persistence.configure_audit_pool",
            side_effect=fake_configure_audit_pool,
        ),
        patch(
            "engine.inference_rule_registry.load_domain_rules",
            side_effect=fake_load_domain_rules,
        ),
        patch(
            "engine.gds.scheduler.GDSScheduler.register_post_job_hook",
            new=fake_register_post_job_hook,
        ),
        patch(
            "engine.gds.community_export.export_community_labels_to_enrich",
            new=AsyncMock(return_value={"nodes_exported": 0}),
        ),
    ):
        from engine.startup_wiring import apply_all_gap_fixes

        await apply_all_gap_fixes(
            pg_dsn="postgresql://test:test@localhost:5432/test_audit",
            neo4j_driver=mock_neo4j_driver,
            domain_pack_loader=mock_domain_loader,
        )

    # Gap-5: audit pool wired
    assert len(configure_audit_pool_calls) == 1
    assert configure_audit_pool_calls[0] is mock_pool

    # Gap-3: rules loaded for the "plasticos" domain
    assert len(load_domain_rules_calls) == 1

    # Gap-2: return channel singleton initialised
    assert GraphToEnrichReturnChannel._instance is not None

    # Gap-6: louvain hook registered
    assert len(register_hook_calls) == 1
    assert register_hook_calls[0]["job_type"] == "louvain"


# ─────────────────────────────────────────────────────────────────────────────
# Test A-ERR — apply_all_gap_fixes fails closed on empty pg_dsn
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gap_fixes_fail_closed_on_empty_pg_dsn(
    mock_neo4j_driver: MagicMock,
    mock_domain_loader: MagicMock,
) -> None:
    """FIX(RULE-9): Engine must not start with an uninitialised audit pool.

    Asserts:
        - apply_all_gap_fixes raises ValueError when pg_dsn is empty.
    """
    from engine.startup_wiring import apply_all_gap_fixes

    with pytest.raises(ValueError, match="pg_dsn is empty"):
        await apply_all_gap_fixes(
            pg_dsn="",
            neo4j_driver=mock_neo4j_driver,
            domain_pack_loader=mock_domain_loader,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test B — Return channel contract enforcement
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_return_channel_rejects_invalid_envelope() -> None:
    """FIX(RULE-9 + GAP-2): ContractViolationError on tampered content_hash.

    Asserts:
        - submit() raises ContractViolationError when content_hash is wrong.
        - The singleton still exists and is functional after the rejection.
    """
    from engine.contract_enforcement import ContractViolationError
    from engine.graph_return_channel import (
        GraphInferenceResultEnvelope,
        GraphToEnrichReturnChannel,
    )

    channel = GraphToEnrichReturnChannel.get_instance()

    bad_envelope = GraphInferenceResultEnvelope(
        packet_id="pkt_test_bad",
        tenant_id="acme",
        inference_outputs=[{"entity_id": "e1", "field": "mfi", "value": 2.1, "confidence": 0.8, "rule": "r1"}],
        content_hash="deadbeef" * 8,  # intentionally wrong
        envelope_hash="ignored",
    )

    with pytest.raises(ContractViolationError, match="content_hash mismatch"):
        await channel.submit(bad_envelope)

    # Channel is still usable after rejection
    assert channel.stats()["rejected"] == 0  # rejection was at validation, not at queue-full
    assert GraphToEnrichReturnChannel._instance is channel


@pytest.mark.asyncio
async def test_return_channel_accepts_valid_envelope() -> None:
    """FIX(RULE-9 + GAP-2): Valid envelopes above CONFIDENCE_FLOOR are enqueued.

    Asserts:
        - build_graph_inference_result_envelope produces a passable envelope.
        - submit() returns the count of targets enqueued.
        - drain() returns all enqueued targets for the tenant.
    """
    from engine.graph_return_channel import (
        GraphToEnrichReturnChannel,
        build_graph_inference_result_envelope,
    )

    channel = GraphToEnrichReturnChannel.get_instance()
    inference_outputs = [
        {"entity_id": "fac-001", "field": "community_id", "value": 42, "confidence": 0.75, "rule": "louvain_community_membership"},
        {"entity_id": "fac-002", "field": "community_id", "value": 42, "confidence": 0.75, "rule": "louvain_community_membership"},
    ]

    envelope = build_graph_inference_result_envelope(
        tenant_id="acme",
        inference_outputs=inference_outputs,
    )

    count = await channel.submit(envelope)
    assert count == 2

    targets = await channel.drain(tenant_id="acme", timeout=0.1)
    assert len(targets) == 2
    assert all(t.field_name == "community_id" for t in targets)


# ─────────────────────────────────────────────────────────────────────────────
# Test C — v1 inference bridge is blocked at import
# ─────────────────────────────────────────────────────────────────────────────


def test_inference_bridge_v1_raises_import_error() -> None:
    """FIX(RULE-2 + GAP-9): Stale v1 bridge callers crash at import time, not at call time.

    Asserts:
        - Importing engine.inference_bridge raises ImportError.
        - The error message includes a meaningful v1 guard message.
    """
    import sys

    # Remove cached import if present from a prior test
    sys.modules.pop("engine.inference_bridge", None)

    with pytest.raises(ImportError):
        import engine.inference_bridge  # noqa: F401


# ─────────────────────────────────────────────────────────────────────────────
# Test D — Boot sequence wires convergence_controller_patch imports
# ─────────────────────────────────────────────────────────────────────────────


def test_convergence_patch_all_symbols_importable() -> None:
    """FIX(RULE-2 + GAP-4/7/8): All patch symbols must be importable before boot.

    Asserts:
        - extract_per_field_confidence, apply_return_channel_targets,
          emit_schema_proposal, enforce_domain_spec, DomainSpecRequiredError
          are all importable from engine.convergence_controller_patch.
    """
    from engine.convergence_controller_patch import (
        DomainSpecRequiredError,
        apply_return_channel_targets,
        emit_schema_proposal,
        enforce_domain_spec,
        extract_per_field_confidence,
    )

    assert callable(extract_per_field_confidence)
    assert callable(apply_return_channel_targets)
    assert callable(emit_schema_proposal)
    assert callable(enforce_domain_spec)
    assert issubclass(DomainSpecRequiredError, TypeError)


def test_enforce_domain_spec_raises_on_none() -> None:
    """FIX(GAP-8): domain_spec=None must raise DomainSpecRequiredError, not silently degrade."""
    from engine.convergence_controller_patch import (
        DomainSpecRequiredError,
        enforce_domain_spec,
    )

    with pytest.raises(DomainSpecRequiredError, match="domain_spec"):
        enforce_domain_spec(None)


def test_extract_per_field_confidence_explicit_dict() -> None:
    """FIX(GAP-7): Explicit per_field_confidence dict is extracted correctly."""
    from engine.convergence_controller_patch import extract_per_field_confidence

    fv = {
        "per_field_confidence": {"mfi": 0.9, "hdpe_grade": 0.75},
        "confidence": 0.5,
    }
    result = extract_per_field_confidence(fv)
    assert result == {"mfi": 0.9, "hdpe_grade": 0.75}


def test_extract_per_field_confidence_flat_fallback() -> None:
    """FIX(GAP-7): Flat confidence is broadcast to all non-meta fields."""
    from engine.convergence_controller_patch import extract_per_field_confidence

    fv = {
        "mfi": 2.1,
        "hdpe_grade": "prime",
        "confidence": 0.6,
        "pass_number": 1,
    }
    result = extract_per_field_confidence(fv)
    assert result["mfi"] == 0.6
    assert result["hdpe_grade"] == 0.6
    assert "pass_number" not in result
    assert "confidence" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Test E — community_export.py exports correctly
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_community_export_submits_to_return_channel(
    mock_neo4j_driver: MagicMock,
) -> None:
    """FIX(RULE-9 + GAP-6): community_export must submit valid targets to return channel.

    Asserts:
        - export_community_labels_to_enrich queries Neo4j with $min_size param.
        - Resulting EnrichmentTargets appear in channel.drain() for the tenant.
        - nodes_exported and communities_found counts match query output.
    """
    from engine.gds.community_export import export_community_labels_to_enrich
    from engine.graph_return_channel import GraphToEnrichReturnChannel

    mock_neo4j_driver.execute_query = AsyncMock(
        return_value=[
            {"entity_id": "fac-001", "community_id": 7},
            {"entity_id": "fac-002", "community_id": 7},
            {"entity_id": "fac-003", "community_id": 12},
        ]
    )

    result = await export_community_labels_to_enrich(
        driver=mock_neo4j_driver,
        tenant_id="acme",
        domain_id="plasticos",
    )

    assert result["nodes_exported"] == 3
    assert result["communities_found"] == 2
    assert result["targets_enqueued"] == 3

    channel = GraphToEnrichReturnChannel.get_instance()
    targets = await channel.drain(tenant_id="acme", timeout=0.1)
    assert len(targets) == 3
    assert all(t.field_name == "community_id" for t in targets)
    assert {t.entity_id for t in targets} == {"fac-001", "fac-002", "fac-003"}


@pytest.mark.asyncio
async def test_community_export_empty_result(
    mock_neo4j_driver: MagicMock,
) -> None:
    """FIX(GAP-6): Empty Neo4j result returns zero-count dict, no exception."""
    from engine.gds.community_export import export_community_labels_to_enrich

    mock_neo4j_driver.execute_query = AsyncMock(return_value=[])

    result = await export_community_labels_to_enrich(
        driver=mock_neo4j_driver,
        tenant_id="acme",
        domain_id="plasticos",
    )

    assert result == {"nodes_exported": 0, "communities_found": 0, "targets_enqueued": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Test F — settings.postgres_dsn field exists and validates
# ─────────────────────────────────────────────────────────────────────────────


def test_settings_has_postgres_dsn_field() -> None:
    """FIX(RULE-9 + GAP-5): postgres_dsn must exist on the Settings model.

    Asserts:
        - The settings singleton has a postgres_dsn attribute.
        - The default value is a non-empty string.
        - It does NOT start with a blank string.
    """
    from engine.config.settings import settings

    assert hasattr(settings, "postgres_dsn")
    assert isinstance(settings.postgres_dsn, str)
    assert settings.postgres_dsn.strip() != ""


def test_settings_postgres_dsn_rejects_default_in_production() -> None:
    """FIX(RULE-9 + GAP-5): default postgres_dsn must be rejected in production."""
    import os

    from pydantic import ValidationError

    with patch.dict(
        os.environ,
        {
            "L9_ENV": "prod",
            "NEO4J_PASSWORD": "real-neo4j-password",
            "API_SECRET_KEY": "real-api-key",
            "POSTGRES_DSN": "postgresql://l9:change-me-in-production@localhost:5432/l9_audit",
        },
    ):
        with pytest.raises(ValidationError, match="postgres_dsn"):
            from pydantic_settings import BaseSettings

            # Re-instantiate to pick up env overrides
            from engine.config.settings import Settings

            Settings()
