# Belief Propagation — Integration Runbook

## Overview

Drop-in integration of the Theory of Trust (ToTh) belief propagation module
into the L9 Enrichment Inference Engine.

**Module:** `engine/scoring/belief_propagation.py`
**Zero external dependencies. No architecture changes.**

---

## Integration Points

### 1. CEG Match Rescoring

**Location:** `engine/handlers.py` → `handle_enrich()` or `handle_match()`

**Position:** After Neo4j query, before GMP-05 Pareto filter.

```python
from engine.scoring.belief_propagation import rescore_candidates

# After fetching raw candidates from Neo4j:
candidates = await execute_match_query(driver, entity_type, entity_id, dimension_keys)

# Apply belief propagation rescoring
rescored = rescore_candidates(
    candidates,
    dimension_keys=["geo_score", "community_score", "temporal_score"],
    prior_key="confidence",   # field holding prior belief (default 0.5 if absent)
    score_key="belief_score", # output field name
)

# Pass rescored candidates to Pareto filter
pareto_result = compute_pareto_front(rescored)
```

### 2. GATE Hop Trace Quality Scoring

**Location:** Wherever GATE hop traces are evaluated for routing decisions.

```python
from engine.scoring.belief_propagation import (
    hop_trust_from_entry,
    chain_composite,
    propagate_chain,
)

# Convert each hop to a trust signal
hop_trusts = [
    hop_trust_from_entry(
        status=hop["status"],
        duration_ms=hop["duration_ms"],
        timeout_ms=hop.get("timeout_ms", 30000),
    )
    for hop in gate_response["hop_trace"]
]

# Measure overall path quality (entropy-penalized)
path_quality = chain_composite(hop_trusts, prior=0.6)

# Measure terminal confidence (last hop)
terminal_confidence = propagate_chain(hop_trusts, prior=0.6)
```

### 3. PacketEnvelope Safety Layer

**Location:** Handler ingress/egress boundaries.

```python
from engine.gates.packet_bridge import validate_packet, wrap_response

# Ingress validation
is_valid, error = validate_packet(incoming_packet)
if not is_valid:
    raise ValueError(f"Invalid packet: {error}")

# ... handler logic ...

# Egress wrapping with intelligence quality metadata
response = wrap_response(
    result=handler_output,
    request_packet=incoming_packet,
    intelligence_quality={
        "method": "entropy_penalized_composite",
        "dimensions_used": dimension_keys,
        "path_quality": path_quality,
        "terminal_confidence": terminal_confidence,
    },
)
```

---

## Trust Tiers

| Tier | Value | Maps to |
|------|-------|---------|
| ENTAILMENT | 0.95 | COMPLETED hop, strong evidence |
| NEUTRAL | 0.60 | PENDING, DELEGATED, unknown |
| CONTRADICTION | 0.10 | FAILED, TIMEOUT |

---

## Confidence Formulas

### Composite Score (CEG Match)

```
S = μ̄ - H̄
where:
  μ̄ = mean of sequential Bayesian updates
  H̄ = mean Shannon entropy of belief states
```

High-entropy signals (conflicting evidence) are penalized. Consistent
high-trust signals produce near-maximum scores.

### Chain Composite (GATE Hop Trace Quality)

Same formula as composite score, applied to ordered hop sequence.
Middle-hop uncertainty propagates entropy penalty to final score.

### Chain Propagation (Terminal Confidence)

Pure sequential Bayesian update — no entropy penalty.
Returns confidence of the final belief after all hops.

---

## Validator Usage

```python
from engine.compliance.validator import validate_enrichment_request

payload = {
    "entity_id": "MAT_001",
    "entity_type": "Material",        # enum: Material, Facility, Buyer, Supplier
    "convergence_depth": 2,           # optional, int 1-5
    "enable_pareto": True,            # optional, bool
}
is_valid, error = validate_enrichment_request(payload)
```

---

## Logging Setup

```python
from engine.utils.logger import setup_logging

# Call once at application startup
setup_logging("INFO")  # or "DEBUG" for development
```

All modules in `engine/scoring/`, `engine/gates/`, `engine/traversal/`, and
`engine/compliance/` use `structlog.get_logger()` — they emit structured JSON
automatically after `setup_logging()` is called.
