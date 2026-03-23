<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [feature-flags, configuration, operations]
owner: engine-team
status: active
/L9_META -->

# CEG Feature Flags — Operations Guide

## How Feature Flags Work

Every intelligence capability in CEG is controlled by a boolean flag in the **domain specification YAML**. Flags are not environment variables or code changes — they live in the domain spec and are validated at load time by Pydantic models in `engine/config/schema.py`.

**Key principles:**
- **Domain-spec-driven:** Each domain (plasticos, freight, healthcare) controls its own flags independently
- **Default disabled:** All intelligence features default to `false` — enabling is opt-in
- **Zero-cost when disabled:** Disabled features are never entered in the code path
- **Pydantic-validated:** Invalid flag values fail at spec load time with clear error messages
- **Hot-reloadable:** Changes take effect within 30 seconds without restart

---

## Complete Feature Flag Reference

### Feedback Loop

| Flag | Type | Default | Location | Effect |
|------|------|---------|----------|--------|
| `feedbackloop.enabled` | `bool` | `false` | FeedbackLoopSpec | Master switch for the entire convergence cycle. When false, `handle_outcomes` writes TransactionOutcome nodes but does not trigger weight learning or propagation |
| `feedbackloop.signal_weights.enabled` | `bool` | `false` | SignalWeightSpec | Enables outcome-based weight learning. Requires `feedbackloop.enabled: true` |
| `feedbackloop.signal_weights.recalculation_cadence_days` | `int` | `30` | SignalWeightSpec | Days between automatic weight recalculations |
| `feedbackloop.signal_weights.min_outcomes_for_recalculation` | `int` | `100` | SignalWeightSpec | Minimum new outcomes before recalculation triggers (whichever threshold is hit first) |
| `feedbackloop.signal_weights.baseline_weight` | `float` | `1.0` | SignalWeightSpec | Starting weight for dimensions with no outcome data |
| `feedbackloop.signal_weights.max_weight` | `float` | `3.0` | SignalWeightSpec | Upper clamp on learned weights |
| `feedbackloop.signal_weights.min_weight` | `float` | `0.1` | SignalWeightSpec | Lower clamp on learned weights |
| `feedbackloop.signal_weights.frequency_adjustment` | `bool` | `true` | SignalWeightSpec | Apply sqrt frequency factor to penalize rare dimensions |
| `feedbackloop.propagation_boost_factor` | `float` | `1.15` | FeedbackLoopSpec | Score multiplier for candidates matching winning configurations |
| `feedbackloop.propagation_similarity_threshold` | `float` | `0.4` | FeedbackLoopSpec | Minimum Jaccard similarity to trigger propagation |
| `feedbackloop.outcome_edge_type` | `str` | `"RESULTED_IN"` | FeedbackLoopSpec | Edge type connecting transactions to outcome nodes |
| `feedbackloop.outcome_node_label` | `str` | `"TransactionOutcome"` | FeedbackLoopSpec | Node label for outcome records |

### Causal Edges

| Flag | Type | Default | Location | Effect |
|------|------|---------|----------|--------|
| `causal.enabled` | `bool` | `false` | CausalSubgraphSpec | Master switch for causal edge subsystem |
| `causal.attribution_enabled` | `bool` | `false` | CausalSubgraphSpec | Enable multi-touch attribution calculation on outcomes |
| `causal.counterfactual_enabled` | `bool` | `false` | CausalSubgraphSpec | Enable CounterfactualScenario generation for negative outcomes |
| `causal.temporal_decay_enabled` | `bool` | `false` | CausalSubgraphSpec | Enable temporal decay subgraph (Phase 2) |
| `causal.chain_depth_limit` | `int` | `5` | CausalSubgraphSpec | Maximum causal chain traversal depth |
| `causal.causal_edges` | `list[CausalEdgeSpec]` | `[]` | CausalSubgraphSpec | Declared causal edge types with `edge_type`, `source_label`, `target_label`, `required_properties`, `temporal_validation`, and `confidence_threshold` |

### Entity Resolution

| Flag | Type | Default | Location | Effect |
|------|------|---------|----------|--------|
| `semantic_registry.enabled` | `bool` | `false` | SemanticRegistrySpec | Master switch for entity resolution |
| `semantic_registry.entity_labels` | `list[str]` | `[]` | SemanticRegistrySpec | Which node labels to resolve (e.g., `["Facility"]`) |
| `semantic_registry.similarity_threshold` | `float` | `0.85` | SemanticRegistrySpec | Minimum combined similarity to merge |
| `semantic_registry.property_weight` | `float` | `0.5` | SemanticRegistrySpec | Weight for property-based similarity (α) |
| `semantic_registry.structural_weight` | `float` | `0.3` | SemanticRegistrySpec | Weight for structural similarity (β) |
| `semantic_registry.behavioral_weight` | `float` | `0.2` | SemanticRegistrySpec | Weight for behavioral similarity (γ) |
| `semantic_registry.comparison_properties` | `list[str]` | `[]` | SemanticRegistrySpec | Which properties to compare for property similarity |
| `semantic_registry.max_candidates` | `int` | `20` | SemanticRegistrySpec | Maximum resolution candidates per entity |

### Counterfactual

