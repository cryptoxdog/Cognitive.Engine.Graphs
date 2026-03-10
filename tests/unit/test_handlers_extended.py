# ============================================================================
# tests/unit/test_handlers_extended.py
# ============================================================================
"""
Unit tests for engine/handlers.py — extended coverage.
Covers: handle_outcomes, handle_resolve, handle_admin, register_all,
        init_dependencies, _require_deps, _require_key.
Target Coverage: 85%+
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.handlers import (
    EngineError,
    ExecutionError,
    ValidationError,
    _require_deps,
    _require_key,
    handle_admin,
    handle_outcomes,
    handle_resolve,
    init_dependencies,
    register_all,
)

# ============================================================================
# FIXTURES
# ============================================================================


def _mock_domain_spec():
    """Create a mock DomainSpec with common fields."""
    spec = MagicMock()
    spec.domain.id = "test_db"
    spec.gates = []
    spec.ontology.nodes = []
    spec.matchentities.candidate = []
    spec.matchentities.queryentity = []
    spec.compliance = None
    spec.sync = None
    spec.model_dump.return_value = {"domain": {"id": "test_db"}}
    return spec


def _mock_deps():
    """Return (mock_driver, mock_loader) with standard config."""
    driver = MagicMock()
    driver.execute_query = AsyncMock(return_value=[{"outcome_id": "out_abc123"}])
    loader = MagicMock()
    loader.load_domain.return_value = _mock_domain_spec()
    loader.list_domains.return_value = ["plasticos", "mortgage"]
    return driver, loader


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestEngineErrors:
    """Test EngineError hierarchy."""

    def test_engine_error_fields(self) -> None:
        """EngineError stores action, tenant, and detail."""
        err = EngineError("test", action="match", tenant="t1", detail="d1")
        assert err.action == "match"
        assert err.tenant == "t1"
        assert err.detail == "d1"

    def test_validation_error_is_engine_error(self) -> None:
        """ValidationError inherits from EngineError."""
        err = ValidationError("bad", action="sync", tenant="t2")
        assert isinstance(err, EngineError)

    def test_execution_error_is_engine_error(self) -> None:
        """ExecutionError inherits from EngineError."""
        err = ExecutionError("fail", action="admin", tenant="t3")
        assert isinstance(err, EngineError)


@pytest.mark.unit
class TestRequireDeps:
    """Test _require_deps helper."""

    def test_raises_when_not_initialized(self) -> None:
        """_require_deps raises RuntimeError when deps are None."""
        with patch("engine.handlers._graph_driver", None), patch("engine.handlers._domain_loader", None):
            with pytest.raises(RuntimeError, match="Dependencies not initialized"):
                _require_deps()

    def test_returns_deps_when_initialized(self) -> None:
        """_require_deps returns (driver, loader) when initialized."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = _require_deps()
            assert result == (driver, loader)


@pytest.mark.unit
class TestRequireKey:
    """Test _require_key helper."""

    def test_returns_value_when_present(self) -> None:
        """_require_key returns the value for existing keys."""
        result = _require_key({"foo": "bar"}, "foo", "test", "t1")
        assert result == "bar"

    def test_raises_validation_error_when_missing(self) -> None:
        """_require_key raises ValidationError for missing keys."""
        with pytest.raises(ValidationError, match="Missing required field 'missing'"):
            _require_key({}, "missing", "test", "t1")


@pytest.mark.unit
class TestInitDependencies:
    """Test init_dependencies."""

    def test_sets_global_driver_and_loader(self) -> None:
        """init_dependencies sets module-level globals."""
        driver = MagicMock()
        loader = MagicMock()
        with patch("engine.handlers._graph_driver", None) as _, patch("engine.handlers._domain_loader", None) as _:
            init_dependencies(driver, loader)


