<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [intelligence, architecture, feedback-loop, causal, entity-resolution]
owner: engine-team
status: active
/L9_META -->

# CEG Intelligence Architecture

## Overview

The Cognitive Engine Graphs (CEG) intelligence layer is a set of additive subsystems that enhance the core gate-then-score matching architecture with self-improving capabilities. These subsystems operate on outcome data to learn, adapt, and surface causal insights — all controlled via domain spec YAML flags.

## Subsystems

### Feedback Loop (`FeedbackLoopSpec`)
Outcome-based convergence cycle: records transaction outcomes, learns signal weights from historical performance, propagates winning configurations to similar candidates, and detects distribution drift.

### Causal Edges (`CausalSubgraphSpec`)
Domain-declared causal relationships validated at write time with temporal precedence checks. Supports multi-touch attribution on outcomes and counterfactual scenario generation for negative results.

### Entity Resolution (`SemanticRegistrySpec`)
Three-signal similarity engine (property α + structural β + behavioral γ) that identifies and merges duplicate entities across ingestion sources.

### Counterfactual Scenarios (`CounterfactualSpec`)
Generates "what-if" scenarios for negative outcomes by comparing against winning configurations, producing actionable insights for domain operators.

## Key Design Decisions

- **Additive, not invasive:** Intelligence subsystems enhance but never replace the core gate-then-score pipeline. Disabling any subsystem returns the engine to its base behavior.
- **Domain-spec-driven:** All flags live in YAML, validated by Pydantic at load time. No code changes needed to toggle features.
- **Frozen models:** All intelligence spec models use `frozen=True` to guarantee immutability after validation.

## File Index

| File | Purpose |
|------|---------|
| `engine/config/schema.py` | Pydantic models: `FeedbackLoopSpec`, `SignalWeightSpec`, `CausalSubgraphSpec`, `CausalEdgeSpec`, `CounterfactualSpec`, `SemanticRegistrySpec` |
| `engine/intelligence/feedback/` | Feedback loop implementation (weight learning, propagation, drift) |
| `engine/intelligence/causal/` | Causal edge validation, attribution, counterfactual generation |
| `engine/intelligence/resolution/` | Entity resolution engine |

## Configuration & Operations

All intelligence features are controlled via domain spec YAML. See [docs/FEATURE_FLAGS.md](docs/FEATURE_FLAGS.md) for the complete operations guide including:

- **Complete flag reference** — every flag with type, default, and effect
- **How to toggle** — edit YAML + hot reload (30s TTL) or admin cache invalidation
- **Per-domain independence** — different domains can run different feature sets
- **Activation recipes** — minimal, progressive, and full activation examples
- **Troubleshooting** — common issues and resolution steps

Domain specs are cached with a 30-second TTL. Changes to YAML files on disk are picked up automatically on the next request after the TTL expires. For immediate effect, use the admin `invalidate_cache` endpoint — no application restart required.
