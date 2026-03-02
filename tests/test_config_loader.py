# tests/test_config_loader.py
"""Tests for DomainPackLoader cache invalidation and path security."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from engine.config.loader import (
    MAX_SPEC_BYTES,
    DomainNotFoundError,
    DomainPackLoader,
    DomainSpecError,
)


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


class TestPathTraversalSecurity:
    """Security tests for DomainPackLoader path traversal prevention."""

    def test_path_traversal_blocked_parent_dir(self, domains_dir: Path) -> None:
        """Reject ../.. traversal attempts."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("../../etc/passwd")

    def test_path_traversal_blocked_single_parent(self, domains_dir: Path) -> None:
        """Reject single ../ traversal."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("../etc/passwd")

    def test_path_traversal_blocked_encoded(self, domains_dir: Path) -> None:
        """Reject URL-encoded traversal (..%2F)."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("..%2F..%2Fetc%2Fpasswd")

    def test_absolute_path_blocked(self, domains_dir: Path) -> None:
        """Reject absolute paths that escape base directory."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("/etc/passwd")

    def test_absolute_path_to_existing_file_blocked(self, domains_dir: Path) -> None:
        """Reject absolute paths even to existing files."""
        # Create a spec.yaml at an absolute path
        abs_spec = domains_dir / "absolute_test" / "spec.yaml"
        abs_spec.parent.mkdir(exist_ok=True)
        abs_spec.write_text("domain: {id: test}")
        # Try to load using absolute path - should fail
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain(str(abs_spec.parent))

    def test_empty_domain_id_rejected(self, domains_dir: Path) -> None:
        """Reject empty domain_id."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("")

    def test_whitespace_domain_id_rejected(self, domains_dir: Path) -> None:
        """Reject whitespace-only domain_id."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("   ")

    def test_dot_domain_id_rejected(self, domains_dir: Path) -> None:
        """Reject single dot domain_id."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain(".")

    def test_double_dot_domain_id_rejected(self, domains_dir: Path) -> None:
        """Reject double dot domain_id."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("..")

    def test_hidden_directory_traversal(self, domains_dir: Path) -> None:
        """Reject traversal via hidden directories."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain(".hidden/../../../etc/passwd")

    def test_null_byte_injection(self, domains_dir: Path) -> None:
        """Reject null byte injection attempts."""
        with pytest.raises(DomainNotFoundError):
            DomainPackLoader(str(domains_dir)).load_domain("testdomain\x00../../etc/passwd")

    def test_valid_domain_loads_successfully(self, domains_dir: Path) -> None:
        """Verify valid domain still loads correctly after security checks."""
        loader = DomainPackLoader(str(domains_dir))
        spec = loader.load_domain("testdomain")
        assert spec.domain.id == "testdomain"

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_spec_file_rejected(self, domains_dir: Path) -> None:
        """Reject spec.yaml that is a symlink."""
        # Create a symlink domain
        symlink_domain = domains_dir / "symlink_domain"
        symlink_domain.mkdir()
        real_spec = domains_dir / "testdomain" / "spec.yaml"
        symlink_spec = symlink_domain / "spec.yaml"
        symlink_spec.symlink_to(real_spec)

        with pytest.raises(DomainNotFoundError, match="symlink"):
            DomainPackLoader(str(domains_dir)).load_domain("symlink_domain")


class TestFileSizeLimit:
    """Tests for file size limit protection (AUD9-1-MED-2)."""

    def test_oversized_spec_rejected(self, domains_dir: Path) -> None:
        """Reject spec files larger than MAX_SPEC_BYTES."""
        oversized_domain = domains_dir / "oversized"
        oversized_domain.mkdir()
        oversized_spec = oversized_domain / "spec.yaml"
        # Create a file larger than the limit
        oversized_spec.write_text("x" * (MAX_SPEC_BYTES + 1))

        with pytest.raises(DomainSpecError, match="exceeds maximum size"):
            DomainPackLoader(str(domains_dir)).load_domain("oversized")

    def test_normal_size_spec_accepted(self, domains_dir: Path) -> None:
        """Accept spec files within size limit."""
        loader = DomainPackLoader(str(domains_dir))
        spec = loader.load_domain("testdomain")
        assert spec is not None


def test_nonexistent_domain(domains_dir: Path) -> None:
    with pytest.raises(DomainNotFoundError):
        DomainPackLoader(str(domains_dir)).load_domain("nope")