| Flag | Type | Default | Location | Effect |
|------|------|---------|----------|--------|
| `counterfactual.enabled` | `bool` | `false` | CounterfactualSpec | Master switch for counterfactual generation |
| `counterfactual.max_scenarios_per_outcome` | `int` | `3` | CounterfactualSpec | Max scenarios generated per negative outcome |
| `counterfactual.min_confidence` | `float` | `0.3` | CounterfactualSpec | Minimum confidence to create a scenario |
| `counterfactual.comparison_pool_size` | `int` | `10` | CounterfactualSpec | How many winning configs to compare against |

---

## Global Settings (Environment Variables)

These are infrastructure-level gates that live outside domain specs:

| Env Var | Default | Effect |
|---------|---------|--------|
| `GDS_ENABLED` | `True` | Controls whether GDS scheduler starts at all. Set to `False` to disable all GDS jobs across all domains |
| `KGE_ENABLED` | `False` | Controls whether KGE embeddings subsystem activates. Phase 4 feature |
| `KGE_EMBEDDING_DIM` | `256` | KGE vector dimension. Must match `KGESpec.embeddingdim` in domain spec |
| `TENANT_ALLOWLIST` | (empty) | Comma-separated list of allowed tenant IDs. Empty = all tenants allowed (dev mode) |
| `DOMAIN_CACHE_MAX_SIZE` | `100` | Maximum number of domain specs in LRU cache |
| `DOMAIN_CACHE_TTL_SECONDS` | `30` | Seconds before cached domain spec is re-validated against disk |

---

## How to Toggle Features

### Step 1: Edit the Domain Spec YAML

```yaml
# domains/plasticos_domain_spec.yaml

# Enable the feedback loop
feedbackloop:
  enabled: true
  signal_weights:
    enabled: true
```

### Step 2: Wait for Hot Reload (30 seconds)

The `DomainPackLoader` cache has a 30-second TTL. After editing the YAML on disk, the next request after 30 seconds will pick up the change automatically.

### Step 3 (Optional): Force Immediate Reload

For immediate effect, call the admin cache invalidation endpoint:

```bash
curl -X POST http://localhost:8000/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action": "admin",
    "tenant": "plasticos",
    "payload": {"subaction": "invalidate_cache"}
  }'
```

No application restart required.

---

## Per-Domain Independence

Each domain spec is loaded and cached independently. Different domains can have entirely different feature configurations:

```yaml
# plasticos — full intelligence stack (mature, 500+ outcomes)
feedbackloop:
  enabled: true
  signal_weights:
    enabled: true
causal:
  enabled: true
  attribution_enabled: true
semantic_registry:
  enabled: true

# freight — minimal (new domain, building outcome data)
feedbackloop:
  enabled: true
  signal_weights:
    enabled: false  # Not enough outcomes yet
causal:
  enabled: false

# healthcare — causal + resolution but no counterfactuals
feedbackloop:
  enabled: true
causal:
  enabled: true
  counterfactual_enabled: false
semantic_registry:
  enabled: true
```

---

## Activation Recipes

### Minimal: Just Feedback Loop
```yaml
feedbackloop:
  enabled: true
  signal_weights:
    enabled: true
```
Outcomes start being recorded with fingerprints. Weights recalculate after 100 outcomes or 30 days.

### Progressive: Add Causal Intelligence
```yaml
feedbackloop:
  enabled: true
  signal_weights:
    enabled: true
causal:
  enabled: true
  attribution_enabled: true
```
Adds causal edge validation on writes and attribution calculation on outcomes.

### Full Activation
```yaml
feedbackloop:
  enabled: true
  signal_weights:
    enabled: true
    frequency_adjustment: true
  propagation_boost_factor: 1.15
causal:
  enabled: true
  attribution_enabled: true
  counterfactual_enabled: true
  chain_depth_limit: 5
semantic_registry:
  enabled: true
  entity_labels: ["Facility"]
  similarity_threshold: 0.85
counterfactual:
  enabled: true
  max_scenarios_per_outcome: 3
```

---

## Troubleshooting

### Flag not taking effect
1. Check the YAML key matches the Pydantic field name exactly (all lowercase, underscores)
2. Verify the spec loads without errors: check application logs for Pydantic validation failures
3. Force cache invalidation via admin endpoint
4. Confirm the parent flag is also enabled (e.g., `feedbackloop.enabled` must be `true` for `signal_weights.enabled` to matter)

### Pydantic validation errors on spec load
The domain spec is validated against the schema at load time. Common issues:
- Wrong field name (e.g., `feedback_loop` instead of `feedbackloop`)
- Wrong type (e.g., string instead of boolean)
- Missing required fields in nested specs

Check logs for: `Domain spec validation failed for {domain_id}: {errors}`

### Drift detector alerts flooding logs
Reduce sensitivity by widening monitoring thresholds or adjusting outcome recording frequency.

### Weight recalculation not triggering
Check that both thresholds are not met: fewer than `min_outcomes_for_recalculation` AND fewer than `recalculation_cadence_days` since last recalculation. Lower the thresholds for faster iteration.

---

## Architecture Reference

For full technical details on each subsystem, see:
- [INTELLIGENCE_ARCHITECTURE.md](../INTELLIGENCE_ARCHITECTURE.md) — Research foundations, formulas, file index
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — Core engine architecture
