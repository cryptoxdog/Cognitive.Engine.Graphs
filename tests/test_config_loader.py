# tests/test_config_loader.py
"""Tests for DomainPackLoader cache invalidation and path security."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine.config.loader import DomainNotFoundError, DomainPackLoader


@pytest.fixture
def domains_dir(tmp_path: Path) -> Path:
    domain_dir = tmp_path / "testdomain"
    domain_dir.mkdir()
    minimal_spec = {
        "domain": {"id": "testdomain", "name": "Test", "version": "1.0"},
        "ontology": {
            "nodes": [
                {
                    "label": "Widget",
                    "managedby": "static",
                    "properties": [{"name": "widget_id", "type": "string", "required": True}],
                }
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "Widget", "matchdirection": "default"}],
            "queryentity": [{"label": "Widget", "matchdirection": "default"}],
        },
        "queryschema": {"matchdirections": ["default"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }
    (domain_dir / "spec.yaml").write_text(yaml.dump(minimal_spec))
    return tmp_path


def test_list_domains(domains_dir: Path) -> None:
    assert "testdomain" in DomainPackLoader(str(domains_dir)).list_domains()


def test_cache_hit(domains_dir: Path) -> None:
    loader = DomainPackLoader(str(domains_dir))
    assert loader.load_domain("testdomain") is loader.load_domain("testdomain")


def test_cache_invalidation_on_mtime(domains_dir: Path) -> None:
    loader = DomainPackLoader(str(domains_dir))
    spec1 = loader.load_domain("testdomain")
    raw = yaml.safe_load((domains_dir / "testdomain" / "spec.yaml").read_text())
    raw["domain"]["version"] = "2.0"
    (domains_dir / "testdomain" / "spec.yaml").write_text(yaml.dump(raw))
    assert loader.load_domain("testdomain") is not spec1


def test_explicit_invalidation(domains_dir: Path) -> None:
    loader = DomainPackLoader(str(domains_dir))
    spec1 = loader.load_domain("testdomain")
    loader.invalidate("testdomain")
    assert loader.load_domain("testdomain") is not spec1


def test_path_traversal_blocked(domains_dir: Path) -> None:
    with pytest.raises(DomainNotFoundError):
        DomainPackLoader(str(domains_dir)).load_domain("../../etc/passwd")


def test_nonexistent_domain(domains_dir: Path) -> None:
    with pytest.raises(DomainNotFoundError):
        DomainPackLoader(str(domains_dir)).load_domain("nope")
