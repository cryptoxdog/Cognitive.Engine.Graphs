"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api, config]
tags: [chassis, settings]
owner: platform-team
status: active
--- /L9_META ---

chassis/config.py — Engine-Agnostic Configuration Contracts

Defines the abstract DomainLoader protocol so the chassis and shared
middleware can reference domain configuration without importing
engine-specific schema models.

Each engine provides its own concrete loader:
    - Graph engine  → engine/config/loader.py (DomainPackLoader)
    - Enrich engine → enrich/config/loader.py (EnrichConfigLoader)
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

MAX_SPEC_BYTES = 5 * 1024 * 1024  # 5MB safety cap
SPEC_YAML = "spec.yaml"


class DomainNotFoundError(Exception):
    """Requested domain spec does not exist."""


class DomainSpecError(Exception):
    """Domain spec failed validation."""


class BaseDomainLoader(ABC):
    """
    Abstract contract for domain configuration loading.

    Concrete loaders implement load_raw() to return validated config.
    The chassis never sees engine-specific Pydantic models — it only
    needs list_domains() for admin endpoints and load_raw() for
    passing config through.
    """

    @abstractmethod
    def list_domains(self) -> list[str]:
        """Return available domain IDs."""

    @abstractmethod
    def load_raw(self, domain_id: str) -> dict[str, Any]:
        """Load domain config as a raw dict (engine validates further)."""

    def invalidate(self, domain_id: str | None = None) -> None:
        """Optional: cache invalidation."""


class YAMLDomainLoader(BaseDomainLoader):
    """
    Filesystem YAML loader with mtime caching.
    Reusable across any engine that stores domain specs as YAML.

    Layout expected:
        domains/{domain_id}/spec.yaml
    """

    def __init__(self, config_path: str | None = None) -> None:
        raw = config_path or os.getenv("DOMAIN_SPECS_PATH") or "domains"
        self._base_path = Path(raw).resolve()
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}

    def list_domains(self) -> list[str]:
        if not self._base_path.is_dir():
            return []
        return [d.name for d in sorted(self._base_path.iterdir()) if d.is_dir() and (d / SPEC_YAML).exists()]

    def load_raw(self, domain_id: str) -> dict[str, Any]:
        spec_path = self._resolve_path(domain_id)
        mtime = spec_path.stat().st_mtime

        if domain_id in self._cache:
            cached, cached_mtime = self._cache[domain_id]
            if cached_mtime >= mtime:
                return cached

        raw = self._read_yaml(spec_path, domain_id)
        self._cache[domain_id] = (raw, mtime)
        return raw

    def invalidate(self, domain_id: str | None = None) -> None:
        if domain_id:
            self._cache.pop(domain_id, None)
        else:
            self._cache.clear()

    def _resolve_path(self, domain_id: str) -> Path:
        if not domain_id or not domain_id.strip():
            raise DomainNotFoundError("Domain ID cannot be empty")
        if "\x00" in domain_id:
            raise DomainNotFoundError(f"Invalid domain ID: {domain_id!r}")

        candidate = (self._base_path / domain_id / SPEC_YAML).resolve()
        raw_path = self._base_path / domain_id / SPEC_YAML

        if raw_path.is_symlink():
            raise DomainNotFoundError(f"Symlinked spec rejected: {domain_id!r}")
        try:
            candidate.resolve().relative_to(self._base_path.resolve())
        except ValueError as exc:
            raise DomainNotFoundError(f"Domain path escapes base: {domain_id!r}") from exc
        if not candidate.exists():
            raise DomainNotFoundError(f"Domain spec not found: {candidate}")
        return candidate

    def _read_yaml(self, path: Path, domain_id: str) -> dict[str, Any]:
        if path.stat().st_size > MAX_SPEC_BYTES:
            raise DomainSpecError(f"Spec {domain_id} exceeds {MAX_SPEC_BYTES} bytes")
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise DomainSpecError(f"Invalid YAML in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise DomainSpecError(f"Spec must be YAML mapping, got {type(raw).__name__}")
        return raw
