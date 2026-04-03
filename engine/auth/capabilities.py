"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [auth]
tags: [auth, capability, sel4, wave3]
owner: engine-team
status: active
--- /L9_META ---

Capability-based access control for CEG (Wave 3, seL4-inspired).

Implements:
- W3-02: Domain-spec capability model with derivation trees
- W3-03: Action-level permission mapping
- W3-04: Capability delegation/revocation with audit trail

seL4 Analogue
--------------
Every action requires an explicit, unforgeable capability token. Capabilities
form a derivation tree where children cannot exceed parent rights (monotonicity
invariant). Revocation is recursive — revoking a parent invalidates all
descendants (CNode_Revoke).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── W3-03: Action-Level Permission Map ──────────────────────────
# Maps every engine action to a required capability string.
# Used by check_action_permission() to enforce at handler entry.

ACTION_PERMISSION_MAP: dict[str, str] = {
    "match": "match:read",
    "sync": "sync:write",
    "enrich": "sync:write",
    "outcomes": "sync:write",
    "admin": "admin:write",
    "kge_search": "admin:kge",
    "calibration_run": "admin:write",
    "score_feedback": "admin:write",
    "apply_weight_proposal": "admin:write",
    "resolve": "match:read",
    "health": "match:read",
    "healthcheck": "match:read",
}

# All known capability action strings
ALL_CAPABILITY_ACTIONS: frozenset[str] = frozenset(ACTION_PERMISSION_MAP.values())


# ── Data Classes ────────────────────────────────────────────────


@dataclass
class Capability:
    """An unforgeable, typed authority token (seL4 CTE analogue).

    Attributes
    ----------
    tenant_id : str
        The tenant this capability belongs to.
    domain_id : str
        The domain scope (``"*"`` = all domains).
    allowed_actions : frozenset[str]
        Set of permitted capability action strings.
    capability_id : str
        Unique, randomly-generated identifier.
    granted_by : str
        ``capability_id`` of the parent (or ``"ROOT"``).
    granted_at : float
        Unix timestamp when created.
    expires_at : float
        Unix timestamp after which expired (0 = never).
    proof_hash : str
        Integrity hash over immutable fields.
    revoked : bool
        Whether explicitly revoked.
    """

    tenant_id: str
    domain_id: str
    allowed_actions: frozenset[str]
    capability_id: str = field(default_factory=lambda: secrets.token_hex(16))
    granted_by: str = "ROOT"
    granted_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    proof_hash: str = field(default="", init=False)
    revoked: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_actions", frozenset(self.allowed_actions))
        self.proof_hash = self._compute_proof_hash()

    def _compute_proof_hash(self) -> str:
        """Deterministic integrity hash over immutable fields."""
        payload = (
            f"{self.capability_id}:{self.tenant_id}:{self.domain_id}:"
            f"{sorted(self.allowed_actions)}:{self.granted_by}:{self.granted_at}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def is_valid_hash(self) -> bool:
        return self.proof_hash == self._compute_proof_hash()

    def is_expired(self) -> bool:
        if self.expires_at == 0.0:
            return False
        return time.time() > self.expires_at

    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired() and self.is_valid_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "tenant_id": self.tenant_id,
            "domain_id": self.domain_id,
            "allowed_actions": sorted(self.allowed_actions),
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "proof_hash": self.proof_hash,
            "revoked": self.revoked,
            "is_active": self.is_active(),
        }


@dataclass
class CapabilityDerivation:
    """Records a parent → child derivation event (seL4 CDT node)."""

    parent_capability: Capability
    child_capability: Capability
    scope_restriction: dict[str, Any]
    derivation_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_capability_id": self.parent_capability.capability_id,
            "child_capability_id": self.child_capability.capability_id,
            "scope_restriction": self.scope_restriction,
            "derivation_time": self.derivation_time,
        }


# ── CapabilityValidator ─────────────────────────────────────────


