# engine/config/loader.py
"""
Domain pack loader.
Loads spec.yaml from filesystem, validates against schema, returns DomainSpec.
"""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from engine.config.schema import DomainSpec

logger = logging.getLogger(__name__)


class DomainPackLoader:
    """Load and validate domain pack YAML specifications."""

    def __init__(self, domains_root: Path = Path("domains")):
        """
        Initialize loader.

        Args:
            domains_root: Root directory containing domain pack subdirectories
        """
        self.domains_root = domains_root
        self._cache: dict[str, DomainSpec] = {}

    def load_domain(self, domain_id: str, use_cache: bool = True) -> DomainSpec:
        """
        Load domain specification by ID.

        Args:
            domain_id: Domain identifier (subdirectory name)
            use_cache: Use cached spec if available

        Returns:
            Validated DomainSpec

        Raises:
            FileNotFoundError: If spec.yaml not found
            ValidationError: If spec violates schema
            yaml.YAMLError: If YAML syntax invalid
        """
        if use_cache and domain_id in self._cache:
            logger.debug(f"Using cached spec for domain '{domain_id}'")
            return self._cache[domain_id]

        spec_path = self.domains_root / domain_id / "spec.yaml"

        if not spec_path.exists():
            raise FileNotFoundError(
                f"Domain spec not found: {spec_path}\nExpected structure: {self.domains_root}/{domain_id}/spec.yaml"
            )

        logger.info(f"Loading domain pack from {spec_path}")

        try:
            with open(spec_path, encoding="utf-8") as f:
                raw_spec = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"YAML syntax error in {spec_path}: {e}")
            raise

        try:
            spec = DomainSpec.model_validate(raw_spec)
        except ValidationError as e:
            logger.error(f"Validation error in {spec_path}:")
            logger.error(str(e))
            raise

        # Verify domain.id matches directory name
        if spec.domain.id != domain_id:
            logger.warning(
                f"Domain ID mismatch: directory='{domain_id}', spec.domain.id='{spec.domain.id}'. Using directory name."
            )

        self._cache[domain_id] = spec
        logger.info(f"Successfully loaded domain '{spec.domain.name}' v{spec.domain.version}")

        return spec

    def list_domains(self) -> list[str]:
        """
        List all available domain IDs.

        Returns:
            List of domain directory names containing spec.yaml
        """
        if not self.domains_root.exists():
            return []

        domains = []
        for path in self.domains_root.iterdir():
            if path.is_dir() and (path / "spec.yaml").exists():
                domains.append(path.name)

        return sorted(domains)

    def reload_domain(self, domain_id: str) -> DomainSpec:
        """
        Force reload domain from disk (bypass cache).

        Args:
            domain_id: Domain identifier

        Returns:
            Freshly loaded DomainSpec
        """
        if domain_id in self._cache:
            del self._cache[domain_id]

        return self.load_domain(domain_id, use_cache=False)

    def get_custom_query_path(self, domain_id: str, query_name: str) -> Path | None:
        """
        Get path to custom Cypher query file.

        Args:
            domain_id: Domain identifier
            query_name: Query file name (without .cypher extension)

        Returns:
            Path to .cypher file if exists, else None
        """
        query_path = self.domains_root / domain_id / "queries" / f"{query_name}.cypher"
        return query_path if query_path.exists() else None

    def load_custom_query(self, domain_id: str, query_name: str) -> str | None:
        """
        Load custom Cypher query content.

        Args:
            domain_id: Domain identifier
            query_name: Query file name (without .cypher extension)

        Returns:
            Cypher query string if file exists, else None
        """
        query_path = self.get_custom_query_path(domain_id, query_name)
        if not query_path:
            return None

        with open(query_path, encoding="utf-8") as f:
            return f.read()
