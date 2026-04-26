<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts]
owner: platform
status: active
/L9_META -->

**Closes:** Agents duplicating Pydantic models across repos

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Shared Models Contract

## Rule
Constellation-wide Pydantic models live in shared packages. Individual
engines import from these packages, NEVER redefine these models.

---

## Package: constellation-node-sdk (Gate SDK — Current Standard)

For inter-node communication, use the Gate SDK:

```python
# ✅ CORRECT — import from constellation_node_sdk
from constellation_node_sdk import TransportPacket, GateClient
from constellation_node_sdk import create_transport_packet
from constellation_node_sdk import get_gate_client_config_from_env
from constellation_node_sdk import register_from_env

# ✅ CORRECT — use engine wrappers
from engine.gate_client import get_gate_client
from engine.packet_bridge import build_request_packet, build_response_packet
```

Installation (pyproject.toml):
```toml
constellation-node-sdk = {git = "https://github.com/cryptoxdog/Gate_SDK.git"}
```

---

## Package: l9-core (Internal Models)

For internal engine operations and memory substrate:
```

l9/
core/
__init__.py
envelope.py          \# PacketEnvelope, PacketAddress, TenantContext, etc.
contract.py          \# ExecuteRequest, ExecuteResponse, HealthResponse
delegation.py        \# delegate_to_node(), DelegationLink, HopEntry
security.py          \# PacketSecurity, PacketGovernance
types.py             \# PacketType enum, shared type aliases

```

## Import Pattern
```python
# ✅ CORRECT — import from l9.core (internal operations)
from l9.core.envelope import PacketEnvelope, TenantContext, PacketLineage
from l9.core.contract import ExecuteRequest, ExecuteResponse
from l9.core.delegation import delegate_to_node
from l9.core.types import PacketType

# ❌ WRONG — redefining in engine code
class PacketEnvelope(BaseModel):  # BANNED — already in l9-core
    packet_id: UUID
    ...

# ❌ WRONG — redefining TransportPacket
class TransportPacket(BaseModel):  # BANNED — already in constellation_node_sdk
    ...

# ❌ WRONG — copying the model file into your repo
# cp ../enrichment-engine/models/envelope.py engine/models/
```


## Engine-Specific Models Stay in Engine

```python
# These are engine-specific — they live in your engine repo
from engine.config.schema import DomainSpec, GateSpec, ScoringDimension
from engine.scoring.models import ScoreRecord
from engine.routing.models import RoutingDecision
```


## When to Add to l9-core vs Engine

| If the model is used by… | Where it lives |
| :-- | :-- |
| 2+ nodes | `l9-core` |
| 1 node only | That engine's `models/` |
| The chassis | `l9-core` (chassis imports from it) |
| Tests only | `tests/conftest.py` fixtures |

## Installation

```bash
# In every engine's pyproject.toml
[project]
dependencies = [
    "l9-core>=1.0.0",
]
```

```
