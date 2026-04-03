"""Unit tests — DomainPackLoader. No Neo4j required."""

from __future__ import annotations

from pathlib import Path

import pytest

# RULE 9: absolute path — same pattern used in conftest.py
DOMAINS_DIR = Path(__file__).parent.parent.parent / "domains"


def test_load_plasticos_returns_domain_spec():
    from engine.config.loader import DomainPackLoader
    from engine.config.schema import DomainSpec

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    assert isinstance(spec, DomainSpec)
    assert spec.domain.id == "plasticos"


def test_load_caches_second_call():
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec1 = loader.load_domain("plasticos")
    spec2 = loader.load_domain("plasticos")
    assert spec1 is spec2  # same object — cache hit


def test_invalidate_clears_cache():
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec1 = loader.load_domain("plasticos")
    loader.invalidate("plasticos")
    spec2 = loader.load_domain("plasticos")
    assert spec1 is not spec2  # different object — cache was cleared


def test_list_domains_includes_plasticos():
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    assert "plasticos" in loader.list_domains()


def test_missing_domain_raises():
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    with pytest.raises(Exception, match="nonexistent"):
        loader.load_domain("nonexistent")


def test_malformed_yaml_raises(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("domain:\n  id: [unclosed")
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=tmp_path)
    with pytest.raises(Exception):
        loader.load_domain("broken")


def test_empty_domains_dir_returns_empty_list(tmp_path):
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader(domains_dir=tmp_path)
    assert loader.list_domains() == []