class CapabilityValidator:
    """Validates, derives, and revokes capabilities.

    Maintains an in-process registry of all issued capabilities and their
    derivation trees. Enforces the seL4 monotonicity invariant on derivation
    and recursive revocation on CNode_Revoke.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Capability] = {}
        self._derivations: dict[str, CapabilityDerivation] = {}

    def register(self, capability: Capability) -> None:
        """Register a capability (e.g. root capabilities from config)."""
        self._registry[capability.capability_id] = capability

    def validate_action(self, capability: object, action: str, tenant: str) -> bool:
        """Return True if capability authorises ``action`` for ``tenant``.

        Checks: registered, integrity, active, tenant match, action allowed.
        """
        if not isinstance(capability, Capability):
            return False
        if not capability.is_valid_hash():
            return False
        if not capability.is_active():
            return False
        if capability.tenant_id not in {tenant, "*"}:
            return False
        if action not in capability.allowed_actions:
            return False
        registered = self._registry.get(capability.capability_id)
        return not (registered is None or registered.revoked)

    def derive_capability(
        self,
        parent: Capability,
        scope_restriction: dict[str, Any],
        expires_in_seconds: float = 0.0,
    ) -> Capability:
        """Derive a more-restricted child capability (seL4 CNode_Mint).

        Enforces monotonicity: child rights ⊆ parent rights.
        """
        if not parent.is_active():
            msg = f"Cannot derive from inactive capability {parent.capability_id!r}"
            raise PermissionError(msg)

        # Monotonicity: domain
        child_domain = scope_restriction.get("domain_id", parent.domain_id)
        if parent.domain_id not in {"*", child_domain}:
            msg = (
                f"Monotonicity violation: parent domain '{parent.domain_id}' "
                f"cannot derive child domain '{child_domain}'"
            )
            raise PermissionError(msg)

        # Monotonicity: actions
        child_actions_raw = scope_restriction.get("allowed_actions", parent.allowed_actions)
        child_actions_iterable: frozenset[str] | set[str]
        if isinstance(child_actions_raw, frozenset):
            child_actions_iterable = child_actions_raw
        else:
            child_actions_iterable = set(child_actions_raw)
        child_actions = frozenset(child_actions_iterable)
        excess = child_actions - parent.allowed_actions
        if excess:
            msg = f"Monotonicity violation: child requests actions {excess} not in parent {parent.capability_id!r}"
            raise PermissionError(msg)

        # Expiry: child cannot outlive parent
        child_expires = time.time() + expires_in_seconds if expires_in_seconds > 0 else 0.0
        if parent.expires_at > 0 and (child_expires == 0 or child_expires > parent.expires_at):
            child_expires = parent.expires_at

        child = Capability(
            tenant_id=parent.tenant_id,
            domain_id=child_domain,
            allowed_actions=child_actions,
            granted_by=parent.capability_id,
            expires_at=child_expires,
        )

        derivation = CapabilityDerivation(
            parent_capability=parent,
            child_capability=child,
            scope_restriction=scope_restriction,
        )

        self._registry[child.capability_id] = child
        self._derivations[child.capability_id] = derivation
        return child

    def revoke_capability(self, capability_id: str) -> bool:
        """Revoke a capability and all descendants (seL4 CNode_Revoke)."""
        cap = self._registry.get(capability_id)
        if cap is None:
            return False

        cap.revoked = True

        children = [
            d.child_capability for d in self._derivations.values() if d.parent_capability.capability_id == capability_id
        ]
        for child in children:
            self.revoke_capability(child.capability_id)

        return True

    def check_derivation_chain(self, capability: Capability) -> list[Capability]:
        """Return full derivation chain from root to the given capability."""
        chain: list[Capability] = [capability]
        current = capability
        visited: set[str] = {capability.capability_id}

        while current.granted_by != "ROOT":
            parent = self._registry.get(current.granted_by)
            if parent is None:
                break
            if parent.capability_id in visited:
                break
            visited.add(parent.capability_id)
            chain.append(parent)
            current = parent

        chain.reverse()
        return chain

    def audit_summary(self) -> dict[str, Any]:
        """Summary of all registered capabilities for audit."""
        active = sum(1 for c in self._registry.values() if c.is_active())
        revoked = sum(1 for c in self._registry.values() if c.revoked)
        expired = sum(1 for c in self._registry.values() if not c.revoked and c.is_expired())
        return {
            "total_registered": len(self._registry),
            "active": active,
            "revoked": revoked,
            "expired": expired,
            "derivations": len(self._derivations),
        }


# ── CapabilitySet (compiled from domain spec) ──────────────────


class CapabilitySet:
    """Compiled capability set from a domain spec's ``capabilities`` section.

    Built at domain-spec load time by the loader, consulted at handler entry.
    """

    def __init__(self, capabilities: list[dict[str, Any]] | None = None) -> None:
        # Internal mapping: action → set of allowed tenant IDs (or {"*"})
        self._action_subjects: dict[str, set[str]] = {}
        for cap in capabilities or []:
            for action in cap.get("actions", []):
                subjects = self._action_subjects.setdefault(action, set())
                for subj in cap.get("allowed_subjects", []):
                    subjects.add(subj)

    def has_capability(self, tenant: str, action: str) -> bool:
        """Check if ``tenant`` holds the required capability for ``action``.

        Returns True if:
        - No capabilities are defined (open access)
        - The action is not in the capability set (no restriction)
        - The tenant is in the allowed subjects for the action
        - Wildcard ``"*"`` is in the allowed subjects
        """
        if not self._action_subjects:
            return True
        subjects = self._action_subjects.get(action)
        if subjects is None:
            return True
        return tenant in subjects or "*" in subjects

    def to_dict(self) -> dict[str, Any]:
        return {action: sorted(subjects) for action, subjects in self._action_subjects.items()}


# ── W3-03: Action Permission Check ─────────────────────────────


def check_action_permission(tenant: str, action: str, capability_set: CapabilitySet | None) -> bool:
    """Check whether ``tenant`` is authorized for ``action`` via the capability set.

    Maps the engine action to a required capability string via ACTION_PERMISSION_MAP,
    then checks the domain-spec CapabilitySet.

    Returns True if authorized (or if no capability set is configured).
    """
    if capability_set is None:
        return True
    required = ACTION_PERMISSION_MAP.get(action)
    if required is None:
        # Unknown action — deny by default in strict mode
        return False
    return capability_set.has_capability(tenant, required)


# ── Module-level singleton validator ────────────────────────────

_capability_validator: CapabilityValidator | None = None


def get_capability_validator() -> CapabilityValidator:
    """Return the module-level CapabilityValidator singleton."""
    global _capability_validator
    if _capability_validator is None:
        _capability_validator = CapabilityValidator()
    return _capability_validator


def reset_capability_validator() -> None:
    """Reset the singleton (for testing)."""
    global _capability_validator
    _capability_validator = None
