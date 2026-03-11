"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, handlers]
owner: engine-team
status: active
--- /L9_META ---

Tests for handle_enrich and handle_healthcheck handlers.

Covers:
- SHIP-17: Zero test coverage for handle_enrich and handle_healthcheck
- AUD6-12: No tests for handle_enrich expression validation path
"""

from __future__ import annotations

import pytest

from engine.handlers import (
    ValidationError,
    _sanitize_expression,
)


class TestSanitizeExpression:
    """Test expression sanitization for handle_enrich."""

    def test_allows_simple_property_access(self) -> None:
        """n.property_name patterns should be allowed."""
        assert _sanitize_expression("n.price") == "n.price"
        assert _sanitize_expression("n.quantity") == "n.quantity"
        assert _sanitize_expression("n.total_amount") == "n.total_amount"

    def test_allows_numeric_literals(self) -> None:
        """Numeric literals should pass through."""
        assert _sanitize_expression("42") == "42"
        assert _sanitize_expression("3.14") == "3.14"
        assert _sanitize_expression("-100") == "-100"

    def test_allows_boolean_literals(self) -> None:
        """Boolean literals should be allowed."""
        assert _sanitize_expression("true") == "true"
        assert _sanitize_expression("false") == "false"
        assert _sanitize_expression("null") == "null"

    def test_allows_string_literals(self) -> None:
        """Simple string literals should be allowed."""
        assert _sanitize_expression("'hello'") == "'hello'"
        assert _sanitize_expression('"world"') == '"world"'

    def test_allows_arithmetic_expressions(self) -> None:
        """Arithmetic on properties should be allowed."""
        assert _sanitize_expression("n.price * n.quantity") == "n.price * n.quantity"
        assert _sanitize_expression("n.total / 100") == "n.total / 100"
        assert _sanitize_expression("n.a + n.b - n.c") == "n.a + n.b - n.c"

    def test_allows_safe_functions(self) -> None:
        """Safe Cypher functions should be allowed."""
        assert _sanitize_expression("toUpper(n.name)") == "toUpper(n.name)"
        assert _sanitize_expression("coalesce(n.value, 0)") == "coalesce(n.value, 0)"
        assert _sanitize_expression("abs(n.delta)") == "abs(n.delta)"

    def test_blocks_call_keyword(self) -> None:
        """CALL keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'call'"):
            _sanitize_expression("n.x CALL something")

    def test_blocks_create_keyword(self) -> None:
        """CREATE keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'create'"):
            _sanitize_expression("n.x} CREATE (evil:Node)")

    def test_blocks_delete_keyword(self) -> None:
        """DELETE keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'delete'"):
            _sanitize_expression("n.x} DELETE n")

    def test_blocks_detach_delete(self) -> None:
        """DETACH DELETE should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'detach'"):
            _sanitize_expression("n.x} DETACH DELETE n")

    def test_blocks_merge_keyword(self) -> None:
        """MERGE keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'merge'"):
            _sanitize_expression("n.x} MERGE (evil:Node)")

    def test_blocks_match_keyword(self) -> None:
        """MATCH keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'match'"):
            _sanitize_expression("n.x} MATCH (a)")

    def test_blocks_union_keyword(self) -> None:
        """UNION keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'union'"):
            _sanitize_expression("n.x UNION n.y")

    def test_blocks_with_keyword(self) -> None:
        """WITH keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'with'"):
            _sanitize_expression("n.x WITH 1 AS x")

    def test_blocks_unwind_keyword(self) -> None:
        """UNWIND keyword should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'unwind'"):
            _sanitize_expression("n.x UNWIND n.y")

    def test_blocks_load_csv(self) -> None:
        """LOAD CSV should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'load'"):
            _sanitize_expression("n.x LOAD n.y")

    def test_blocks_apoc_procedures(self) -> None:
        """APOC procedures should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'apoc'"):
            _sanitize_expression("apoc.do.when(true, 'evil')")

    def test_blocks_gds_procedures(self) -> None:
        """GDS procedures should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'gds'"):
            _sanitize_expression("gds.louvain.write()")

    def test_blocks_dbms_procedures(self) -> None:
        """DBMS procedures should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden keyword 'dbms'"):
            _sanitize_expression("dbms.security.createUser()")

    def test_blocks_db_dot_prefix(self) -> None:
        """db. prefix should be blocked."""
        with pytest.raises(ValidationError, match=r"Forbidden pattern 'db\.'"):
            _sanitize_expression("db.labels()")

    def test_blocks_line_comments(self) -> None:
        """Line comments should be blocked."""
        with pytest.raises(ValidationError, match="Forbidden pattern '//'"):
            _sanitize_expression("n.x // comment")

    def test_blocks_block_comments(self) -> None:
        """Block comments should be blocked."""
        with pytest.raises(ValidationError, match=r"Forbidden pattern '/\*'"):
            _sanitize_expression("n.x /* comment */")

    def test_blocks_dollar_dollar_injection(self) -> None:
        """$$ injection pattern should be blocked."""
        with pytest.raises(ValidationError, match=r"Forbidden pattern '\$\$'"):
            _sanitize_expression("$$evil$$")

    def test_blocks_dollar_brace_injection(self) -> None:
        """${ injection pattern should be blocked."""
        with pytest.raises(ValidationError, match=r"Forbidden pattern '\$\{'"):
            _sanitize_expression("${evil}")

    def test_blocks_string_with_embedded_quotes(self) -> None:
        """String literals with embedded quotes/escapes should be blocked."""
        # String with escape character - blocked at pattern validation stage
        with pytest.raises(ValidationError, match="does not match allowed patterns"):
            _sanitize_expression("'it\\'s evil'")

    def test_blocks_disallowed_characters(self) -> None:
        """Characters outside whitelist should be blocked."""
        with pytest.raises(ValidationError, match="Disallowed character"):
            _sanitize_expression("n.x; DROP TABLE users")

    def test_blocks_expressions_without_safe_patterns(self) -> None:
        """Expressions without property access or safe functions should be blocked."""
        with pytest.raises(ValidationError, match="does not match allowed patterns"):
            _sanitize_expression("random_stuff")