@pytest.mark.unit
class TestHandleOutcomes:
    """Test handle_outcomes handler."""

    @pytest.mark.asyncio
    async def test_outcomes_success(self) -> None:
        """handle_outcomes records a success outcome."""
        driver, loader = _mock_deps()
        spec = _mock_domain_spec()
        spec.compliance = None
        loader.load_domain.return_value = spec

        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_outcomes(
                "t1",
                {
                    "match_id": "m_123",
                    "candidate_id": "c_456",
                    "outcome": "success",
                },
            )
            assert result["status"] == "recorded"
            assert "outcome_id" in result
            driver.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_outcomes_failure_outcome(self) -> None:
        """handle_outcomes accepts failure outcome."""
        driver, loader = _mock_deps()
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_outcomes(
                "t1",
                {
                    "match_id": "m_1",
                    "candidate_id": "c_1",
                    "outcome": "failure",
                },
            )
            assert result["status"] == "recorded"

    @pytest.mark.asyncio
    async def test_outcomes_partial_outcome(self) -> None:
        """handle_outcomes accepts partial outcome."""
        driver, loader = _mock_deps()
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_outcomes(
                "t1",
                {
                    "match_id": "m_1",
                    "candidate_id": "c_1",
                    "outcome": "partial",
                },
            )
            assert result["status"] == "recorded"

    @pytest.mark.asyncio
    async def test_outcomes_invalid_outcome_raises(self) -> None:
        """handle_outcomes raises ValidationError for invalid outcome string."""
        driver, loader = _mock_deps()
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ValidationError, match="Invalid outcome"):
                await handle_outcomes(
                    "t1",
                    {
                        "match_id": "m_1",
                        "candidate_id": "c_1",
                        "outcome": "invalid",
                    },
                )

    @pytest.mark.asyncio
    async def test_outcomes_missing_match_id_raises(self) -> None:
        """handle_outcomes raises ValidationError when match_id missing."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ValidationError, match="Missing required field 'match_id'"):
                await handle_outcomes("t1", {"candidate_id": "c_1", "outcome": "success"})

    @pytest.mark.asyncio
    async def test_outcomes_neo4j_error_raises_execution_error(self) -> None:
        """handle_outcomes raises ExecutionError on Neo4j failure."""
        driver, loader = _mock_deps()
        driver.execute_query = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ExecutionError, match="Outcome write failed"):
                await handle_outcomes(
                    "t1",
                    {
                        "match_id": "m_1",
                        "candidate_id": "c_1",
                        "outcome": "success",
                    },
                )


@pytest.mark.unit
class TestHandleResolve:
    """Test handle_resolve handler."""

    @pytest.mark.asyncio
    async def test_resolve_success(self) -> None:
        """handle_resolve creates RESOLVED_FROM edge and returns IDs."""
        driver, loader = _mock_deps()
        driver.execute_query = AsyncMock(return_value=[{"resolution_id": "res_abc"}])
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_resolve(
                "t1",
                {
                    "entity_type": "Facility",
                    "source_id": "src_1",
                    "target_id": "tgt_1",
                },
            )
            assert result["status"] == "resolved"
            assert "resolution_id" in result
            assert result["source_id"] == "src_1"
            assert result["target_id"] == "tgt_1"

    @pytest.mark.asyncio
    async def test_resolve_with_confidence_and_signal(self) -> None:
        """handle_resolve passes confidence and signal params."""
        driver, loader = _mock_deps()
        driver.execute_query = AsyncMock(return_value=[{}])
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_resolve(
                "t1",
                {
                    "entity_type": "Facility",
                    "source_id": "s1",
                    "target_id": "t1",
                    "confidence": 0.85,
                    "signal": "embedding",
                },
            )
            assert result["status"] == "resolved"
            call_kwargs = driver.execute_query.call_args
            params = call_kwargs.kwargs.get("parameters") or call_kwargs[1].get("parameters", {})
            assert params["confidence"] == 0.85
            assert params["signal"] == "embedding"

    @pytest.mark.asyncio
    async def test_resolve_missing_entity_type_raises(self) -> None:
        """handle_resolve raises ValidationError when entity_type missing."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ValidationError, match="Missing required field 'entity_type'"):
                await handle_resolve("t1", {"source_id": "s1", "target_id": "t1"})

    @pytest.mark.asyncio
    async def test_resolve_neo4j_error_raises_execution_error(self) -> None:
        """handle_resolve raises ExecutionError on Neo4j failure."""
        driver, loader = _mock_deps()
        driver.execute_query = AsyncMock(side_effect=RuntimeError("connection lost"))
        loader.load_domain.return_value = _mock_domain_spec()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ExecutionError, match="Entity resolution failed"):
                await handle_resolve(
                    "t1",
                    {
                        "entity_type": "Facility",
                        "source_id": "s1",
                        "target_id": "t1",
                    },
                )


