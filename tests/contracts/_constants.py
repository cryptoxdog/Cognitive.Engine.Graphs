"""
Shared constants for contract validation tests.

Imported by test modules directly; conftest.py imports these for fixture setup.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_ROOT = REPO_ROOT / "docs" / "contracts"

KNOWN_ACTIONS = {"match", "sync", "admin", "outcomes", "resolve", "health", "healthcheck", "enrich"}

OUTCOME_VALUES = {"success", "failure", "partial"}

REQUIRED_ENV_VARS = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "REDIS_URL", "API_KEY"]

FORBIDDEN_PROD_SECRETS: dict[str, list[str]] = {
    "NEO4J_PASSWORD": ["password", "change-me-in-production"],
    "API_KEY": ["change-me-in-production", "dev-key-sha256-not-for-production"],
}

PACKET_REQUIRED_FIELDS: dict[str, list[str]] = {
    "REQUEST": ["packet_id", "packet_type", "action", "tenant", "payload", "content_hash"],
    "RESPONSE": ["packet_id", "packet_type", "action", "tenant", "payload", "content_hash"],
}

ACTION_PERMISSION_MAP: dict[str, str] = {
    "match": "match:read",
    "sync": "sync:write",
    "admin": "admin:write",
    "outcomes": "sync:write",
    "resolve": "match:read",
    "enrich": "sync:write",
}
