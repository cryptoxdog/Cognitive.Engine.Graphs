"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, config]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine/config/loader.py — DomainPackLoader.
Target Coverage: 85%+
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.config.loader import (
    MAX_SPEC_BYTES,
    DomainNotFoundError,
    DomainPackLoader,
    DomainSpecError,
)

# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestDomainPackLoaderInit:
    """Test DomainPackLoader initialization."""

    def test_init_with_explicit_path(self, tmp_path: Path) -> None:
        """DomainPackLoader resolves explicit config_path."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        assert loader._base_path == tmp_path.resolve()

    def test_init_from_env_var(self, tmp_path: Path) -> None:
        """DomainPackLoader reads DOMAIN_SPECS_PATH env var."""
        with patch.dict(os.environ, {"DOMAIN_SPECS_PATH": str(tmp_path)}):
            loader = DomainPackLoader()
            assert loader._base_path == tmp_path.resolve()

    def test_init_default_path(self) -> None:
        """DomainPackLoader defaults to 'domains' when no path given."""
        with patch.dict(os.environ, {}, clear=True):
            loader = DomainPackLoader()
            assert loader._base_path == Path("domains").resolve()


@pytest.mark.unit
class TestResolveSpecPath:
    """Test _resolve_spec_path security checks."""

    def test_blocks_empty_domain_id(self, tmp_path: Path) -> None:
        """Empty domain_id raises DomainNotFoundError."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainNotFoundError, match="cannot be empty"):
            loader._resolve_spec_path("")

    def test_blocks_whitespace_domain_id(self, tmp_path: Path) -> None:
        """Whitespace-only domain_id raises DomainNotFoundError."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainNotFoundError, match="cannot be empty"):
            loader._resolve_spec_path("   ")

    def test_blocks_null_bytes(self, tmp_path: Path) -> None:
        """Null byte in domain_id raises DomainNotFoundError."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainNotFoundError, match="null byte"):
            loader._resolve_spec_path("evil\x00domain")

    def test_blocks_path_traversal(self, tmp_path: Path) -> None:
        """Path traversal attempts raise DomainNotFoundError."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainNotFoundError):
            loader._resolve_spec_path("../../etc/passwd")

    def test_blocks_symlinks(self, tmp_path: Path) -> None:
        """Symlinked spec.yaml raises DomainNotFoundError."""
        domain_dir = tmp_path / "evil_domain"
        domain_dir.mkdir()
        target = tmp_path / "real_spec.yaml"
        target.write_text("domain: {id: evil}")
        symlink = domain_dir / "spec.yaml"
        symlink.symlink_to(target)
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainNotFoundError, match="symlink"):
            loader._resolve_spec_path("evil_domain")

    def test_missing_spec_file_raises(self, tmp_path: Path) -> None:
        """Non-existent spec.yaml raises DomainNotFoundError."""
        domain_dir = tmp_path / "missing"
        domain_dir.mkdir()
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainNotFoundError, match="not found"):
            loader._resolve_spec_path("missing")


@pytest.mark.unit
class TestLoadAndValidate:
    """Test _load_and_validate."""

    def test_oversized_file_raises(self, tmp_path: Path) -> None:
        """File exceeding MAX_SPEC_BYTES raises DomainSpecError."""
        domain_dir = tmp_path / "big"
        domain_dir.mkdir()
        spec_file = domain_dir / "spec.yaml"
        spec_file.write_text("x" * (MAX_SPEC_BYTES + 1))
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainSpecError, match="exceeds maximum size"):
            loader._load_and_validate(spec_file, "big")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """Malformed YAML raises DomainSpecError."""
        domain_dir = tmp_path / "bad_yaml"
        domain_dir.mkdir()
        spec_file = domain_dir / "spec.yaml"
        spec_file.write_text("{{{{invalid yaml:::::")
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainSpecError, match="Invalid YAML"):
            loader._load_and_validate(spec_file, "bad_yaml")

    def test_non_dict_yaml_raises(self, tmp_path: Path) -> None:
        """YAML that parses to non-dict raises DomainSpecError."""
        domain_dir = tmp_path / "list_yaml"
        domain_dir.mkdir()
        spec_file = domain_dir / "spec.yaml"
        spec_file.write_text("- item1\n- item2")
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainSpecError, match="must be a YAML mapping"):
            loader._load_and_validate(spec_file, "list_yaml")

    def test_invalid_schema_raises(self, tmp_path: Path) -> None:
        """Valid YAML but invalid DomainSpec schema raises DomainSpecError."""
        domain_dir = tmp_path / "bad_schema"
        domain_dir.mkdir()
        spec_file = domain_dir / "spec.yaml"
        spec_file.write_text("domain: {id: test}")
        loader = DomainPackLoader(config_path=str(tmp_path))
        with pytest.raises(DomainSpecError, match="validation failed"):
            loader._load_and_validate(spec_file, "bad_schema")


@pytest.mark.unit
class TestLoadDomain:
    """Test load_domain caching behavior."""

    def test_caches_on_first_load(self, tmp_path: Path) -> None:
        """load_domain caches spec on first load."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        mock_spec = MagicMock()
        with (
            patch.object(loader, "_resolve_spec_path") as mock_resolve,
            patch.object(loader, "_load_and_validate", return_value=mock_spec),
        ):
            mock_path = MagicMock()
            mock_path.stat.return_value.st_mtime = 1000.0
            mock_resolve.return_value = mock_path
            result = loader.load_domain("test_domain")
            assert result == mock_spec
            assert "test_domain" in loader._cache

    def test_returns_cached_when_mtime_unchanged(self, tmp_path: Path) -> None:
        """load_domain returns cached spec when mtime is unchanged."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        mock_spec = MagicMock()
        loader._cache["cached"] = (mock_spec, 1000.0, 0.0)
        with patch.object(loader, "_resolve_spec_path") as mock_resolve:
            mock_path = MagicMock()
            mock_path.stat.return_value.st_mtime = 1000.0
            mock_resolve.return_value = mock_path
            result = loader.load_domain("cached")
            assert result == mock_spec

    def test_reloads_when_mtime_changes(self, tmp_path: Path) -> None:
        """load_domain reloads when file mtime changes."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        old_spec = MagicMock()
        new_spec = MagicMock()
        loader._cache["stale"] = (old_spec, 1000.0, 0.0)
        with (
            patch.object(loader, "_resolve_spec_path") as mock_resolve,
            patch.object(loader, "_load_and_validate", return_value=new_spec),
        ):
            mock_path = MagicMock()
            mock_path.stat.return_value.st_mtime = 2000.0
            mock_resolve.return_value = mock_path
            result = loader.load_domain("stale")
            assert result == new_spec


