<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts]
owner: platform
status: active
/L9_META -->

<!-- L9_TEMPLATE: true -->
# L9 Inter-Node Delegation Contract

## Rule
Nodes NEVER call each other via raw HTTP. All inter-node communication routes
through the **Gate SDK** (`constellation_node_sdk`) which handles routing,
transport, lineage, and fail-closed validation.

---

## Current Standard: Gate SDK (GMP-133)

All outbound inter-node calls MUST use the `GateClient` singleton:

```python
from engine.gate_client import get_gate_client
from engine.packet_bridge import build_request_packet

# Build a compliant TransportPacket
packet = build_request_packet(
    action="enrich",
    payload={"entity": {"name": "ABC Plastics"}, "objective": "..."},
    tenant="plasticos",
    trace_id=inbound_trace_id,  # REQUIRED — propagate from inbound request
    destination_node="enrichment-engine",
)

# Send via Gate
client = get_gate_client()
response_packet = await client.send_to_gate(packet)
```

### Fail-Closed Validation

`build_request_packet()` raises `ValueError` if:
- `trace_id` is missing or blank
- `tenant` is missing or blank
- `action` is missing or blank

### Response Packets

Use `build_response_packet()` to preserve lineage:

```python
from engine.packet_bridge import build_response_packet

response = build_response_packet(
    inbound=inbound_packet,
    payload={"result": [...], "status": "success"},
)
```

---

## Legacy Pattern: delegate_to_node() (DEPRECATED)

> **Note:** This pattern predates the Gate SDK. New code MUST use `GateClient`.

```python
from l9.chassis.contract import delegate_to_node

response_packet = await delegate_to_node(
    envelope=current_packet,         # The packet you're currently processing
    target="enrichment-engine",      # Destination node name (from registry)
    action="enrich",                 # Action the target should execute
    payload={                        # Action-specific payload
        "entity": {"name": "ABC Plastics", "city": "Houston"},
        "schema": {"materials_handled": "list[str]", ...},
        "objective": "Research this facility's capabilities",
        "kb_context": "plastics-recycling-v8",
    },
    permissions=["enrich"],          # Scoped — target can ONLY do this
)
```


## What GateClient Does Internally

1. Wraps payload in `TransportPacket` with full lineage
2. Validates trace_id, tenant, action (fail-closed)
3. Routes via Gate to destination node
4. Gate handles retry, circuit-breaker, timeout
5. Returns response `TransportPacket`

## What delegate_to_node() Does Internally (Legacy)

1. Creates a new derived packet (`derivation_type="delegation"`)
2. Sets `address.destination_node` to target
3. Appends a `DelegationLink` with scoped permissions
4. Appends a `HopEntry` to hop_trace: `{node, action: "delegate", status: "delegated"}`
5. Sets `governance.audit_required = True`
6. Sends via configured transport (HTTP POST to target's `/v1/execute`)
7. Returns the response PacketEnvelope

## BANNED Patterns

```python
# ❌ Raw HTTP calls between nodes
import httpx
resp = await httpx.post("http://enrichment-engine/v1/execute", json={...})

# ❌ Importing another node's code
from enrichment_engine.orchestrator import enrich_entity

# ❌ Direct database access to another node's data
await pg.execute("SELECT * FROM enrichment_engine.packetstore WHERE ...")

# ❌ Constructing envelopes manually for delegation
packet = PacketEnvelope(packet_type="api_request", ...)  # WRONG for delegation
```


## Valid Node Names (Constellation Registry)

```
plasticos
enrichment-engine
graph-engine
score-engine
route-engine
forecast-engine
signal-capture
health-monitor
handoff-engine
```

```
