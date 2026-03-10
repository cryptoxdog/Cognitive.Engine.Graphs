# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [config]
# tags: [packet, envelope, pydantic]
# owner: engine-team
# status: active
# --- /L9_META ---
# L9 PacketEnvelope v3.0.0 — Constellation Wire Format
# Zero legacy. No memory substrate dependency. Standalone.
# The atom of the AI-Constellation.

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENUMS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PacketType(StrEnum):
    """Extensible. Products register new types at will."""

    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    EVENT = "event"
    COMMAND = "command"
    QUERY = "query"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING = "reasoning"
    DELEGATION = "delegation"
    GOVERNANCE = "governance"
    HEARTBEAT = "heartbeat"


class Action(StrEnum):
    """Chassis-routable actions. Engines extend freely."""

    MATCH = "match"
    SYNC = "sync"
    ENRICH = "enrich"
    QUERY = "query"
    ADMIN = "admin"
    HEALTH = "health"
    DELEGATE = "delegate"
    CALLBACK = "callback"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SUB-OBJECTS (all frozen, extra=forbid)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PacketAddress(BaseModel):
    """Where the packet came from, where it's going, where to reply."""

    model_config = {"frozen": True, "extra": "forbid"}

    source_node: str  # constellation node that emitted
    destination_node: str | None = None  # target node (None = chassis-routed)
    reply_to: str | None = None  # node to receive response


class TenantContext(BaseModel):
    """Multi-tenant identity stack. Supports delegation chains."""

    model_config = {"frozen": True, "extra": "forbid"}

    actor: str  # tenant performing the action
    on_behalf_of: str | None = None  # delegating tenant (if delegated)
    originator: str | None = None  # root tenant that started the chain
    org_id: str | None = None  # organization grouping
    user_id: str | None = None  # individual user within tenant


class DelegationLink(BaseModel):
    """One hop in a delegation chain: who authorized whom to do what."""

    model_config = {"frozen": True, "extra": "forbid"}

    delegator: str  # who granted authority
    delegatee: str  # who received authority
    scope: tuple[str, ...]  # permitted actions ("enrich", "match")
    granted_at: datetime
    expires_at: datetime | None = None
    proof_hash: str | None = None  # HMAC of delegation grant


class HopEntry(BaseModel):
    """One stop in the packet's journey through the constellation."""

    model_config = {"frozen": True, "extra": "forbid"}

    node_id: str
    action: str
    entered_at: datetime
    exited_at: datetime | None = None
    status: str | None = None  # "ok" | "error" | "delegated"
    signature: str | None = None  # HMAC proving this node touched it


class PacketLineage(BaseModel):
    """Derivation chain. Immutable ancestry."""

    model_config = {"frozen": True, "extra": "forbid"}

    parent_ids: tuple[UUID, ...] = ()
    root_id: UUID | None = None  # ultimate ancestor (first packet)
    generation: int = 0
    derivation_type: str | None = None  # "fan_out" | "transform" | "aggregate"
    fan_out_count: int | None = None  # expected downstream packets


class PacketSecurity(BaseModel):
    """Cryptographic integrity + classification."""

    model_config = {"frozen": True, "extra": "forbid"}

    content_hash: str  # SHA-256 of canonical payload
    hash_algorithm: str = "sha256"
    signature: str | None = None  # HMAC-SHA256 signed by source node
    signing_key_id: str | None = None  # which key signed it
    classification: str = "internal"  # "public" | "internal" | "confidential" | "restricted"
    encryption_status: str = "plaintext"  # "plaintext" | "aes256-gcm" | "envelope-encrypted"
    pii_fields: tuple[str, ...] = ()  # payload keys containing PII (for GDPR ops)


class PacketObservability(BaseModel):
    """Distributed tracing + metrics hooks."""

    model_config = {"frozen": True, "extra": "forbid"}

    trace_id: str  # W3C traceparent trace-id
    span_id: str | None = None  # current span
    parent_span_id: str | None = None  # parent span
    correlation_id: str | None = None  # business-level correlation
    created_at: datetime
    ingested_at: datetime | None = None  # when the receiving node accepted it
    processing_ms: float | None = None