class TestHandleHealthcheck:
    """Test handle_healthcheck handler."""

    @pytest.mark.asyncio
    async def test_healthcheck_returns_status(self) -> None:
        """handle_healthcheck should return health status dict."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_driver = MagicMock()
        mock_driver.execute_query = AsyncMock(return_value=[{"ping": 1}])

        mock_loader = MagicMock()
        mock_loader.load_domain.return_value = MagicMock()

        with patch("engine.handlers._graph_driver", mock_driver), patch("engine.handlers._domain_loader", mock_loader):
            from engine.handlers import handle_healthcheck

            result = await handle_healthcheck("test_tenant", {})

            assert "status" in result
            assert result["status"] == "healthy"
            assert "checks" in result
            assert "neo4j" in result["checks"]


class TestHandleEnrich:
    """Test handle_enrich handler."""

    @pytest.mark.asyncio
    async def test_enrich_requires_entity_type(self) -> None:
        """handle_enrich should require entity_type in payload."""
        from unittest.mock import MagicMock, patch

        mock_driver = MagicMock()
        mock_loader = MagicMock()
        mock_loader.load_domain.return_value = MagicMock()

        with patch("engine.handlers._graph_driver", mock_driver), patch("engine.handlers._domain_loader", mock_loader):
            from engine.handlers import handle_enrich

            with pytest.raises(ValidationError, match="entity_type required"):
                await handle_enrich("test_tenant", {})

    @pytest.mark.asyncio
    async def test_enrich_returns_zero_for_empty_enrichments(self) -> None:
        """handle_enrich should return 0 count for empty enrichments."""
        from unittest.mock import MagicMock, patch

        mock_driver = MagicMock()
        mock_loader = MagicMock()
        mock_loader.load_domain.return_value = MagicMock()

        with patch("engine.handlers._graph_driver", mock_driver), patch("engine.handlers._domain_loader", mock_loader):
            from engine.handlers import handle_enrich

            result = await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [],
                },
            )

            assert result["enriched_count"] == 0
            assert result["entity_type"] == "Facility"

    @pytest.mark.asyncio
    async def test_enrich_validates_expressions(self) -> None:
        """handle_enrich should validate expressions before execution."""
        from unittest.mock import MagicMock, patch

        mock_driver = MagicMock()
        mock_loader = MagicMock()
        mock_loader.load_domain.return_value = MagicMock()

        with patch("engine.handlers._graph_driver", mock_driver), patch("engine.handlers._domain_loader", mock_loader):
            from engine.handlers import handle_enrich

            with pytest.raises(ValidationError, match="Forbidden keyword 'call'"):
                await handle_enrich(
                    "test_tenant",
                    {
                        "entity_type": "Facility",
                        "enrichments": [
                            {"property": "evil", "expression": "n.x CALL something"},
                        ],
                    },
                )

    @pytest.mark.asyncio
    async def test_enrich_executes_valid_enrichment(self) -> None:
        """handle_enrich should execute valid enrichments."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_driver = MagicMock()
        mock_driver.execute_query = AsyncMock(return_value=[{"enriched_count": 5}])

        mock_spec = MagicMock()
        mock_spec.domain.id = "test_db"

        mock_loader = MagicMock()
        mock_loader.load_domain.return_value = mock_spec

        with patch("engine.handlers._graph_driver", mock_driver), patch("engine.handlers._domain_loader", mock_loader):
            from engine.handlers import handle_enrich

            result = await handle_enrich(
                "test_tenant",
                {
                    "entity_type": "Facility",
                    "enrichments": [
                        {"property": "computed_value", "expression": "n.price * n.quantity"},
                    ],
                },
            )

            assert result["enriched_count"] == 5
            assert result["entity_type"] == "Facility"
            mock_driver.execute_query.assert_called_once()
