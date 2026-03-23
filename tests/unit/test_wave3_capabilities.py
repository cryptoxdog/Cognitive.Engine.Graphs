"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, wave3, capability, auth]
owner: engine-team
status: active
--- /L9_META ---

Tests for Wave 3: Capability & Access Control (seL4-inspired).

Covers:
- W3-01: Tenant authorization enforcement (JWT allowed_tenants, bypass key)
- W3-02: Capability model (register, validate, derive, revoke, chain check)
- W3-03: Action-level permissions (ACTION_PERMISSION_MAP, check_action_permission)
- W3-04: Delegation/revocation audit trail
"""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from engine.auth.capabilities import (
    ACTION_PERMISSION_MAP,
    Capability,
    CapabilitySet,
    CapabilityValidator,
    check_action_permission,
    get_capability_validator,
    reset_capability_validator,
)
from engine.config.schema import CapabilitySpec, DomainSpec

# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_validator():
    """Reset the module-level singleton before each test."""
    reset_capability_validator()
    yield
    reset_capability_validator()


@pytest.fixture
def root_capability() -> Capability:
    """A root capability with broad permissions."""
    return Capability(
        tenant_id="acme",
        domain_id="*",
        allowed_actions=frozenset({"match:read", "sync:write", "admin:write"}),
    )


@pytest.fixture
def validator() -> CapabilityValidator:
    return CapabilityValidator()


@pytest.fixture
def minimal_domain_spec_with_caps() -> DomainSpec:
    """Minimal domain spec with capabilities defined."""
    raw = {
        "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "MaterialIntake",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [{"name": "intake_id", "type": "int", "required": True}],
                },
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "intake_to_buyer"}],
            "queryentity": [{"label": "MaterialIntake", "matchdirection": "intake_to_buyer"}],
        },
        "queryschema": {"matchdirections": ["intake_to_buyer"], "fields": []},
        "gates": [],
        "scoring": {"dimensions": []},
        "capabilities": [
            {"name": "match_read", "actions": ["match:read"], "allowed_subjects": ["*"]},
            {"name": "sync_write", "actions": ["sync:write"], "allowed_subjects": ["acme", "globex"]},
            {"name": "admin_all", "actions": ["admin:write", "admin:kge"], "allowed_subjects": ["acme"]},
        ],
    }
    return DomainSpec(**raw)


# ═══════════════════════════════════════════════════════════════════
#  W3-01: Tenant Authorization Enforcement
# ═══════════════════════════════════════════════════════════════════


class TestTenantAuthEnforcement:
    """W3-01: JWT allowed_tenants check and bypass key."""

    def test_jwt_payload_decode(self):
        """_decode_jwt_payload extracts claims from a valid JWT."""
        from chassis.auth.auth import _decode_jwt_payload

        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
        payload = (
            base64.urlsafe_b64encode(json.dumps({"sub": "user1", "allowed_tenants": ["acme", "globex"]}).encode())
            .rstrip(b"=")
            .decode()
        )
        sig = base64.urlsafe_b64encode(b"signature").rstrip(b"=").decode()
        token = f"{header}.{payload}.{sig}"

        claims = _decode_jwt_payload(token)
        assert claims["sub"] == "user1"
        assert claims["allowed_tenants"] == ["acme", "globex"]

    def test_jwt_payload_decode_non_jwt(self):
        """Non-JWT tokens return empty dict."""
        from chassis.auth.auth import _decode_jwt_payload

        assert _decode_jwt_payload("plain-api-key") == {}
        assert _decode_jwt_payload("") == {}

    def test_jwt_payload_decode_malformed(self):
        """Malformed JWT returns empty dict."""
        from chassis.auth.auth import _decode_jwt_payload

        assert _decode_jwt_payload("a.b.c") == {}

    def test_validate_tenant_access_with_allowed_tenants(self):
        """_validate_tenant_access rejects tenant not in allowed_tenants."""
        from engine.handlers import ValidationError, _validate_tenant_access

        mock_state = MagicMock()
        mock_state.tenant_allowlist = None
        with patch("engine.handlers.get_state", return_value=mock_state):
            with patch("engine.config.settings.settings") as mock_settings:
                mock_settings.tenant_auth_enabled = True
                with pytest.raises(ValidationError, match="not in JWT allowed_tenants"):
                    _validate_tenant_access("evil_corp", "match", allowed_tenants=["acme", "globex"])

    def test_validate_tenant_access_allowed(self):
        """_validate_tenant_access passes when tenant is in allowed_tenants."""
        from engine.handlers import _validate_tenant_access

        mock_state = MagicMock()
        mock_state.tenant_allowlist = None
        with patch("engine.handlers.get_state", return_value=mock_state):
            with patch("engine.config.settings.settings") as mock_settings:
                mock_settings.tenant_auth_enabled = True
                # Should not raise
                _validate_tenant_access("acme", "match", allowed_tenants=["acme", "globex"])

    def test_validate_tenant_access_wildcard(self):
        """Wildcard * in allowed_tenants allows any tenant."""
        from engine.handlers import _validate_tenant_access

        mock_state = MagicMock()
        mock_state.tenant_allowlist = None
        with patch("engine.handlers.get_state", return_value=mock_state):
            with patch("engine.config.settings.settings") as mock_settings:
                mock_settings.tenant_auth_enabled = True
                _validate_tenant_access("anything", "match", allowed_tenants=["*"])

    def test_validate_tenant_access_disabled(self):
        """When tenant_auth_enabled is False, skip JWT check."""
        from engine.handlers import _validate_tenant_access

        mock_state = MagicMock()
        mock_state.tenant_allowlist = None
        with patch("engine.handlers.get_state", return_value=mock_state):
            with patch("engine.config.settings.settings") as mock_settings:
                mock_settings.tenant_auth_enabled = False
                _validate_tenant_access("evil_corp", "match", allowed_tenants=["acme"])


# ═══════════════════════════════════════════════════════════════════
#  W3-02: Capability Model
# ═══════════════════════════════════════════════════════════════════


class TestCapability:
    """W3-02: Capability dataclass tests."""

    def test_creation(self, root_capability: Capability):
        assert root_capability.tenant_id == "acme"
        assert root_capability.domain_id == "*"
        assert "match:read" in root_capability.allowed_actions
        assert root_capability.granted_by == "ROOT"
        assert root_capability.revoked is False
        assert root_capability.is_active()

    def test_proof_hash_integrity(self, root_capability: Capability):
        assert root_capability.is_valid_hash()
        # Tamper with the capability
        root_capability.proof_hash = "tampered"
        assert not root_capability.is_valid_hash()
        assert not root_capability.is_active()

    def test_expiry(self):
        cap = Capability(
            tenant_id="acme",
            domain_id="*",
            allowed_actions=frozenset({"match:read"}),
            expires_at=time.time() - 10,  # already expired
        )
        assert cap.is_expired()
        assert not cap.is_active()

    def test_not_expired(self):
        cap = Capability(
            tenant_id="acme",
            domain_id="*",
            allowed_actions=frozenset({"match:read"}),
            expires_at=time.time() + 3600,
        )
        assert not cap.is_expired()
        assert cap.is_active()

    def test_never_expires(self, root_capability: Capability):
        assert root_capability.expires_at == 0.0
        assert not root_capability.is_expired()

    def test_revocation(self, root_capability: Capability):
        root_capability.revoked = True
        assert not root_capability.is_active()

    def test_to_dict(self, root_capability: Capability):
        d = root_capability.to_dict()
        assert d["tenant_id"] == "acme"
        assert d["domain_id"] == "*"
        assert "match:read" in d["allowed_actions"]
        assert d["is_active"] is True


class TestCapabilityValidator:
    """W3-02: CapabilityValidator tests."""

    def test_register_and_validate(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        assert validator.validate_action(root_capability, "match:read", "acme")

    def test_validate_unregistered(self, validator: CapabilityValidator, root_capability: Capability):
        assert not validator.validate_action(root_capability, "match:read", "acme")

    def test_validate_wrong_tenant(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        assert not validator.validate_action(root_capability, "match:read", "globex")

    def test_validate_wrong_action(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        assert not validator.validate_action(root_capability, "admin:kge", "acme")

    def test_validate_revoked(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        root_capability.revoked = True
        assert not validator.validate_action(root_capability, "match:read", "acme")

    def test_validate_wildcard_tenant(self, validator: CapabilityValidator):
        cap = Capability(tenant_id="*", domain_id="*", allowed_actions=frozenset({"match:read"}))
        validator.register(cap)
        assert validator.validate_action(cap, "match:read", "any_tenant")

    def test_derive_capability(self, validator: CapabilityValidator, root_capability: Capability):
        """Derive a child capability with restricted scope."""
        validator.register(root_capability)
        child = validator.derive_capability(
            root_capability,
            scope_restriction={"domain_id": "plasticos", "allowed_actions": ["match:read"]},
        )
        assert child.domain_id == "plasticos"
        assert child.allowed_actions == frozenset({"match:read"})
        assert child.granted_by == root_capability.capability_id
        assert child.is_active()

    def test_derive_monotonicity_domain(self, validator: CapabilityValidator):
        """Child cannot have a different domain than parent (unless parent is wildcard)."""
        parent = Capability(tenant_id="acme", domain_id="plasticos", allowed_actions=frozenset({"match:read"}))
        validator.register(parent)
        with pytest.raises(PermissionError, match="Monotonicity violation"):
            validator.derive_capability(parent, scope_restriction={"domain_id": "other_domain"})

    def test_derive_monotonicity_actions(self, validator: CapabilityValidator, root_capability: Capability):
        """Child cannot have actions not in parent."""
        validator.register(root_capability)
        with pytest.raises(PermissionError, match="Monotonicity violation"):
            validator.derive_capability(
                root_capability,
                scope_restriction={"allowed_actions": ["match:read", "admin:kge"]},
            )

    def test_derive_from_inactive(self, validator: CapabilityValidator, root_capability: Capability):
        """Cannot derive from revoked/expired capability."""
        validator.register(root_capability)
        root_capability.revoked = True
        with pytest.raises(PermissionError, match="inactive"):
            validator.derive_capability(root_capability, scope_restriction={})

    def test_derive_expiry_inheritance(self, validator: CapabilityValidator):
        """Child cannot outlive parent."""
        parent = Capability(
            tenant_id="acme",
            domain_id="*",
            allowed_actions=frozenset({"match:read"}),
            expires_at=time.time() + 100,
        )
        validator.register(parent)
        child = validator.derive_capability(parent, scope_restriction={}, expires_in_seconds=9999)
        # Child should inherit parent's expiry (shorter)
        assert child.expires_at == parent.expires_at

    def test_revoke_recursive(self, validator: CapabilityValidator, root_capability: Capability):
        """Revoking parent also revokes all descendants."""
        validator.register(root_capability)
        child = validator.derive_capability(root_capability, scope_restriction={"allowed_actions": ["match:read"]})
        grandchild = validator.derive_capability(child, scope_restriction={"allowed_actions": ["match:read"]})

        assert child.is_active()
        assert grandchild.is_active()

        # Revoke root
        validator.revoke_capability(root_capability.capability_id)

        assert root_capability.revoked
        assert child.revoked
        assert grandchild.revoked

    def test_revoke_nonexistent(self, validator: CapabilityValidator):
        assert not validator.revoke_capability("nonexistent_id")

    def test_check_derivation_chain(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        child = validator.derive_capability(root_capability, scope_restriction={"allowed_actions": ["match:read"]})
        grandchild = validator.derive_capability(child, scope_restriction={"allowed_actions": ["match:read"]})

        chain = validator.check_derivation_chain(grandchild)
        assert len(chain) == 3
        assert chain[0].capability_id == root_capability.capability_id
        assert chain[1].capability_id == child.capability_id
        assert chain[2].capability_id == grandchild.capability_id

    def test_audit_summary(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        child = validator.derive_capability(root_capability, scope_restriction={"allowed_actions": ["match:read"]})

        summary = validator.audit_summary()
        assert summary["total_registered"] == 2
        assert summary["active"] == 2
        assert summary["revoked"] == 0
        assert summary["derivations"] == 1


# ═══════════════════════════════════════════════════════════════════
#  W3-02: CapabilitySet (domain-spec compiled capabilities)
# ═══════════════════════════════════════════════════════════════════


class TestCapabilitySet:
    def test_empty_capabilities(self):
        """No capabilities defined → open access."""
        cs = CapabilitySet([])
        assert cs.has_capability("any_tenant", "match:read")

    def test_wildcard_subjects(self):
        """Wildcard '*' allows any tenant."""
        cs = CapabilitySet([{"actions": ["match:read"], "allowed_subjects": ["*"]}])
        assert cs.has_capability("any_tenant", "match:read")

    def test_specific_subjects(self):
        """Only listed tenants are allowed."""
        cs = CapabilitySet([{"actions": ["sync:write"], "allowed_subjects": ["acme", "globex"]}])
        assert cs.has_capability("acme", "sync:write")
        assert cs.has_capability("globex", "sync:write")
        assert not cs.has_capability("evil_corp", "sync:write")

    def test_action_not_in_set(self):
        """Unrestricted actions allow any tenant."""
        cs = CapabilitySet([{"actions": ["match:read"], "allowed_subjects": ["acme"]}])
        assert cs.has_capability("any_tenant", "admin:write")

    def test_multiple_capabilities(self):
        caps = [
            {"actions": ["match:read"], "allowed_subjects": ["*"]},
            {"actions": ["sync:write"], "allowed_subjects": ["acme"]},
            {"actions": ["admin:write"], "allowed_subjects": ["acme"]},
        ]
        cs = CapabilitySet(caps)
        assert cs.has_capability("globex", "match:read")
        assert not cs.has_capability("globex", "sync:write")
        assert not cs.has_capability("globex", "admin:write")
        assert cs.has_capability("acme", "sync:write")

    def test_to_dict(self):
        cs = CapabilitySet([{"actions": ["match:read"], "allowed_subjects": ["acme"]}])
        d = cs.to_dict()
        assert "match:read" in d
        assert "acme" in d["match:read"]


# ═══════════════════════════════════════════════════════════════════
#  W3-03: Action-Level Permissions
# ═══════════════════════════════════════════════════════════════════


class TestActionPermissions:
    def test_permission_map_coverage(self):
        """All main engine actions are in ACTION_PERMISSION_MAP."""
        required_actions = {"match", "sync", "enrich", "outcomes", "admin"}
        assert required_actions.issubset(ACTION_PERMISSION_MAP.keys())

    def test_check_action_permission_authorized(self):
        cs = CapabilitySet([{"actions": ["match:read"], "allowed_subjects": ["acme"]}])
        assert check_action_permission("acme", "match", cs)

    def test_check_action_permission_unauthorized(self):
        cs = CapabilitySet([{"actions": ["match:read"], "allowed_subjects": ["acme"]}])
        assert not check_action_permission("evil_corp", "match", cs)

    def test_check_action_permission_no_capability_set(self):
        """No capability set → all authorized."""
        assert check_action_permission("any", "match", None)

    def test_check_action_permission_unknown_action(self):
        """Unknown action denied by default."""
        cs = CapabilitySet([{"actions": ["match:read"], "allowed_subjects": ["*"]}])
        assert not check_action_permission("acme", "nonexistent_action", cs)

    def test_enforce_capability_with_spec(self, minimal_domain_spec_with_caps: DomainSpec):
        """_enforce_capability raises ValidationError for unauthorized tenant."""
        from engine.handlers import ValidationError, _enforce_capability

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.capability_auth_enabled = True
            # "evil_corp" is not in allowed_subjects for sync:write
            with pytest.raises(ValidationError, match="lacks capability"):
                _enforce_capability("evil_corp", "sync", minimal_domain_spec_with_caps)

    def test_enforce_capability_authorized(self, minimal_domain_spec_with_caps: DomainSpec):
        """_enforce_capability passes for authorized tenant."""
        from engine.handlers import _enforce_capability

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.capability_auth_enabled = True
            # "acme" has sync:write
            _enforce_capability("acme", "sync", minimal_domain_spec_with_caps)

    def test_enforce_capability_disabled(self, minimal_domain_spec_with_caps: DomainSpec):
        """When capability_auth_enabled is False, skip check."""
        from engine.handlers import _enforce_capability

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.capability_auth_enabled = False
            _enforce_capability("evil_corp", "sync", minimal_domain_spec_with_caps)

    def test_enforce_capability_no_caps_in_spec(self):
        """No capabilities in spec → open access."""
        from engine.handlers import _enforce_capability

        raw = {
            "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
            "ontology": {
                "nodes": [
                    {
                        "label": "Facility",
                        "managedby": "sync",
                        "candidate": True,
                        "matchdirection": "intake_to_buyer",
                        "properties": [{"name": "facility_id", "type": "int", "required": True}],
                    },
                    {
                        "label": "MaterialIntake",
                        "managedby": "api",
                        "queryentity": True,
                        "matchdirection": "intake_to_buyer",
                        "properties": [{"name": "intake_id", "type": "int", "required": True}],
                    },
                ],
                "edges": [],
            },
            "matchentities": {
                "candidate": [{"label": "Facility", "matchdirection": "intake_to_buyer"}],
                "queryentity": [{"label": "MaterialIntake", "matchdirection": "intake_to_buyer"}],
            },
            "queryschema": {"matchdirections": ["intake_to_buyer"], "fields": []},
            "gates": [],
            "scoring": {"dimensions": []},
        }
        spec = DomainSpec(**raw)

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.capability_auth_enabled = True
            _enforce_capability("any_tenant", "match", spec)


# ═══════════════════════════════════════════════════════════════════
#  W3-04: Delegation & Revocation Audit Trail
# ═══════════════════════════════════════════════════════════════════


class TestDelegationAudit:
    def test_delegate_creates_child(self, validator: CapabilityValidator, root_capability: Capability):
        """Delegation creates a valid child capability."""
        validator.register(root_capability)
        child = validator.derive_capability(
            root_capability,
            scope_restriction={"domain_id": "plasticos", "allowed_actions": ["match:read"]},
        )
        assert child.is_active()
        assert child.granted_by == root_capability.capability_id
        assert child.domain_id == "plasticos"

    def test_revoke_parent_cascades(self, validator: CapabilityValidator, root_capability: Capability):
        """Revoking parent invalidates all descendants."""
        validator.register(root_capability)
        c1 = validator.derive_capability(root_capability, scope_restriction={"allowed_actions": ["match:read"]})
        c2 = validator.derive_capability(c1, scope_restriction={"allowed_actions": ["match:read"]})

        assert c1.is_active()
        assert c2.is_active()

        validator.revoke_capability(root_capability.capability_id)

        assert not c1.is_active()
        assert not c2.is_active()

    def test_derivation_recorded(self, validator: CapabilityValidator, root_capability: Capability):
        """Derivation is tracked for audit purposes."""
        validator.register(root_capability)
        child = validator.derive_capability(root_capability, scope_restriction={"allowed_actions": ["match:read"]})
        assert child.capability_id in validator._derivations
        derivation = validator._derivations[child.capability_id]
        assert derivation.parent_capability.capability_id == root_capability.capability_id

    def test_audit_summary_after_revocation(self, validator: CapabilityValidator, root_capability: Capability):
        validator.register(root_capability)
        child = validator.derive_capability(root_capability, scope_restriction={"allowed_actions": ["match:read"]})
        validator.revoke_capability(root_capability.capability_id)

        summary = validator.audit_summary()
        assert summary["revoked"] == 2
        assert summary["active"] == 0

    def test_singleton_validator(self):
        """get_capability_validator returns a singleton."""
        v1 = get_capability_validator()
        v2 = get_capability_validator()
        assert v1 is v2


# ═══════════════════════════════════════════════════════════════════
#  Schema Integration: CapabilitySpec in DomainSpec
# ═══════════════════════════════════════════════════════════════════


class TestCapabilitySpecSchema:
    def test_capability_spec_model(self):
        spec = CapabilitySpec(name="test", actions=["match:read"], allowed_subjects=["*"])
        assert spec.name == "test"
        assert spec.actions == ["match:read"]
        assert spec.allowed_subjects == ["*"]

    def test_domain_spec_with_capabilities(self, minimal_domain_spec_with_caps: DomainSpec):
        assert len(minimal_domain_spec_with_caps.capabilities) == 3
        assert minimal_domain_spec_with_caps.capabilities[0].name == "match_read"

    def test_domain_spec_without_capabilities(self):
        """DomainSpec works without capabilities (backwards compatible)."""
        raw = {
            "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
            "ontology": {
                "nodes": [
                    {
                        "label": "Facility",
                        "managedby": "sync",
                        "candidate": True,
                        "matchdirection": "d1",
                        "properties": [{"name": "id", "type": "int", "required": True}],
                    },
                    {
                        "label": "Query",
                        "managedby": "api",
                        "queryentity": True,
                        "matchdirection": "d1",
                        "properties": [{"name": "id", "type": "int", "required": True}],
                    },
                ],
                "edges": [],
            },
            "matchentities": {
                "candidate": [{"label": "Facility", "matchdirection": "d1"}],
                "queryentity": [{"label": "Query", "matchdirection": "d1"}],
            },
            "queryschema": {"matchdirections": ["d1"], "fields": []},
            "gates": [],
            "scoring": {"dimensions": []},
        }
        spec = DomainSpec(**raw)
        assert spec.capabilities == []


# ═══════════════════════════════════════════════════════════════════
#  Settings: Wave 3 Feature Flags
# ═══════════════════════════════════════════════════════════════════


class TestWave3Settings:
    def test_default_flags(self):
        """Wave 3 flags have correct defaults."""
        from engine.config.settings import Settings

        # Create a fresh settings instance with no env overrides
        s = Settings(
            _env_file=None,
            neo4j_password="test-safe",
            api_secret_key="test-safe",
        )
        assert s.tenant_auth_enabled is True
        assert s.tenant_auth_bypass_key == ""
        assert s.capability_auth_enabled is True

    def test_flags_can_be_overridden(self):
        """Wave 3 flags can be set via constructor (simulating env vars)."""
        from engine.config.settings import Settings

        s = Settings(
            _env_file=None,
            neo4j_password="test-safe",
            api_secret_key="test-safe",
            tenant_auth_enabled=False,
            tenant_auth_bypass_key="super-secret",
            capability_auth_enabled=False,
        )
        assert s.tenant_auth_enabled is False
        assert s.tenant_auth_bypass_key == "super-secret"
        assert s.capability_auth_enabled is False
