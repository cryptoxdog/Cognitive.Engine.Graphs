"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [config, domain-loader]
owner: engine-team
status: active
--- /L9_META ---

Domain pack loader.
Discovers, validates, caches, and hot-reloads domain spec YAML files.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)

# Maximum spec file size (5MB) to prevent OOM on malicious/corrupted files
MAX_SPEC_BYTES = 5 * 1024 * 1024


class DomainNotFoundError(Exception):
    """Raised when a requested domain spec does not exist."""


class DomainSpecError(Exception):
    """Raised when a domain spec fails validation."""


class DomainPackLoader:
    """
    Loads and caches domain spec YAML files with hot-reload support.

    Thread-safety: Cache operations are protected by a threading.Lock.
    TTL-based invalidation avoids per-request stat() syscalls.
    LRU eviction keeps cache bounded (configurable via DOMAIN_CACHE_MAX_SIZE).
    """

    def __init__(self, config_path: str | None = None) -> None:
        raw = config_path or os.getenv("DOMAIN_SPECS_PATH") or "domains"
        self._base_path = Path(raw).resolve()
        self._cache: dict[str, tuple[DomainSpec, float, float]] = {}  # domain_id → (spec, mtime, cached_at)
        self._lock = threading.Lock()
        self._max_size = int(os.getenv("DOMAIN_CACHE_MAX_SIZE", "100"))
        self._ttl_seconds = float(os.getenv("DOMAIN_CACHE_TTL_SECONDS", "30"))

    def load_domain(self, domain_id: str) -> DomainSpec:
        """Load and validate a domain spec with mtime-based cache invalidation."""
        spec_path = self._resolve_spec_path(domain_id)

        with self._lock:
            if domain_id in self._cache:
                cached_spec, cached_mtime, cached_at = self._cache[domain_id]
                # Skip stat() if within TTL
                if (time.monotonic() - cached_at) < self._ttl_seconds:
                    return cached_spec
                # TTL expired — check mtime
                current_mtime = spec_path.stat().st_mtime
                if cached_mtime >= current_mtime:
                    # Refresh cached_at timestamp
                    self._cache[domain_id] = (cached_spec, cached_mtime, time.monotonic())
                    return cached_spec
                logger.info("Domain spec changed on disk, reloading: %s", domain_id)
            else:
                current_mtime = spec_path.stat().st_mtime

            spec = self._load_and_validate(spec_path, domain_id)

            # LRU eviction: if cache is full, remove oldest entry
            if len(self._cache) >= self._max_size and domain_id not in self._cache:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][2])
                del self._cache[oldest_key]
                logger.debug("Evicted oldest domain cache entry: %s", oldest_key)

            self._cache[domain_id] = (spec, current_mtime, time.monotonic())
            return spec

    def invalidate(self, domain_id: str | None = None) -> None:
        """Force cache invalidation."""
        with self._lock:
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
        """Resolve and validate spec file path — prevents path traversal and symlink attacks."""
        # Reject empty or whitespace-only domain_id
        if not domain_id or not domain_id.strip():
            raise DomainNotFoundError("Domain ID cannot be empty")

        # Reject null bytes (potential injection attack)
        if "\x00" in domain_id:
            raise DomainNotFoundError(f"Invalid domain ID: {domain_id!r} contains null byte")

        # Reject absolute domain IDs — only relative IDs are valid
        if Path(domain_id).is_absolute():
            raise DomainNotFoundError(f"Invalid domain ID: {domain_id!r} must be a relative path")

        candidate = (self._base_path / domain_id / "spec.yaml").resolve()

        # Check for symlinks before resolving - reject symlinked spec files
        raw_path = self._base_path / domain_id / "spec.yaml"
        if raw_path.is_symlink():
            raise DomainNotFoundError(f"Invalid domain path: {domain_id!r} spec.yaml is a symlink")

        # Verify resolved path is within base directory using proper path ancestry check
        try:
            candidate.relative_to(self._base_path.resolve())
        except ValueError as exc:
            raise DomainNotFoundError(f"Invalid domain path: {domain_id!r} resolves outside base directory") from exc

        if not candidate.exists():
            raise DomainNotFoundError(f"Domain spec not found: {candidate}")

        return candidate

    def _load_and_validate(self, path: Path, domain_id: str) -> DomainSpec:
        """Load YAML and validate against DomainSpec schema."""
        # Check file size before reading to prevent OOM
        file_size = path.stat().st_size
        if file_size > MAX_SPEC_BYTES:
            raise DomainSpecError(
                f"Domain spec {domain_id} exceeds maximum size: {file_size} bytes > {MAX_SPEC_BYTES} bytes"
            )

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
