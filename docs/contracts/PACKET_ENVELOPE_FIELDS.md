<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts, packet]
owner: platform
status: active
/L9_META -->

<!-- L9_TEMPLATE: true -->
# L9 PacketEnvelope Field Contract

> **Migration Notice (GMP-133):** For inter-node communication, use `TransportPacket`
> from `constellation_node_sdk` via `engine/packet_bridge.py`. PacketEnvelope remains
> valid for internal engine use and memory substrate operations.

## TransportPacket (Gate SDK — Current Standard)

```python
from constellation_node_sdk import TransportPacket
from engine.packet_bridge import build_request_packet, build_response_packet

# Build outbound packet
packet = build_request_packet(
    action="graph-query",
    payload={"cypher": "MATCH (n) RETURN n"},
    tenant="plasticos",
    trace_id="trace-12345",
)

# Access fields
packet.header.action        # "graph-query"
packet.header.trace_id      # "trace-12345"
packet.payload              # {"cypher": "..."}
packet.tenant.actor         # "plasticos"
```

---

## PacketEnvelope (Internal Use)

## Rule
PacketEnvelope is immutable (frozen=True). Every constellation node that creates,
reads, or derives a packet MUST use these exact field names. No aliases. No abbreviations.

## Required Fields (must be present on every packet)

```python
class PacketEnvelope(BaseModel, frozen=True):
    packet_id: UUID                      # Auto-generated, globally unique
    packet_type: str                     # From PACKET_TYPE_REGISTRY.md
    payload: dict[str, Any]              # Domain-specific data — the ONLY field that varies
    timestamp: datetime                  # UTC, auto-generated
```


## Standard Optional Fields

```python
    metadata: PacketMetadata | None      # schema_version, agent, domain
    provenance: PacketProvenance | None  # source, tool, derive_type
    confidence: PacketConfidence | None  # score (0.0-1.0), rationale
    reasoning_block: dict | None         # StructuredReasoningBlock if applicable
    thread_id: UUID | None               # Conversation/task grouping
    lineage: PacketLineage | None        # parent_ids, derivation_type, generation
    tags: list[str]                      # Lightweight labels
    ttl: datetime | None                 # Expiration for garbage collection
    trace_id: str | None                 # W3C Trace Context ID
    correlation_id: str | None           # Cross-service correlation
    content_hash: str                    # SHA-256 — auto-computed, UNIQUE constraint in DB
```


## Nested Model Fields

### PacketMetadata

```python
class PacketMetadata(BaseModel, frozen=True):
    schema_version: str                  # e.g., "1.1.0"
    agent: str | None                    # Which agent/service created this
    domain: str | None                   # e.g., "plasticos"
```


### PacketProvenance

```python
class PacketProvenance(BaseModel, frozen=True):
    source: str                          # e.g., "enrichment-engine", "graph-engine"
    tool: str | None                     # e.g., "sonar-variations", "gate-compiler"
    derive_type: str | None              # e.g., "enrichment", "inference", "match"
```


### PacketConfidence

```python
class PacketConfidence(BaseModel, frozen=True):
    score: float                         # 0.0 to 1.0
    rationale: str | None                # Why this confidence level
```


### PacketLineage

```python
class PacketLineage(BaseModel, frozen=True):
    parent_ids: list[UUID]               # Packets this was derived from
    derivation_type: str                 # "enrichment", "inference", "match", "delegation"
    generation: int                      # 0 = root, increments per derivation
```


### PacketAddress

```python
class PacketAddress(BaseModel, frozen=True):
    source_node: str                     # e.g., "plasticos"
    destination_node: str                # e.g., "enrichment-engine"
    reply_to: str | None                 # Where to send the response
```


### TenantContext

```python
class TenantContext(BaseModel, frozen=True):
    actor: str                           # Who is doing it
    on_behalf_of: str | None             # Who authorized it
    originator: str | None               # Who started the chain
    org_id: str                          # Tenant isolation key
    user_id: str | None                  # Individual actor
```


## Immutability Contract

```python
# ✅ CORRECT — derive creates a new packet
new_packet = original.derive(
    mutation={"payload": new_payload},
    derivation_type="enrichment",
)
# new_packet.lineage.parent_ids == [original.packet_id]
# new_packet.lineage.generation == original.lineage.generation + 1

# ❌ BANNED — direct mutation raises ValidationError
original.payload["new_field"] = "value"  # FROZEN — will crash
```


## content_hash Computation

```python
# Deterministic: sorted keys, canonical JSON
import hashlib, json
hash_input = json.dumps({
    "packet_type": envelope.packet_type,
    "action": envelope.payload.get("action"),
    "payload": envelope.payload,
    "tenant": envelope.tenant.actor,
    "address": envelope.address.dict() if envelope.address else None,
}, sort_keys=True)
content_hash = hashlib.sha256(hash_input.encode()).hexdigest()
```


## WRONG Field Names (agents generate these — they're all wrong)

```python
packetid          # WRONG → packet_id
packettype        # WRONG → packet_type
contentHash       # WRONG → content_hash
threadId          # WRONG → thread_id
traceId           # WRONG → trace_id
parentIds         # WRONG → parent_ids (inside PacketLineage)
sourceNode        # WRONG → source_node (inside PacketAddress)
onBehalfOf        # WRONG → on_behalf_of (inside TenantContext)
```

```
