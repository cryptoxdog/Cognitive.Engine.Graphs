## Diff Summary: v0.3.0 → v0.4.0

### High-Level Statistics

| Metric | v0.3.0 | v0.4.0 | Delta |
|--------|--------|--------|-------|
| Lines | 2,117 | 1,752 | -365 |
| Node labels | 12 | 22 | +10 |
| Edge types | 13 | 31 | +18 |
| GDS jobs | 3 | 9 | +6 |
| Scoring dimensions | 4 | 5 | +1 |
| Gates | 14 | 14 | 0 |

---

### 1. Header / Purpose Shift

| Aspect | v0.3.0 | v0.4.0 |
|--------|--------|--------|
| Title | "Comprehensive Stress Test Reference Implementation" | "Recycled Plastics Brokerage Matching" |
| Purpose | Engine feature coverage scoreboard (10/10 gate types, 9/9 scoring, etc.) | Production-ready spec with architecture, rollout phases |
| Owner | `plasticos-platform-team` | `igor-beylin` |
| Domain ID | `plasticos` | `plastics-recycling-brokerage` |

**v0.3.0** was a **stress-test reference** proving the engine handles every feature type.
**v0.4.0** is a **production deployment spec** with architecture, rollout phases, and safety checks.

---

### 2. New `architecture` Section (v0.4.0 only)

```yaml
architecture:
  service: plasticos-graph-intelligence
  framework: FastAPI
  database: "Neo4j 5.x Enterprise + GDS plugin"
  language: "Python 3.11+"
  async_driver: true
  cypher_location: "app/graph/queries/*.cypher"
  inline_cypher: forbidden
```

This section didn't exist in v0.3.0.

---

### 3. Ontology Changes

#### Candidates (Facility)

| Property | v0.3.0 | v0.4.0 |
|----------|--------|--------|
| `facility_id` type | `string` | `int` |
| `match_direction` | `intake_to_facility` | `material_to_facility` |
| `facility_role` values | `[processor, compounder, manufacturer, broker, trader, tolling]` | `[broker, processor, compounder, mrf, recycler]` |
| Indexes | None declared | 4 explicit indexes + constraint |
| New properties | — | `louvain_geo_community_id`, `onboarded_at`, `last_transaction_at`, `success_rate_90d`, `avg_turnaround_days` |

#### Query Entities

| v0.3.0 | v0.4.0 |
|--------|--------|
| `Intake` node | `MaterialProfile` + `IntakeMatchRequest` (Pydantic, not persisted) |

#### Taxonomy Nodes

**v0.4.0 adds:**
- `FormFactor`
- `ColorFamily`
- `QualityLevel`
- `MaterialAttribute`

**v0.4.0 adds constraints** for all taxonomy nodes.

#### Knowledge/KB Nodes

| v0.3.0 | v0.4.0 |
|--------|--------|
| `Grade`, `InferenceRule`, `KBContaminantSpec`, `QualityTier` | `Grade`, `CapabilityProfile`, `Application`, `Certification`, `Additive` |

**Removed:** `InferenceRule`, `KBContaminantSpec`, `QualityTier`
**Added:** `CapabilityProfile`, `Application`, `Certification`, `Additive`

#### Auxiliary Nodes

**v0.4.0 adds:**
- `EquipmentType` (reified from boolean properties)
- `Community` (materialized Louvain cluster)
- `TransactionOutcome` (v1.1 feedback loop)
- `SignalEvent` (v1.1 entity resolution)

**Removed:** `Company`, `Margin`

---

### 4. Edge Changes

#### New Edge Layers in v0.4.0

| Layer | Edge Types |
|-------|------------|
| Polymer Similarity | `CO_ACCEPTED_WITH`, `SUBSTITUTABLE_FOR`, `CO_PURCHASED_WITH` |
| Geo-Proximity | `COLOCATED_WITH` |
| Temporal Weighting | `RECENTLY_TRANSACTED_WITH`, `ACCEPTED_MATERIAL_FROM` |
| Process Affinity | `COMPATIBLE_WITH_PROCESS` |
| Equipment Capability | `HAS_EQUIPMENT`, `REQUIRES_EQUIPMENT` |
| Negative Signal | `REJECTED_MATERIAL_FROM`, `REJECTED_BY` |
| Behavioral | `PROCESSED_POLYMER`, `COMPATIBLE_WITH`, `SIMILAR_PROFILE_SHAPE`, `COMPETES_WITH` |
| Outcome (v1.1) | `RESULTED_IN`, `RESOLVED_FROM` |
| Economic | `RATE_PROFILE`, `PRICE_CORRIDOR` |

#### Removed Edges

- `CONSTRAINED_BY` (MaterialProfile → Freight)
- `BOUND_BY` (Facility → Freight)
- `INFLUENCES` (Freight → Margin)
- `QUALIFIES_FOR` (MaterialProfile → Grade)
- `INFERRED_BY` (Grade → InferenceRule)
- `CONTAMINANT_ROUTE` (KBContaminantSpec → EquipmentType)
- `OFFERED_TO` (Facility → Facility)

---

### 5. Gates

