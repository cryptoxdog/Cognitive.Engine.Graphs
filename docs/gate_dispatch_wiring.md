# GATE Dispatch — Belief Propagation Wiring

## Location

`gate/engine/dispatch.py` — after `response_packet = PacketEnvelope.parse_obj(response.json())`
and before storing in packet store.

## Code Addition

```python
from engine.scoring.belief_propagation import (
    hop_trust_from_entry,
    propagate_chain,
    chain_composite,
)

# Compute chain confidence from hop trace
hop_trusts = [
    hop_trust_from_entry(
        status=hop.status,
        duration_ms=hop.duration_ms,
        timeout_ms=response_packet.metadata.timeout_ms,
    )
    for hop in response_packet.hop_trace
]

# Terminal confidence — how confident is the last hop?
chain_confidence = propagate_chain(hop_trusts, prior=0.6)

# Path quality — how consistent was the whole trace?
chain_quality = chain_composite(hop_trusts, prior=0.6)

# Merge into intelligence_quality (preserves any CEG-side fields)
intelligence_quality = response_packet.payload.get("intelligence_quality", {})
intelligence_quality.update({
    "chain_confidence": chain_confidence,
    "chain_quality": chain_quality,
    "hop_count": len(response_packet.hop_trace),
})

# Derive new packet with updated intelligence_quality (immutable)
response_packet = response_packet.derive(
    payload={
        **response_packet.payload,
        "intelligence_quality": intelligence_quality,
    }
)
```

## Trust Tiers (from `belief_propagation.py`)

| Status | Trust Signal | Rationale |
|---|---|---|
| `COMPLETED` | 0.95 | Entailment tier — hop succeeded |
| `PENDING` / `DELEGATED` | 0.60 | Neutral tier — in-flight |
| `FAILED` / `TIMEOUT` | 0.10 | Contradiction tier |

Timeout proximity penalty: if `duration_ms / timeout_ms > 0.5`, trust degrades
linearly from 0.95 → 0.60 as the ratio approaches 1.0.

## Output Fields

| Field | Formula | Meaning |
|---|---|---|
| `chain_confidence` | `propagate_chain(hop_trusts)` | Terminal belief — confidence of the last hop |
| `chain_quality` | `chain_composite(hop_trusts)` | Entropy-penalized path quality — penalizes inconsistent hops |
| `hop_count` | `len(hop_trace)` | Number of hops in this packet's delegation chain |

These fields are downstream-readable from `response_packet.payload["intelligence_quality"]`.
