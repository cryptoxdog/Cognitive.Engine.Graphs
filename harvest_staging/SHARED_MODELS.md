
**Closes:** Agents duplicating Pydantic models across repos

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Shared Models Contract

## Rule
Constellation-wide Pydantic models live in the `l9-core` package. Individual
engines import from `l9.core`, NEVER redefine these models.

## Package: l9-core
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
# ✅ CORRECT — import from l9.core
from l9.core.envelope import PacketEnvelope, TenantContext, PacketLineage
from l9.core.contract import ExecuteRequest, ExecuteResponse
from l9.core.delegation import delegate_to_node
from l9.core.types import PacketType

# ❌ WRONG — redefining in engine code
class PacketEnvelope(BaseModel):  # BANNED — already in l9-core
    packet_id: UUID
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