**Both versions have 14 gates.** v0.4.0 simplifies the gate definitions:

| Gate | v0.3.0 | v0.4.0 |
|------|--------|--------|
| Format | Verbose with `type`, `null_behavior`, `relaxed_penalty`, `cypher_override` | Compact with `cypher_fragment`, `type`, `reads` |
| MFI-Process Physics | Reads from `COMPATIBLE_WITH_PROCESS` edge via traversal | Inline WHERE clause with process_type rules |
| Form-Equipment | Composite gate with `cypher_override` | Reads boolean properties directly |

**Key difference:** v0.3.0 gates use traversal aliases and edge properties. v0.4.0 gates are pure Cypher WHERE fragments reading node properties.

---

### 6. Scoring

| Dimension | v0.3.0 | v0.4.0 |
|-----------|--------|--------|
| `geo_proximity` | ✓ (0.15 weight) | ✓ `geo_score` (0.25 weight) |
| `backhaul_proximity` | ✓ (0.05 weight) | ✗ Removed |
| `transaction_depth` | ✓ (0.15 weight) | ✗ Merged into reinforcement |
| `reinforcement` | ✓ (0.15 weight) | ✓ (0.20 weight) |
| `quality` | ✓ (0.10 weight) | ✗ Removed |
| `contamination_headroom` | ✓ (0.10 weight) | ✗ Removed |
| `community` | ✓ multiplicative | ✓ `community_bias` multiplicative |
| `price_alignment` | ✓ (0.05 weight) | ✗ Moved to `future_dimensions` |
| `recency` | ✓ (0.05 weight) | ✗ Merged into reinforcement |
| `kge` | ✓ (0.10 weight) | ✗ Moved to `future_dimensions` |
| `structural_score` | ✗ | ✓ (0.30 weight) |
| `facility_freshness` | ✗ | ✓ (0.10 weight, v1.1) |

**v0.4.0 formula:**
```
(w_structural * structural_score + w_geo * geo_score + w_reinforcement * reinforcement_score + w_freshness * facility_freshness) * community_bias
```

---

### 7. GDS Jobs

| Job | v0.3.0 | v0.4.0 |
|-----|--------|--------|
| `louvain` | ✓ | ✓ |
| `structural` | ✓ | ✓ `structural_precompute` |
| `reinforcement` | ✓ | ✓ `reinforcement_rebuild` |
| `polymer_cooccurrence` | ✓ | ✓ `polymer_co_occurrence` |
| `geo_proximity` | ✓ | ✓ |
| `geo_louvain` | ✓ | ✓ `louvain_geo` |
| `temporal_recency` | ✓ | ✓ |
| `reinforcement_outcomes` | ✓ | ✓ `reinforcement_accepted` |
| `equipment_sync` | ✓ | ✓ |
| `on_demand_rebuild` | ✓ | ✗ Removed |
| `decay_recompute` | ✗ | ✓ (v1.1) |

---

### 8. Sections Removed in v0.4.0

- **Traversal** (Section 3) — v0.3.0 had explicit traversal steps; v0.4.0 embeds in Cypher
- **Sync endpoints** (Section 6) — v0.4.0 has `api_endpoints` instead
- **Negotiation** (Section 9) — `BargainingGame` removed entirely
- **Tenancy** (Section 10) — Multi-tenant config removed
- **Compliance** (Section 11) — SOX/GDPR/HIPAA section removed
- **Units** (Section 12) — Unit conversion definitions removed
- **Plugins** (Section 13) — Custom gate plugins removed
- **Stress test coverage** — Scoreboard removed (was v0.3.0's purpose)

---

### 9. Sections Added in v0.4.0

- **Architecture** — Service, framework, database, coding standards
- **Rollout phases** — 6-phase deployment plan (A→F)
- **Safety checks** — Regression tests, heap monitoring, rollback tests
- **Additive guarantee** — Explicit contract that existing behavior unchanged
- **Schema summary** — Node/edge/job counts with delta
- **Coding standards** — 15 rules for implementation

---

### 10. Key Behavioral Differences

| Behavior | v0.3.0 | v0.4.0 |
|----------|--------|--------|
| **Match direction** | `intake_to_facility` | `material_to_facility` |
| **Query entity** | `Intake` (persisted node) | `IntakeMatchRequest` (Pydantic, not persisted) |
| **Gate evaluation** | Traversal aliases + edge properties | Pure Cypher WHERE on node properties |
| **Scoring** | 9 dimensions + KGE | 4 dimensions + 1 v1.1 + future |
| **Negotiation** | `BargainingGame` enabled | Removed |
| **KGE** | Enabled, 0.10 weight | Phase 4 (disabled) |
| **Temporal decay** | Implicit in recency scoring | Explicit half-life config |
| **Feedback loop** | None | `POST /v1/outcomes` + `TransactionOutcome` node |

---

### Summary

**v0.3.0** = Comprehensive stress-test spec proving engine feature coverage
**v0.4.0** = Production-ready spec with architecture, phased rollout, and additive guarantees

The core matching logic (14 gates, 4 base scoring dimensions) is preserved. v0.4.0 adds topology layers for KGE/GDS enrichment without changing the match query output.
