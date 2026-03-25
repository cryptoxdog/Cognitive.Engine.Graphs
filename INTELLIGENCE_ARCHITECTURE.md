# CEG Intelligence Architecture — Technical Reference

**Version:** 2.0.0 | **Date:** March 2026 | **L9 Labs**

## Overview

The Cognitive Engine Graph (CEG) is a gate-then-score knowledge graph matching engine that transforms domain data into inference-bearing graph structures. CEG's intelligence layer closes the feedback loop — learning from every outcome to refine future matches through signal weight adjustment, causal attribution, and entity resolution.

## Research Foundations

### Algorithmic Primitives and Compositional Geometry of Reasoning in Language Models
**Lippl, McGee et al. (2026)** | arXiv:2510.15987v2 | Microsoft Research + Columbia

Key concepts integrated:
- **Match fingerprinting** — Each TransactionOutcome stores an algorithmic fingerprint: which scoring dimensions were active, their weights, and which gates passed. This creates the training data for outcome-based weight learning. (`engine/feedback/signal_weights.py`, `engine/handlers.py`)
- **χ²-divergence drift detection** — The symmetric χ²-distance between recent and historical fingerprint distributions monitors match quality drift. (`engine/feedback/drift_detector.py`)
- **Primitive subtraction as negative penalty** — Dimensions that correlate with negative outcomes receive active penalties, not just reduced weights — implementing the paper's finding that subtracting primitive vectors suppresses associated behaviors. (`engine/scoring/assembler.py`)

### OmniSage: Large Scale, Multi-Entity Heterogeneous Graph Representation Learning
**Badrinath, Yang et al. (2025)** | arXiv:2504.17811v2 | Pinterest Engineering

Key concepts integrated:
- **Triple contrastive similarity** — Entity resolution combines property similarity (entity-feature), structural similarity (entity-entity via shared neighbors), and behavioral similarity (user-entity via shared outcomes). (`engine/resolution/similarity.py`, `engine/resolution/resolver.py`)
- **Power-law graph pruning** — High-degree nodes in co-occurrence projections are pruned to `d^0.86` edges, preventing hub dominance in community detection. (`engine/gds/scheduler.py`)
- **Sample probability correction** — Pattern matching similarity corrected for frequency bias: `corrected = raw - log(freq) / log(total)`. (`engine/feedback/pattern_matcher.py`)
- **Weight confidence intervals** — Learned weights include 95% CI; uncertain weights (small sample) are dampened toward neutral. (`engine/feedback/signal_weights.py`)

### ReasoningLM: Enabling Structural Subgraph Reasoning in Pre-trained Language Models
**Jiang, Zhou et al. (2023)** | EMNLP 2023, pp.3721-3735 | Renmin University + Alibaba

Key concepts integrated:
- **BFS subgraph serialization** — Candidate causal neighborhoods are serialized via BFS into human-readable explanation strings, preserving structural information. (`engine/causal/serializer.py`)
- **Retrieval-then-reasoning for counterfactuals** — Counterfactual generation follows the paper's two-phase pattern: retrieve the outcome's causal neighborhood, then reason about alternative configurations. (`engine/causal/counterfactual.py`)
- **Constrained attention as gate interaction** — The paper's 4-mode attention mask concept informs future gate interaction modeling. (Architecture roadmap)

## Architecture

### Feedback Loop (Convergence Cycle)

```
Match Request → Gate-then-Score → Results Returned
                                       ↓
                             Outcome Recorded (handle_outcomes)
                                       ↓
                             Match Fingerprint Stored
                             (active_dimensions, weights, gates_passed)
                                       ↓
                             ConvergenceLoop.on_outcome_recorded()
                               ├── ScorePropagator (boost matching configs)
                               ├── SignalWeightCalculator (lift formula + CI)
                               ├── CounterfactualGenerator (for failures)
                               └── DriftDetector (χ² divergence check)
                                       ↓
                             DimensionWeight Nodes in Neo4j
                                       ↓
                             ScoringAssembler.load_learned_weights()
                             (spec_weight × learned_weight = final)
                                       ↓
                             Next Match → Improved Scoring ↺
```

