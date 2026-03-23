"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [intake]
tags: [intake, vertical, discovery]
owner: engine-team
status: active
--- /L9_META ---

Vertical discovery — identifies standard fields for a customer vertical.

Deterministic implementation: looks up domain YAML by vertical keyword,
extracts ontology properties tagged as vertical-standard. No external
API calls — actual Sonar discovery happens in EIE.
"""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml

from engine.config.schema import DomainSpec

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class VerticalDiscoveryResult:
    """Result of vertical field discovery."""

    def __init__(
        self,
        *,
        vertical_fields: list[str],
        vertical_name: str,
        discovery_suggested: bool = False,
    ) -> None:
        self.vertical_fields = vertical_fields
        self.vertical_name = vertical_name
        self.discovery_suggested = discovery_suggested

    def __repr__(self) -> str:
        return (
            f"VerticalDiscoveryResult(vertical={self.vertical_name!r}, "
            f"fields={len(self.vertical_fields)}, "
            f"discovery_suggested={self.discovery_suggested})"
        )


_VERTICAL_KEYWORDS: dict[str, str] = {
    "plastic": "plasticos",
    "recycl": "plasticos",
    "polymer": "plasticos",
    "mortgage": "mortgage_brokerage",
    "lending": "mortgage_brokerage",
    "healthcare": "healthcare_referral",
    "medical": "healthcare_referral",
    "freight": "freight_matching",
    "logistics": "freight_matching",
    "shipping": "freight_matching",
    "legal": "legal_discovery",
    "roofing": "roofing_company",
}


def _detect_vertical(business_profile: str) -> str | None:
    """Match business profile text to a known vertical keyword."""
    profile_lower = business_profile.lower()
    for keyword, vertical in _VERTICAL_KEYWORDS.items():
        if keyword in profile_lower:
            return vertical
    return None


def _load_domain_fields(
    vertical: str,
    domains_dir: str = "domains",
) -> list[str]:
    """Extract property names from the domain YAML for a given vertical."""
    domains_path = Path(domains_dir)
    candidates = [
        domains_path / f"{vertical}_domain_spec.yaml",
        domains_path / vertical / "spec.yaml",
        domains_path / f"{vertical}_spec.yaml",
    ]
    for spec_path in candidates:
        if spec_path.exists():
            with spec_path.open() as fh:
                raw = yaml.safe_load(fh)
            if raw and "ontology" in raw:
                fields: list[str] = []
                nodes = raw["ontology"].get("nodes", [])
                if isinstance(nodes, dict):
                    node_list: list[dict[str, object]] = []
                    for group in nodes.values():
                        if isinstance(group, list):
                            node_list.extend(group)
                    nodes = node_list
                for node in nodes:
                    for prop in node.get("properties", []):
                        name = prop.get("name", "")
                        if name:
                            fields.append(name)
                logger.info(
                    "vertical_fields_loaded",
                    vertical=vertical,
                    field_count=len(fields),
                    source=str(spec_path),
                )
                return fields
    return []


def discover_vertical_fields(
    business_profile: str,
    spec: DomainSpec | None = None,
    *,
    domains_dir: str = "domains",
) -> VerticalDiscoveryResult:
    """
    Discover vertical-standard fields from business profile.

    Parameters
    ----------
    business_profile:
        Free-text description of the customer's business.
    spec:
        Optional pre-loaded DomainSpec (takes priority over YAML lookup).
    domains_dir:
        Path to the domains directory for YAML lookups.

    Returns
    -------
    VerticalDiscoveryResult with field names and discovery suggestion flag.
    """
    vertical = _detect_vertical(business_profile)

    if vertical is None:
        logger.info("vertical_not_detected", profile_snippet=business_profile[:80])
        return VerticalDiscoveryResult(
            vertical_fields=[],
            vertical_name="unknown",
            discovery_suggested=True,
        )

    # If spec already provided, extract directly
    if spec is not None:
        fields = [prop.name for node in spec.ontology.nodes for prop in node.properties]
        return VerticalDiscoveryResult(
            vertical_fields=fields,
            vertical_name=vertical,
            discovery_suggested=False,
        )

    # Load from YAML
    fields = _load_domain_fields(vertical, domains_dir=domains_dir)
    if not fields:
        logger.info(
            "vertical_yaml_missing",
            vertical=vertical,
        )
        return VerticalDiscoveryResult(
            vertical_fields=[],
            vertical_name=vertical,
            discovery_suggested=True,
        )

    return VerticalDiscoveryResult(
        vertical_fields=fields,
        vertical_name=vertical,
        discovery_suggested=False,
    )
