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
Nodes NEVER call each other via raw HTTP. All inter-node communication uses
`delegate_to_node()` which wraps the request in a PacketEnvelope with delegation
chain, hop trace, and scoped permissions.

## The Only Way to Call Another Node
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


## What delegate_to_node() Does Internally

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
