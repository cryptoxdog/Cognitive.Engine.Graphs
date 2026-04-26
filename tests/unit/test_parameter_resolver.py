"""Unit tests — Parameter coercion: range floats, booleans, set lists, None exclusion."""

from __future__ import annotations

from pathlib import Path

DOMAINS_DIR = Path(__file__).parent.parent.parent / "domains"


def test_none_values_excluded_from_params():
    """None values must never reach Cypher parameters."""
    from engine.config.loader import DomainPackLoader
    from engine.traversal.resolver import ParameterResolver

    loader = DomainPackLoader(config_path=str(DOMAINS_DIR))
    spec = loader.load_domain("plasticos")
    resolver = ParameterResolver(spec)
    result = resolver.resolve({"some_param": None, "valid_param": "value"})
    assert "some_param" not in result
    assert result.get("valid_param") == "value"


def test_string_passthrough():
    from engine.config.loader import DomainPackLoader
    from engine.traversal.resolver import ParameterResolver

    loader = DomainPackLoader(config_path=str(DOMAINS_DIR))
    spec = loader.load_domain("plasticos")
    resolver = ParameterResolver(spec)
    result = resolver.resolve({"tag": "HDPE"})
    assert result["tag"] == "HDPE"


def test_empty_params_returns_empty():
    from engine.config.loader import DomainPackLoader
    from engine.traversal.resolver import ParameterResolver

    loader = DomainPackLoader(config_path=str(DOMAINS_DIR))
    spec = loader.load_domain("plasticos")
    resolver = ParameterResolver(spec)
    result = resolver.resolve({})
    assert isinstance(result, dict)
    assert len(result) == 0
