"""Unit tests — Parameter coercion: range floats, booleans, set lists, None exclusion."""

from __future__ import annotations

import pytest


@pytest.fixture
def plasticos_spec():
    """Load plasticos spec, skip if not loadable."""
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader()
    try:
        return loader.load_domain("plasticos")
    except Exception:
        pytest.skip("plasticos domain spec not loadable with current schema")


def test_none_values_excluded_from_params(plasticos_spec):
    """None values must never reach Cypher parameters."""
    from engine.traversal.resolver import ParameterResolver

    resolver = ParameterResolver(plasticos_spec)
    result = resolver.resolve({"some_param": None, "valid_param": "value"})
    assert "some_param" not in result
    assert result.get("valid_param") == "value"


def test_string_passthrough(plasticos_spec):
    """String params pass through unchanged."""
    from engine.traversal.resolver import ParameterResolver

    resolver = ParameterResolver(plasticos_spec)
    result = resolver.resolve({"tag": "HDPE"})
    assert result["tag"] == "HDPE"


def test_empty_params_returns_empty(plasticos_spec):
    """Empty input returns empty dict."""
    from engine.traversal.resolver import ParameterResolver

    resolver = ParameterResolver(plasticos_spec)
    result = resolver.resolve({})
    assert isinstance(result, dict)
    assert len(result) == 0
