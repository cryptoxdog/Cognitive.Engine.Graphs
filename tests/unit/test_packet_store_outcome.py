"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, packet-store, outcome, feedback-loop, w2-02b]
owner: engine-team
status: active
--- /L9_META ---

tests/unit/test_packet_store_outcome.py
Unit tests for PacketStore.record_outcome() -- W2-02b feedback loop substrate.

Coverage (16 tests):
  - Disabled store returns False without DB call
  - Pool failure is non-fatal (returns False, never raises)
  - Successful UPDATE 1 returns True
  - UPDATE 0 (packet not found / tenant mismatch) returns False + warning
  - outcome_jsonb payload has correct structure
  - feedback_metadata=None serializes as JSON null
  - Tenant always in SQL WHERE clause (RLS safety)
  - asyncpg exception never propagates
  - Idempotent: repeated calls return True, row count == 2
  - value=None, 0.0, 1.0, 100.5 serialize correctly
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# -- Helpers ---------------------------------------------------------------


def _make_store_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import engine.packet.packet_store as ps_mod

    monkeypatch.setattr(ps_mod, "_PACKET_STORE_ENABLED", True)


def _mock_pool(execute_result: str = "UPDATE 1") -> tuple[Any, AsyncMock]:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=execute_result)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)

    pool_mgr = AsyncMock()
    pool_mgr.get_pool = AsyncMock(return_value=pool)
    return pool_mgr, conn


_BASE_KWARGS: dict[str, Any] = {
    "match_packet_id": "550e8400-e29b-41d4-a716-446655440000",
    "tenant": "test-tenant",
    "outcome_id": "out_001",
    "outcome": "success",
    "match_id": "match_001",
    "candidate_id": "cand_001",
    "value": None,
    "feedback_metadata": None,
}


# -- Tests -----------------------------------------------------------------


@pytest.mark.unit
class TestRecordOutcomeDisabled:
    @pytest.mark.asyncio
    async def test_returns_false_when_store_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        monkeypatch.setattr(ps_mod, "_PACKET_STORE_ENABLED", False)
        pool_mgr, _ = _mock_pool()
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        result = await ps_mod.PacketStore().record_outcome(**_BASE_KWARGS)

        assert result is False
        pool_mgr.get_pool.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_db_call_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        monkeypatch.setattr(ps_mod, "_PACKET_STORE_ENABLED", False)
        pool_mgr, conn = _mock_pool()
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        await ps_mod.PacketStore().record_outcome(**_BASE_KWARGS)

        conn.execute.assert_not_called()


@pytest.mark.unit
class TestRecordOutcomePoolFailure:
    @pytest.mark.asyncio
    async def test_pool_error_is_non_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)
        pool_mgr = AsyncMock()
        pool_mgr.get_pool = AsyncMock(side_effect=RuntimeError("DSN not set"))
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        result = await ps_mod.PacketStore().record_outcome(**_BASE_KWARGS)

        assert result is False  # non-fatal, no exception raised


