"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring]
owner: engine-team
status: active
--- /L9_META ---

Tests for scoring assembler security — CUSTOMCYPHER expression validation.

Covers AUD8-HIGH-03: CUSTOMCYPHER validator test coverage.
"""

from __future__ import annotations

import pytest

from engine.scoring.assembler import _validate_custom_expression


class TestValidateCustomExpression:
    """Test _validate_custom_expression() for CUSTOMCYPHER security."""

    # ─────────────────────────────────────────────────────────────────────────
    # ALLOWED EXPRESSIONS (should pass validation)
    # ─────────────────────────────────────────────────────────────────────────

    def test_allows_simple_property_access(self) -> None:
        """Simple property access should be allowed."""
        assert _validate_custom_expression("candidate.price", "test_dim") == "candidate.price"
        assert _validate_custom_expression("query.threshold", "test_dim") == "query.threshold"

    def test_allows_arithmetic_expressions(self) -> None:
        """Arithmetic on properties should be allowed."""
        expr = "candidate.price * 1.5 + query.threshold"
        assert _validate_custom_expression(expr, "test_dim") == expr

    def test_allows_safe_functions(self) -> None:
        """Safe Cypher functions should be allowed."""
        assert _validate_custom_expression("coalesce(candidate.value, 0)", "test_dim")
        assert _validate_custom_expression("log(candidate.count + 1)", "test_dim")
        assert _validate_custom_expression("exp(candidate.score)", "test_dim")
        assert _validate_custom_expression("abs(candidate.delta)", "test_dim")
        assert _validate_custom_expression("toFloat(candidate.amount)", "test_dim")

    def test_allows_keyword_as_property_substring(self) -> None:
        """Keywords as substrings in property names should be allowed."""
        # 'call' is substring of 'recall_rate' but not a word boundary
        assert _validate_custom_expression("candidate.recall_rate", "test_dim")
        # 'set' is substring of 'dataset_id'
        assert _validate_custom_expression("candidate.dataset_id", "test_dim")
        # 'match' is substring of 'match_score' — wait, this IS a word boundary
        # Actually 'match_score' has 'match' at word boundary, so this should fail
        # Let's test 'rematch_count' instead
        assert _validate_custom_expression("candidate.rematch_count", "test_dim")
        # 'delete' is substring of 'undelete_flag'
        assert _validate_custom_expression("candidate.undelete_flag", "test_dim")

    def test_allows_complex_safe_expression(self) -> None:
        """Complex but safe expressions should be allowed."""
        expr = "coalesce(candidate.weight, 1.0) * log(candidate.volume + 1) / query.normalizer"
        assert _validate_custom_expression(expr, "test_dim") == expr

    # ─────────────────────────────────────────────────────────────────────────
    # FORBIDDEN EXPRESSIONS (should raise ValueError)
    # ─────────────────────────────────────────────────────────────────────────

    def test_blocks_call_keyword(self) -> None:
        """CALL keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'call'"):
            _validate_custom_expression("candidate.x CALL something", "test_dim")

    def test_blocks_call_lowercase(self) -> None:
        """call keyword (lowercase) should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'call'"):
            _validate_custom_expression("call db.labels()", "test_dim")

    def test_blocks_create_keyword(self) -> None:
        """CREATE keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'create'"):
            _validate_custom_expression("candidate.x} CREATE (evil:Node) //", "test_dim")

    def test_blocks_merge_keyword(self) -> None:
        """MERGE keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'merge'"):
            _validate_custom_expression("candidate.x} MERGE (evil:Node) //", "test_dim")

    def test_blocks_delete_keyword(self) -> None:
        """DELETE keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'delete'"):
            _validate_custom_expression("candidate.x} DELETE n //", "test_dim")

    def test_blocks_detach_keyword(self) -> None:
        """DETACH keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'detach'"):
            _validate_custom_expression("candidate.x} DETACH DELETE n //", "test_dim")

    def test_blocks_match_keyword(self) -> None:
        """MATCH keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'match'"):
            _validate_custom_expression("candidate.x} MATCH (a)-[r]->(b) //", "test_dim")

    def test_blocks_return_keyword(self) -> None:
        """RETURN keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'return'"):
            _validate_custom_expression("candidate.x} RETURN n //", "test_dim")

    def test_blocks_with_keyword(self) -> None:
        """WITH keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'with'"):
            _validate_custom_expression("candidate.x} WITH 1 AS x //", "test_dim")

    def test_blocks_unwind_keyword(self) -> None:
        """UNWIND keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'unwind'"):
            _validate_custom_expression("candidate.x} UNWIND [1,2,3] AS x //", "test_dim")

    def test_blocks_foreach_keyword(self) -> None:
        """FOREACH keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'foreach'"):
            _validate_custom_expression("candidate.x FOREACH something", "test_dim")

    def test_blocks_load_keyword(self) -> None:
        """LOAD keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'load'"):
            _validate_custom_expression("candidate.x} LOAD CSV FROM 'http://evil.com' //", "test_dim")

    def test_blocks_union_keyword(self) -> None:
        """UNION keyword should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'union'"):
            _validate_custom_expression("candidate.x UNION candidate.y", "test_dim")

    def test_blocks_apoc_procedures(self) -> None:
        """APOC procedures should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'apoc'"):
            _validate_custom_expression("apoc.do.when(true, 'evil')", "test_dim")

    def test_blocks_gds_procedures(self) -> None:
        """GDS procedures should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'gds'"):
            _validate_custom_expression("gds.louvain.write()", "test_dim")

    def test_blocks_dbms_procedures(self) -> None:
        """DBMS procedures should be blocked."""
        with pytest.raises(ValueError, match="forbidden keyword 'dbms'"):
            _validate_custom_expression("dbms.security.createUser()", "test_dim")

    def test_blocks_line_comments(self) -> None:
        """Line comments should be blocked."""
        with pytest.raises(ValueError, match="comment syntax"):
            _validate_custom_expression("candidate.x // comment", "test_dim")

    def test_blocks_block_comments(self) -> None:
        """Block comments should be blocked."""
        with pytest.raises(ValueError, match="comment syntax"):
            _validate_custom_expression("candidate.x /* comment */", "test_dim")

    def test_blocks_dollar_dollar_injection(self) -> None:
        """$$ injection pattern should be blocked."""
        with pytest.raises(ValueError, match="injection pattern"):
            _validate_custom_expression("$$evil$$", "test_dim")

    def test_blocks_dollar_brace_injection(self) -> None:
        """${ injection pattern should be blocked."""
        with pytest.raises(ValueError, match="injection pattern"):
            _validate_custom_expression("${evil}", "test_dim")

    # ─────────────────────────────────────────────────────────────────────────
    # EDGE CASES
    # ─────────────────────────────────────────────────────────────────────────

    def test_case_insensitive_keyword_detection(self) -> None:
        """Keyword detection should be case-insensitive."""
        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_custom_expression("CaLl apoc.foo()", "test_dim")
        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_custom_expression("MATCH (n)", "test_dim")
        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_custom_expression("match (n)", "test_dim")

    def test_keyword_must_be_word_boundary(self) -> None:
        """Keywords must be at word boundaries to be blocked."""
        # 'recall' contains 'call' but not at word boundary
        assert _validate_custom_expression("candidate.recall", "test_dim")
        # 'unmatch' contains 'match' but not at word boundary
        assert _validate_custom_expression("candidate.unmatch_count", "test_dim")
        # 'dataset' contains 'set' but not at word boundary
        assert _validate_custom_expression("candidate.dataset", "test_dim")

    def test_dimension_name_in_error_message(self) -> None:
        """Error messages should include the dimension name."""
        with pytest.raises(ValueError, match="my_custom_dim"):
            _validate_custom_expression("CALL evil()", "my_custom_dim")