class PacketGovernance(BaseModel):
    """Audit + compliance metadata."""

    model_config = {"frozen": True, "extra": "forbid"}

    intent: str | None = None  # why this packet exists
    compliance_tags: tuple[str, ...] = ()  # "GDPR", "SOC2", "ECOA", "HIPAA"
    retention_days: int | None = None  # override default TTL
    redaction_applied: bool = False
    audit_required: bool = False
    data_subject_id: str | None = None  # for GDPR right-to-delete


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THE ENVELOPE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PacketEnvelope(BaseModel):
    """
    L9 AI-Constellation canonical wire format v3.0.0.

    Contracts:
      - IMMUTABLE after creation (frozen=True).
      - Mutations produce NEW packets via derive().
      - content_hash covers (packet_type, action, payload, tenant_context, address).
      - Extra fields rejected (extra=forbid).
      - All sub-objects frozen independently.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    # ── identity ──
    packet_id: UUID = Field(default_factory=uuid4)
    packet_type: PacketType
    action: Action
    schema_version: str = "3.0.0"

    # ── routing ──
    address: PacketAddress
    tenant: TenantContext

    # ── domain data ──
    payload: dict[str, Any]

    # ── delegation ──
    delegation_chain: tuple[DelegationLink, ...] = ()

    # ── journey ──
    hop_trace: tuple[HopEntry, ...] = ()

    # ── ancestry ──
    lineage: PacketLineage = Field(default_factory=PacketLineage)

    # ── security ──
    security: PacketSecurity

    # ── observability ──
    observability: PacketObservability

    # ── governance ──
    governance: PacketGovernance = Field(default_factory=lambda: PacketGovernance(intent=None))

    # ── labels ──
    tags: tuple[str, ...] = ()

    # ── expiry ──
    ttl: datetime | None = None

    # ── methods ──

    def verify_integrity(self) -> bool:
        """Recompute content_hash and compare to stored value."""
        return self.security.content_hash == _compute_hash(
            self.packet_type, self.action, self.payload, self.tenant, self.address
        )

    def derive(
        self,
        *,
        packet_type: PacketType | None = None,
        action: Action | None = None,
        payload: dict[str, Any] | None = None,
        address: PacketAddress | None = None,
        tenant: TenantContext | None = None,
        tags: tuple[str, ...] | None = None,
        derivation_type: str = "transform",
        extra_hop: HopEntry | None = None,
        extra_delegation: DelegationLink | None = None,
        governance: PacketGovernance | None = None,
        ttl: datetime | None = None,
    ) -> PacketEnvelope:
        """Create a new packet derived from this one. Immutable lineage."""
        new_type = packet_type or self.packet_type
        new_action = action or self.action
        new_payload = payload if payload is not None else self.payload
        new_address = address or self.address
        new_tenant = tenant or self.tenant

        new_lineage = PacketLineage(
            parent_ids=(self.packet_id,),
            root_id=self.lineage.root_id or self.packet_id,
            generation=self.lineage.generation + 1,
            derivation_type=derivation_type,
        )

        new_hops = self.hop_trace
        if extra_hop:
            new_hops = (*self.hop_trace, extra_hop)

        new_delegations = self.delegation_chain
        if extra_delegation:
            new_delegations = (*self.delegation_chain, extra_delegation)

        new_hash = _compute_hash(new_type, new_action, new_payload, new_tenant, new_address)

        return PacketEnvelope(
            packet_type=new_type,
            action=new_action,
            address=new_address,
            tenant=new_tenant,
            payload=new_payload,
            delegation_chain=new_delegations,
            hop_trace=new_hops,
            lineage=new_lineage,
            security=PacketSecurity(
                content_hash=new_hash,
                hash_algorithm=self.security.hash_algorithm,
                signing_key_id=self.security.signing_key_id,
                classification=self.security.classification,
                encryption_status=self.security.encryption_status,
                pii_fields=self.security.pii_fields,
            ),
            observability=PacketObservability(
                trace_id=self.observability.trace_id,
                correlation_id=self.observability.correlation_id,
                created_at=datetime.now(UTC),
            ),
            governance=governance or self.governance,
            tags=tags if tags is not None else self.tags,
            ttl=ttl or self.ttl,
        )

    def to_wire(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict for transport."""
        result: dict[str, Any] = json.loads(self.model_dump_json())
        return result

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> PacketEnvelope:
        """Deserialize from wire dict. Validates all fields."""
        return cls.model_validate(data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HASH FUNCTION (deterministic canonical serialization)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _compute_hash(
    packet_type: PacketType,
    action: Action,
    payload: dict[str, Any],
    tenant: TenantContext,
    address: PacketAddress,
) -> str:
    canonical = json.dumps(
        {
            "packet_type": packet_type.value,
            "action": action.value,
            "payload": payload,
            "tenant": json.loads(tenant.model_dump_json()),
            "address": json.loads(address.model_dump_json()),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FACTORY (convenience builder)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def create_packet(
    *,
    packet_type: PacketType,
    action: Action,
    source_node: str,
    actor_tenant: str,
    payload: dict[str, Any],
    trace_id: str,
    destination_node: str | None = None,
    reply_to: str | None = None,
    on_behalf_of: str | None = None,
    originator: str | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
    classification: str = "internal",
    pii_fields: tuple[str, ...] = (),
    compliance_tags: tuple[str, ...] = (),
    intent: str | None = None,
    tags: tuple[str, ...] = (),
    ttl: datetime | None = None,
    signing_key_id: str | None = None,
) -> PacketEnvelope:
    """One-call factory. Computes hash automatically."""

    address = PacketAddress(
        source_node=source_node,
        destination_node=destination_node,
        reply_to=reply_to,
    )
    tenant = TenantContext(
        actor=actor_tenant,
        on_behalf_of=on_behalf_of,
        originator=originator or actor_tenant,
        org_id=org_id,
        user_id=user_id,
    )
    content_hash = _compute_hash(packet_type, action, payload, tenant, address)

    return PacketEnvelope(
        packet_type=packet_type,
        action=action,
        address=address,
        tenant=tenant,
        payload=payload,
        security=PacketSecurity(
            content_hash=content_hash,
            classification=classification,
            pii_fields=pii_fields,
            signing_key_id=signing_key_id,
        ),
        observability=PacketObservability(
            trace_id=trace_id,
            created_at=datetime.now(UTC),
        ),
        governance=PacketGovernance(
            intent=intent,
            compliance_tags=compliance_tags,
        ),
        tags=tags,
        ttl=ttl,
    )