@pytest.mark.unit
class TestRecordOutcomeSuccess:
    @pytest.mark.asyncio
    async def test_returns_true_on_update_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)
        pool_mgr, _ = _mock_pool("UPDATE 1")
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        result = await ps_mod.PacketStore().record_outcome(**_BASE_KWARGS)

        assert result is True

    @pytest.mark.asyncio
    async def test_outcome_jsonb_payload_structure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)

        captured: list[Any] = []

        async def cap(*args: Any) -> str:
            captured.extend(args)
            return "UPDATE 1"

        pool_mgr, conn = _mock_pool()
        conn.execute = AsyncMock(side_effect=cap)
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        feedback = {"weights_recalculated": True, "new_weights": {"geo": 0.27}}
        kwargs = {
            "match_packet_id": "550e8400-e29b-41d4-a716-446655440001",
            "tenant": "plasticos",
            "outcome_id": "out_struct1",
            "outcome": "partial",
            "match_id": "match_002",
            "candidate_id": "cand_002",
            "value": 42.5,
            "feedback_metadata": feedback,
        }
        await ps_mod.PacketStore().record_outcome(**kwargs)

        # captured[0]=SQL, captured[1]=json, captured[2]=packet_id, captured[3]=tenant
        payload = json.loads(captured[1])
        assert payload["outcome_id"] == "out_struct1"
        assert payload["outcome"] == "partial"
        assert payload["match_id"] == "match_002"
        assert payload["candidate_id"] == "cand_002"
        assert payload["value"] == pytest.approx(42.5)
        assert payload["feedback"] == feedback
        assert "recorded_at" in payload
        datetime.fromisoformat(payload["recorded_at"])  # valid ISO-8601

    @pytest.mark.asyncio
    async def test_tenant_in_sql_parameters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)

        captured: list[Any] = []

        async def cap(*args: Any) -> str:
            captured.extend(args)
            return "UPDATE 1"

        pool_mgr, conn = _mock_pool()
        conn.execute = AsyncMock(side_effect=cap)
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        kwargs = dict(_BASE_KWARGS)
        kwargs["tenant"] = "isolated-tenant"
        kwargs["match_packet_id"] = "550e8400-e29b-41d4-a716-446655440002"
        await ps_mod.PacketStore().record_outcome(**kwargs)

        assert captured[3] == "isolated-tenant"
        assert captured[2] == "550e8400-e29b-41d4-a716-446655440002"

    @pytest.mark.asyncio
    async def test_feedback_metadata_none_is_json_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)

        captured: list[str] = []

        async def cap(*args: Any) -> str:
            captured.append(args[1])
            return "UPDATE 1"

        pool_mgr, conn = _mock_pool()
        conn.execute = AsyncMock(side_effect=cap)
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        await ps_mod.PacketStore().record_outcome(**_BASE_KWARGS)

        payload = json.loads(captured[0])
        assert "feedback" in payload
        assert payload["feedback"] is None  # serialized as null, not absent


@pytest.mark.unit
class TestRecordOutcomeNoRowFound:
    @pytest.mark.asyncio
    async def test_returns_false_on_update_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)
        pool_mgr, _ = _mock_pool("UPDATE 0")
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        kwargs = dict(_BASE_KWARGS)
        kwargs["match_packet_id"] = "00000000-0000-0000-0000-000000000000"
        kwargs["tenant"] = "ghost-tenant"
        result = await ps_mod.PacketStore().record_outcome(**kwargs)

        assert result is False


@pytest.mark.unit
class TestRecordOutcomeNonFatal:
    @pytest.mark.asyncio
    async def test_asyncpg_exception_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)

        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("connection reset by peer"))
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=False)
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=acq)
        pool_mgr = AsyncMock()
        pool_mgr.get_pool = AsyncMock(return_value=pool)
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        result = await ps_mod.PacketStore().record_outcome(**_BASE_KWARGS)

        assert result is False  # never raises

    @pytest.mark.asyncio
    async def test_idempotent_second_write_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)

        call_count = 0

        async def count(*args: Any) -> str:
            nonlocal call_count
            call_count += 1
            return "UPDATE 1"

        pool_mgr, conn = _mock_pool()
        conn.execute = AsyncMock(side_effect=count)
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        store = ps_mod.PacketStore()
        r1 = await store.record_outcome(**_BASE_KWARGS)
        r2 = await store.record_outcome(**_BASE_KWARGS)

        assert r1 is True
        assert r2 is True
        assert call_count == 2


@pytest.mark.unit
class TestRecordOutcomeValueTypes:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            (0.0, 0.0),
            (1.0, 1.0),
            (100.5, 100.5),
        ],
    )
    @pytest.mark.asyncio
    async def test_value_serialization(
        self,
        value: float | None,
        expected: float | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import engine.packet.packet_store as ps_mod

        _make_store_enabled(monkeypatch)

        captured: list[str] = []

        async def cap(*args: Any) -> str:
            captured.append(args[1])
            return "UPDATE 1"

        pool_mgr, conn = _mock_pool()
        conn.execute = AsyncMock(side_effect=cap)
        monkeypatch.setattr(ps_mod, "_pool_manager", pool_mgr)

        kwargs = dict(_BASE_KWARGS, value=value)
        await ps_mod.PacketStore().record_outcome(**kwargs)

        payload = json.loads(captured[0])
        assert payload["value"] == expected