### Signal Weight Formula

For each scoring dimension `i`:

```
lift_i = P(positive | dim_i active) / P(positive)
freq_factor_i = √(count_with_dim_i / total_outcomes)
ci_width_i = 1.96 × √(lift_i × (1 - lift_i) / sample_size_i)
confidence_i = 1.0 - min(ci_width_i, 1.0)
weight_i = clamp(1.0 + (lift_i - 1.0) × confidence_i × freq_factor_i, min, max)
```

### Causal Edge Types

| Edge Type | Source → Target | Semantics |
|-----------|----------------|-----------|
| CAUSED_BY | Signal → Signal | A triggered B |
| TRIGGERED | Signal → Outcome | Signal influenced outcome |
| DROVE | Entity → Outcome | Entity actions drove result |
| RESULTED_IN | Outcome → Entity | Ground truth effect |
| ACCELERATED_BY | Entity → Signal | Signal increased velocity |
| BLOCKED_BY | Entity → Entity | Blocker caused negative outcome |
| ENABLED_BY | Event → Activity | Activity enabled outcome |
| PREVENTED_BY | Event → Intervention | Action prevented negative |
| INFLUENCED_BY | Entity → Entity | Asymmetric influence |
| CONTRIBUTED_TO | TouchPoint → Attribution | Weighted causal contribution |

### Entity Resolution (Multi-Signal Similarity)

```
similarity(a, b) = α × property_sim(a, b)
                 + β × structural_sim(a, b)
                 + γ × behavioral_sim(a, b)

Where:
  property_sim = Jaccard(categorical_props) + cosine(numeric_props)
  structural_sim = |shared_neighbors(a,b)| / |union_neighbors(a,b)|
  behavioral_sim = |shared_outcomes(a,b)| / |union_outcomes(a,b)|
  α + β + γ = 1.0 (configurable per domain)
```

### DomainSpec Feature Gates

| Feature | Spec Field | Default |
|---------|-----------|---------|
| Feedback loop | `feedbackloop.enabled` | `false` |
| Signal weight learning | `feedbackloop.signal_weights.enabled` | `false` |
| Confidence dampening | `feedbackloop.signal_weights.confidence_dampening` | `true` |
| Drift detection | `feedbackloop.drift_threshold` | `0.15` |
| Causal edges | `causal.enabled` | `false` |
| Attribution | `causal.attribution_enabled` | `false` |
| Counterfactuals | `counterfactual.enabled` | `false` |
| Entity resolution | `semantic_registry.enabled` | `false` |

### Key Files

| Module | File | Purpose |
|--------|------|---------|
| Feedback | `engine/feedback/convergence.py` | Orchestrates the convergence cycle |
| Feedback | `engine/feedback/signal_weights.py` | Lift formula + CI + weight storage |
| Feedback | `engine/feedback/drift_detector.py` | χ²-divergence monitoring |
| Feedback | `engine/feedback/pattern_matcher.py` | Jaccard + probability correction |
| Feedback | `engine/feedback/score_propagator.py` | Boost/penalty propagation |
| Causal | `engine/causal/edge_taxonomy.py` | 10 causal edge types |
| Causal | `engine/causal/causal_compiler.py` | Cypher generation for causal edges |
| Causal | `engine/causal/causal_validator.py` | Runtime temporal precedence |
| Causal | `engine/causal/counterfactual.py` | Auto-generate scenarios for losses |
| Causal | `engine/causal/attribution.py` | Multi-touch attribution models |
| Causal | `engine/causal/serializer.py` | BFS subgraph explanation strings |
| Resolution | `engine/resolution/resolver.py` | Canonical entity deduplication |
| Resolution | `engine/resolution/similarity.py` | Multi-signal similarity scorer |
| Scoring | `engine/scoring/assembler.py` | Consumes DimensionWeight nodes |

---

**Repository:** https://github.com/cryptoxdog/Cognitive.Engine.Graphs
**L9 Labs** | March 2026
