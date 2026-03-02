# engine/config/loader.py
"""
Domain pack loader.
Discovers, validates, caches, and hot-reloads domain spec YAML files.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)


class DomainNotFoundError(Exception):
    """Raised when a requested domain spec does not exist."""


class DomainSpecError(Exception):
    """Raised when a domain spec fails validation."""


class DomainPackLoader:
    """
    Loads and caches domain spec YAML files with hot-reload support.

    Thread-safety note: The _cache dict is designed for single-threaded
    initialization at startup. It is populated during application bootstrap
    before any concurrent requests are served. In multi-worker deployments,
    each worker has its own DomainPackLoader instance with isolated cache.
    Do NOT share a DomainPackLoader instance across threads or async tasks
    that may mutate the cache concurrently.
    """

    def __init__(self, config_path: str | None = None) -> None:
        raw = config_path or os.getenv("DOMAIN_SPECS_PATH") or "domains"
        self._base_path = Path(raw).resolve()
        # NOTE: Cache is NOT thread-safe. See class docstring for usage constraints.
        self._cache: dict[str, tuple[DomainSpec, float]] = {}

    def load_domain(self, domain_id: str) -> DomainSpec:
        """Load and validate a domain spec with mtime-based cache invalidation."""
        spec_path = self._resolve_spec_path(domain_id)
        current_mtime = spec_path.stat().st_mtime

        if domain_id in self._cache:
            cached_spec, cached_mtime = self._cache[domain_id]
            if cached_mtime >= current_mtime:
                return cached_spec
            logger.info("Domain spec changed on disk, reloading: %s", domain_id)

        spec = self._load_and_validate(spec_path, domain_id)
        self._cache[domain_id] = (spec, current_mtime)
        return spec

    def invalidate(self, domain_id: str | None = None) -> None:
        """Force cache invalidation."""
        if domain_id:
            self._cache.pop(domain_id, None)
        else:
            self._cache.clear()

    def list_domains(self) -> list[str]:
        """Discover all domain directories containing spec.yaml."""
        if not self._base_path.is_dir():
            return []
        return [d.name for d in sorted(self._base_path.iterdir()) if d.is_dir() and (d / "spec.yaml").exists()]

    def _resolve_spec_path(self, domain_id: str) -> Path:
        """Resolve and validate spec file path — prevents path traversal."""
        candidate = (self._base_path / domain_id / "spec.yaml").resolve()
        if not str(candidate).startswith(str(self._base_path)):
            raise DomainNotFoundError(f"Invalid domain path: {domain_id!r} resolves outside base directory")
        if not candidate.exists():
            raise DomainNotFoundError(f"Domain spec not found: {candidate}")
        return candidate

    def _load_and_validate(self, path: Path, domain_id: str) -> DomainSpec:
        """Load YAML and validate against DomainSpec schema."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise DomainSpecError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise DomainSpecError(f"Domain spec must be a YAML mapping, got {type(raw).__name__}")

        try:
            return DomainSpec.model_validate(raw)
        except PydanticValidationError as exc:
            raise DomainSpecError(f"Domain '{domain_id}' validation failed:\n{exc}") from exc