@pytest.mark.unit
class TestListDomains:
    """Test list_domains discovery."""

    def test_discovers_domain_dirs(self, tmp_path: Path) -> None:
        """list_domains finds directories with spec.yaml."""
        for name in ["alpha", "beta"]:
            d = tmp_path / name
            d.mkdir()
            (d / "spec.yaml").write_text("placeholder")
        (tmp_path / "no_spec_dir").mkdir()
        loader = DomainPackLoader(config_path=str(tmp_path))
        domains = loader.list_domains()
        assert "alpha" in domains
        assert "beta" in domains
        assert "no_spec_dir" not in domains

    def test_returns_empty_for_nonexistent_path(self) -> None:
        """list_domains returns [] for non-existent base path."""
        loader = DomainPackLoader(config_path="/nonexistent/path/xyz")
        assert loader.list_domains() == []


@pytest.mark.unit
class TestInvalidate:
    """Test cache invalidation."""

    def test_invalidate_single_domain(self, tmp_path: Path) -> None:
        """invalidate(domain_id) clears single entry."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        loader._cache["d1"] = (MagicMock(), 100.0)
        loader._cache["d2"] = (MagicMock(), 200.0)
        loader.invalidate("d1")
        assert "d1" not in loader._cache
        assert "d2" in loader._cache

    def test_invalidate_all(self, tmp_path: Path) -> None:
        """invalidate() with no args clears entire cache."""
        loader = DomainPackLoader(config_path=str(tmp_path))
        loader._cache["d1"] = (MagicMock(), 100.0)
        loader._cache["d2"] = (MagicMock(), 200.0)
        loader.invalidate()
        assert len(loader._cache) == 0