@pytest.mark.unit
class TestHandleAdmin:
    """Test handle_admin handler."""

    @pytest.mark.asyncio
    async def test_admin_list_domains(self) -> None:
        """admin list_domains returns domain list."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_admin("t1", {"subaction": "list_domains"})
            assert "domains" in result
            assert result["domains"] == ["plasticos", "mortgage"]

    @pytest.mark.asyncio
    async def test_admin_get_domain(self) -> None:
        """admin get_domain returns serialized domain spec."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_admin("t1", {"subaction": "get_domain", "domain_id": "plasticos"})
            assert "domain" in result

    @pytest.mark.asyncio
    async def test_admin_init_schema(self) -> None:
        """admin init_schema creates constraints and returns count."""
        driver, loader = _mock_deps()
        driver.execute_query = AsyncMock(return_value=[])
        spec = _mock_domain_spec()
        spec.ontology.nodes = []
        loader.load_domain.return_value = spec
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            result = await handle_admin("t1", {"subaction": "init_schema", "domain_id": "plasticos"})
            assert result["status"] == "schema_initialized"
            assert "constraints_created" in result

    @pytest.mark.asyncio
    async def test_admin_trigger_gds(self) -> None:
        """admin trigger_gds triggers a GDS job."""
        driver, loader = _mock_deps()
        spec = _mock_domain_spec()
        spec.gdsjobs = []
        loader.load_domain.return_value = spec
        mock_scheduler = MagicMock()
        mock_scheduler.trigger_job = AsyncMock(return_value={"nodes_written": 10})
        with (
            patch("engine.handlers._graph_driver", driver),
            patch("engine.handlers._domain_loader", loader),
            patch("engine.handlers._get_or_create_scheduler", return_value=mock_scheduler),
        ):
            result = await handle_admin(
                "t1",
                {
                    "subaction": "trigger_gds",
                    "domain_id": "plasticos",
                    "job_name": "louvain",
                },
            )
            assert result["status"] == "triggered"
            assert result["job"] == "louvain"

    @pytest.mark.asyncio
    async def test_admin_unknown_subaction_raises(self) -> None:
        """admin raises ValidationError for unknown subaction."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ValidationError, match="Unknown admin subaction"):
                await handle_admin("t1", {"subaction": "nope"})

    @pytest.mark.asyncio
    async def test_admin_missing_subaction_raises(self) -> None:
        """admin raises ValidationError when subaction missing."""
        driver, loader = _mock_deps()
        with patch("engine.handlers._graph_driver", driver), patch("engine.handlers._domain_loader", loader):
            with pytest.raises(ValidationError, match="Missing required field 'subaction'"):
                await handle_admin("t1", {})


@pytest.mark.unit
class TestRegisterAll:
    """Test register_all function."""

    def test_registers_all_8_handlers(self) -> None:
        """register_all registers exactly 8 handlers."""
        mock_router = MagicMock()
        register_all(mock_router)
        assert mock_router.register_handler.call_count == 8
        registered = {call.args[0] for call in mock_router.register_handler.call_args_list}
        expected = {"match", "sync", "admin", "outcomes", "resolve", "health", "healthcheck", "enrich"}
        assert registered == expected
