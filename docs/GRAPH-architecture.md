<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [architecture, graph]
owner: engine-team
status: active
/L9_META -->

# GRAPH Cognitive Engine - Architecture Documentation

## Overview

The **GRAPH Cognitive Engine** is Layer 3 (Analysis) of the RevOpsOS / L9 platform's intelligence stack. It consumes enriched entities from Layer 2 (ENRICH) and runs **deterministic intelligence** via:

- **14 WHERE gates** (hard filters)
- **4 scoring dimensions** (soft assessment)
- **Louvain community detection** (structural patterns)
- **Temporal decay models** (recency weighting)
- **Outcome feedback loops** (self-correction)
- **KGE embeddings** (CompoundE3D, Phase 4)

## Architecture Layers

```
┌─────────────────────────────────────────┐
│  Layer 1: IDENTIFICATION                │
│  (Clay, Apollo, ZoomInfo)               │
│  ❌ Not our domain - commodity           │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Layer 2: UNDERSTANDING (ENRICH)        │
│  • Schema Discovery                      │
│  • Multi-pass Convergence Loop          │
│  • Domain KB Injection                   │
│  • Confidence Scoring (0.0-1.0)         │
│  • Full Provenance Chains               │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Layer 3: ANALYSIS (GRAPH) ← WE ARE HERE│
│  • 14 WHERE Gates (deterministic)        │
│  • 4 Scoring Dimensions (probabilistic)  │
│  • Community Detection (Louvain)         │
│  • Temporal Decay (recency)              │
│  • Outcome Feedback (learning)           │
│  • KGE Embeddings (CompoundE3D)          │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Downstream Services (Consume GRAPH)    │
│  • SCORE: Rank entities                  │
│  • ROUTE: Assignment logic               │
│  • FORECAST: Predictive models           │
│  • SIGNAL: Real-time alerts              │
│  • HEALTH: System diagnostics            │
│  • HANDOFF: Cross-team coordination      │
└─────────────────────────────────────────┘
```

## Core Differentiators

### What Competitors Do (Layer 1 Only)
- **Clay/Apollo/ZoomInfo**: Identification only
- **RB2B/Clearbit**: Contact discovery
- **Terminus/6sense**: Intent signals

**All stop at Layer 1. They answer "WHO is this?"**

### What We Do (Layers 2 + 3)
- **ENRICH**: Schema discovery, not just field-filling
- **GRAPH**: Deterministic intelligence, not just scoring
- **Convergence Loop**: Inference creates enrichment targets creates inference
- **Domain KB Injection**: Vertical-specific intelligence (e.g., plastics recycling)

**We answer "WHO + WHAT + WHY + HOW WELL?"**

---

## 14 WHERE Gates (Deterministic Filters)

Gates are **hard filters** that entities MUST pass. Each returns `GateResult`:
- `passed: bool` — Did entity meet threshold?
- `score: float` — How well did it pass? (0.0–1.0)
- `evidence: Dict` — Supporting data for audit trail

### Material-Based Gates
1. **MATERIAL_MATCH** — Does company produce required material type?
2. **GRADE_COMPATIBILITY** — Is material grade acceptable?
3. **CONTAMINATION_TOLERANCE** — Within contamination limits?
4. **MFI_RANGE_MATCH** — Melt Flow Index in target range?

### Facility-Based Gates
5. **FACILITY_CERTIFICATION** — Has ISO/FDA/EPA certifications?
6. **FACILITY_TIER** — Meets tier requirement (1=best, 10=worst)?
7. **PROCESSING_CAPABILITY** — Can process material type?
8. **CAPACITY_THRESHOLD** — Has sufficient capacity (kg/month)?

### Relationship-Based Gates
9. **EXISTING_RELATIONSHIP** — Prior successful engagement?
10. **GEOGRAPHIC_PROXIMITY** — Within service radius?
11. **SUPPLY_CHAIN_POSITION** — Right position in chain (upstream/downstream)?

### Compliance/Risk Gates
12. **COMPLIANCE_STATUS** — Meets regulatory requirements?
13. **CREDIT_STANDING** — Financial stability check?
14. **EXCLUSION_LIST** — Not on do-not-engage list?

### Implementation Pattern

```python
gate_result = gate_evaluator.evaluate_gate(
    gate=WhereGate.MATERIAL_MATCH,
    entity_id='company_123',
    context={
        'required_material': 'HDPE',
        'min_products': 3
    }
)

if not gate_result.passed:
    # Entity fails - short circuit, don't score dimensions
    return EntityScore(composite_score=0.0)
```

---

## 4 Scoring Dimensions (Soft Assessment)

Dimensions are **probabilistic scores** (0.0–1.0) that measure fit quality. Each returns `ScoringResult`:
- `score: float` — Composite dimension score
- `components: Dict[str, float]` — Sub-scores that contribute
- `confidence: float` — How confident are we? (0.0–1.0)
- `provenance: List[str]` — Source entity IDs

### 1. CAPABILITY — "Can they do what we need?"
**Components:**
- Facility count (how many facilities?)
- Product count (how diverse is portfolio?)
- Material diversity (how many material types?)
- Certifications (ISO/FDA/EPA certs)

**Cypher Query:**
```cypher
MATCH (c:Company {id: $company_id})
OPTIONAL MATCH (c)-[:OPERATES]->(f:Facility)
OPTIONAL MATCH (c)-[:PRODUCES]->(p:Product)
OPTIONAL MATCH (p)-[:CONTAINS]->(m:Material)
RETURN c.id as entity_id,
       count(DISTINCT f) as facility_count,
       count(DISTINCT p) as product_count,
       count(DISTINCT m) as material_count,
       collect(DISTINCT f.certifications) as certifications
```

**Scoring Logic:**
```python
facility_score = min(1.0, facility_count / 3.0)
product_score = min(1.0, product_count / 5.0)
material_diversity = min(1.0, material_count / 4.0)

capability_score = (
    facility_score * 0.4 +
    product_score * 0.3 +
    material_diversity * 0.3
)
```

### 2. COMPATIBILITY — "Does it fit our requirements?"
**Components:**
- Grade match (exact vs acceptable vs incompatible)
- MFI compatibility (within target range?)
- Product count (how many compatible products?)

**Cypher Query:**
```cypher
MATCH (c:Company {id: $company_id})-[:PRODUCES]->(p:Product)-[:CONTAINS]->(m:Material)
WHERE m.type = $required_material
WITH c, m, p,
     CASE
       WHEN m.grade = $required_grade THEN 1.0
       WHEN m.grade IN $acceptable_grades THEN 0.8
       ELSE 0.3
     END as grade_match
RETURN c.id as entity_id,
       avg(grade_match) as avg_grade_match,
       count(p) as compatible_products
```

**Scoring Logic:**
```python
compatibility_score = (
    grade_match_score * 0.5 +
    product_count_score * 0.2 +
    mfi_score * 0.3
)
```

### 3. CAPACITY — "Can they handle the volume?"
**Components:**
- Total capacity (sum across facilities)
- Available capacity (unused capacity)
- Utilization rate (60-80% is sweet spot)

**Cypher Query:**
```cypher
MATCH (c:Company {id: $company_id})-[:OPERATES]->(f:Facility)
RETURN c.id as entity_id,
       sum(f.capacity) as total_capacity,
       avg(f.utilization) as avg_utilization,
       sum(f.capacity * (1.0 - f.utilization)) as available_capacity
```

**Scoring Logic:**
```python
adequacy_score = min(1.0, available_capacity / required_capacity)

# Utilization sweet spot: 60-80%
if 0.6 <= utilization <= 0.8:
    utilization_score = 1.0
elif utilization < 0.6:
    utilization_score = 0.7  # Under-utilized
else:
    utilization_score = max(0.0, 1.0 - (utilization - 0.8) * 2)

capacity_score = adequacy_score * 0.7 + utilization_score * 0.3
```

### 4. COMMITMENT — "Will they follow through?"
**Components:**
- Success rate (successful interactions / total)
- Response time (how fast do they respond?)
- Consistency (stddev of response times)

**Cypher Query:**
```cypher
MATCH (c:Company {id: $company_id})-[r:INTERACTED_WITH]->()
WHERE r.timestamp > datetime() - duration({days: 365})
WITH c, r,
     CASE
       WHEN r.outcome = 'success' THEN 1.0
       WHEN r.outcome = 'partial' THEN 0.5
       ELSE 0.0
     END as outcome_score
RETURN c.id as entity_id,
       count(r) as total_interactions,
       avg(outcome_score) as success_rate,
       avg(r.response_time_hours) as avg_response_time,
       stdDev(r.response_time_hours) as response_time_consistency
```

**Scoring Logic:**
```python
success_score = success_rate  # Primary indicator
response_score = 1.0 / (1.0 + avg_response_time / 24.0)
consistency_score = 1.0 / (1.0 + response_consistency / 12.0)

commitment_score = (
    success_score * 0.6 +
    response_score * 0.25 +
    consistency_score * 0.15
)
```

---

## Composite Scoring

Final entity score combines gates + dimensions:

```python
# Step 1: Evaluate all gates
gate_results = [evaluate_gate(gate) for gate in gates]
gate_pass_rate = sum(gr.passed for gr in gate_results) / len(gate_results)

# Step 2: If required gates fail, short circuit
required_pass = all(gr.passed for gr in gate_results if gr.gate in required_gates)
if not required_pass:
    return EntityScore(composite_score=0.0)

# Step 3: Score dimensions
dimension_scores = {
    dim: score_dimension(dim, entity_id, context)
    for dim in ScoringDimension
}

# Step 4: Weighted composite
weights = {
    CAPABILITY: 0.25,
    COMPATIBILITY: 0.30,
    CAPACITY: 0.25,
    COMMITMENT: 0.20
}

composite = sum(
    dimension_scores[dim].score * weights[dim]
    for dim in ScoringDimension
)

# Step 5: Apply gate pass rate modifier
composite *= gate_pass_rate

return EntityScore(
    entity_id=entity_id,
    gate_results=gate_results,
    dimension_scores=dimension_scores,
    composite_score=composite
)
```

---

## Louvain Community Detection

**Purpose:** Discover structural patterns (e.g., supply chain clusters, competitor groups)

**Neo4j GDS Query:**
```cypher
CALL gds.louvain.stream('company-graph', {
  relationshipWeightProperty: 'interaction_strength',
  includeIntermediateCommunities: false
})
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) as company, communityId
RETURN communityId,
       collect(company.id) as members,
       count(company) as size
ORDER BY size DESC
```

**Output:**
- `community_id` — Unique community identifier
- `members` — Set of entity IDs in community
- `modularity` — Community quality metric (0.0–1.0)
- `density` — Internal connection density

**Use Cases:**
- **Supply chain mapping** — Identify upstream/downstream clusters
- **Competitor analysis** — Find companies serving similar markets
- **Cross-sell opportunities** — Discover related industries

---

## Temporal Decay

**Purpose:** Recent data is more valuable than stale data

**Decay Function:**
```python
def temporal_decay(timestamp: datetime, half_life_days: int = 90) -> float:
    """Exponential decay: score * e^(-λt)"""
    days_old = (datetime.utcnow() - timestamp).days
    decay_factor = math.exp(-math.log(2) * days_old / half_life_days)
    return decay_factor
```

**Applied To:**
- Interaction history (COMMITMENT dimension)
- Facility utilization data (CAPACITY dimension)
- Enrichment confidence scores (from ENRICH)

**Example:**
```python
interaction_score = base_score * temporal_decay(interaction.timestamp, half_life_days=90)
# 90 days old → 50% weight
# 180 days old → 25% weight
# 365 days old → ~3% weight
```

---

## Outcome Feedback Loop

**Purpose:** Self-correct scoring based on actual outcomes

### Phase 1: Initial Scoring
```python
# Score entity using gates + dimensions
entity_score = engine.evaluate_entity(entity_id, gates, context)
# composite_score = 0.85
```

### Phase 2: Outcome Capture
```python
# After engagement, capture actual outcome
outcome = {
    'entity_id': entity_id,
    'predicted_score': 0.85,
    'actual_outcome': 'success',  # or 'failure'
    'actual_score': 0.95,  # Measured performance
    'timestamp': datetime.utcnow()
}
```

### Phase 3: Model Adjustment
```python
# Calculate prediction error
error = actual_score - predicted_score  # 0.95 - 0.85 = +0.10

# Adjust dimension weights
if error > 0.1:  # Under-predicted
    # Increase weight of dimensions that signaled high
    for dim, result in entity_score.dimension_scores.items():
        if result.score > 0.8:
            weights[dim] *= 1.05  # Boost weight
```

### Phase 4: Create Inference Target for ENRICH
```python
# High error = need better enrichment
if abs(error) > 0.2:
    inference_packet = PacketEnvelope(
        payload={
            'entity_id': entity_id,
            'inference_type': 'capability_reassessment',
            'reason': f'prediction_error={error:.2f}',
            'priority': 'high'
        },
        source='GRAPH',
        destination='ENRICH'
    )
    enrich_service.submit(inference_packet)
```

**This is the convergence loop:** GRAPH inference creates ENRICH targets creates GRAPH data.

---

## Knowledge Graph Embeddings (KGE) - Phase 4

**Purpose:** Learn entity representations for similarity search, prediction, completion

### CompoundE3D Model
- **Architecture:** 3D rotational embeddings (head, relation, tail)
- **Training:** Link prediction on (entity, relationship, entity) triples
- **Output:** Dense vectors (dim=128-512) capturing entity semantics

### Feature Vector Extraction
```python
feature_vector = {
    'entity_id': 'company_123',
    'entity_types': ['Company', 'Manufacturer'],
    'out_degree': 45,  # Number of outgoing relationships
    'relationship_types': ['PRODUCES', 'OPERATES', 'INTERACTED_WITH'],
    'attributes': {
        'industry': 'plastics_recycling',
        'employee_count': 250,
        'revenue': 15000000
    }
}
```

### Embedding Training
```python
# Prepare triples
triples = [
    ('company_123', 'PRODUCES', 'product_456'),
    ('company_123', 'OPERATES', 'facility_789'),
    ('product_456', 'CONTAINS', 'material_hdpe')
]

# Train CompoundE3D
model = CompoundE3D(dim=256)
model.train(triples, epochs=100)

# Get embedding
embedding = model.embed('company_123')  # [256-dim vector]
```

### Use Cases
1. **Entity similarity** — Find companies similar to top performers
2. **Relationship prediction** — Predict missing links (e.g., likely to produce X)
3. **Attribute completion** — Infer missing entity attributes
4. **Anomaly detection** — Entities with unusual embedding patterns

---

## Graph Schema (Neo4j)

### Node Labels
- `Company` — Organizations (suppliers, customers, competitors)
- `Contact` — People (decision-makers, influencers)
- `Product` — Goods/services offered
- `Material` — Raw materials (HDPE, LDPE, PET, etc.)
- `Facility` — Physical locations (plants, warehouses)
- `Interaction` — Engagement events (calls, meetings, emails)

### Relationship Types
- `PRODUCES` — Company → Product
- `CONTAINS` — Product → Material
- `OPERATES` — Company → Facility
- `INTERACTED_WITH` — Company → Company (weighted by strength)
- `WORKS_AT` — Contact → Company
- `LOCATED_IN` — Facility → Location

### Property Examples
```cypher
// Company node
(c:Company {
  id: 'company_123',
  name: 'RecycleCorp',
  industry: 'plastics_recycling',
  employee_count: 250,
  revenue: 15000000,
  credit_rating: 'A',
  created_at: datetime()
})

// Facility node
(f:Facility {
  id: 'facility_789',
  name: 'North Plant',
  tier: 2,
  capacity: 50000,  // kg/month
  utilization: 0.72,
  certifications: ['ISO_9001', 'FDA_Approved'],
  lat: 35.7796,
  lon: -78.6382
})

// Material node
(m:Material {
  id: 'material_hdpe',
  type: 'HDPE',
  grade: 'post-consumer',
  contamination_tolerance: 0.02,
  mfi_range: '0.5-1.5'
})

// Interaction relationship
(c1)-[r:INTERACTED_WITH {
  timestamp: datetime(),
  outcome: 'success',
  satisfaction_score: 0.9,
  response_time_hours: 4.5,
  interaction_type: 'sales_call'
}]->(c2)
```

---

## PacketEnvelope Protocol (Inter-Service Communication)

**All data flows between constellation nodes use PacketEnvelope:**

```python
@dataclass
class PacketEnvelope:
    """Immutable communication contract"""
    payload: Dict[str, any]
    source: str         # Originating service
    destination: str    # Target service
    packet_id: str = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    provenance: List[str] = field(default_factory=list)
```

### Example: ENRICH → GRAPH
```python
# ENRICH completes convergence, sends enriched entity to GRAPH
packet = PacketEnvelope(
    payload={
        'entity_id': 'company_123',
        'entity_type': 'Company',
        'enrichment_data': {
            'industry': 'plastics_recycling',
            'facility_count': 3,
            'material_types': ['HDPE', 'LDPE']
        },
        'confidence': 0.92,
        'convergence_passes': 3
    },
    source='ENRICH',
    destination='GRAPH'
)

graph_service.ingest(packet)
```

### Example: GRAPH → SCORE
```python
# GRAPH completes scoring, sends results to SCORE
packet = PacketEnvelope(
    payload={
        'entity_id': 'company_123',
        'composite_score': 0.85,
        'dimension_scores': {
            'capability': 0.80,
            'compatibility': 0.92,
            'capacity': 0.78,
            'commitment': 0.88
        },
        'gates_passed': 12,
        'gates_failed': 2
    },
    source='GRAPH',
    destination='SCORE'
)

score_service.rank(packet)
```

---

## Revenue Tier Upsell Path

Each tier naturally upsells to the next:

### Seed (Free)
- **Includes:** Layer 1 identification only (Clay/Apollo data)
- **Limitation:** No ENRICH, no GRAPH
- **Hook:** "See which companies exist, but not which ones fit"

### Enrich ($500/mo)
- **Includes:** Layer 2 ENRICH (schema discovery, convergence loop)
- **Value:** Discover fields you didn't know you needed
- **Hook:** "Now you know WHAT they do, but not WHO to prioritize"

### Discover ($2K/mo)
- **Includes:** Layer 3 GRAPH (gates, dimensions, communities)
- **Value:** Deterministic ranking, not just scoring
- **Hook:** "You can rank them, but can you predict outcomes?"

### Autonomous ($5K-10K/mo)
- **Includes:** Full constellation (SCORE, ROUTE, FORECAST, SIGNAL, HEALTH, HANDOFF)
- **Value:** Fully automated revenue operations
- **Hook:** "The system runs itself, you just approve exceptions"

---

## Infrastructure Stack

### Neo4j + GDS
- **Version:** Neo4j 5.18+ with GDS 2.x plugin
- **Deployment:** Docker Compose (dev) → Kubernetes (prod)
- **Scaling:** Read replicas for query load, write primary for ingestion

### PostgreSQL + pgvector
- **Purpose:** Memory substrate shared with ENRICH
- **Schema:** Entity metadata, enrichment history, convergence state
- **Vector Index:** Embedding similarity search (KGE Phase 4)

### Redis
- **Purpose:** Distributed cache, state persistence, pub/sub
- **Use Cases:** Gate evaluation cache, dimension score cache, job queue

### L9 Chassis
- **Auth:** JWT-based service-to-service auth
- **Ingress:** API Gateway with rate limiting
- **Observability:** Prometheus metrics, Grafana dashboards, structured logs

### Terraform IaC
- **Modules:** Neo4j cluster, PostgreSQL RDS, Redis Cluster, EKS node groups
- **State:** S3 backend with DynamoDB locking
- **Environments:** dev, staging, prod

---

## Competitive Positioning

### What Competitors Claim
- "AI-powered enrichment" (everyone says this)
- "Accurate contact data" (Layer 1 commodity)
- "Intent signals" (purchase intent, not capability)

### What Competitors Actually Do
- **Clay/Apollo:** Identification + basic enrichment (Layer 1 + partial Layer 2)
- **ZoomInfo:** Contact discovery + company data (Layer 1 only)
- **Clearbit/RB2B:** Website visitors + firmographics (Layer 1 only)
- **6sense/Terminus:** Intent + engagement scoring (Layer 1 + behavioral signals)

**None do schema discovery. None do deterministic intelligence. None have convergence loops.**

### What We Do Differently

| Feature | Competitors | Us |
|---------|-------------|-----|
| **Schema Discovery** | ❌ Fixed fields | ✅ Discovers fields you didn't know existed |
| **Multi-pass Convergence** | ❌ Single pass | ✅ Inference → enrichment → inference loop |
| **Domain KB Injection** | ❌ Generic models | ✅ Vertical-specific intelligence (plastics, etc.) |
| **Deterministic Gates** | ❌ Scoring only | ✅ Hard filters before soft scoring |
| **4D Scoring** | ❌ Single score | ✅ Capability, Compatibility, Capacity, Commitment |
| **Community Detection** | ❌ None | ✅ Louvain clustering (supply chain mapping) |
| **Temporal Decay** | ❌ Static | ✅ Recency-weighted scoring |
| **Outcome Feedback** | ❌ None | ✅ Self-correcting from actual results |
| **KGE Embeddings** | ❌ None | ✅ CompoundE3D for similarity/prediction |

---

## Example Use Case: Plastics Recycling Vertical

### Input (from ENRICH)
```json
{
  "entity_id": "company_123",
  "entity_type": "Company",
  "name": "RecycleCorp",
  "industry": "plastics_recycling",
  "enrichment_data": {
    "facility_count": 3,
    "material_types": ["HDPE", "LDPE"],
    "certifications": ["ISO_9001", "FDA_Approved"],
    "annual_capacity": 150000
  },
  "confidence": 0.92
}
```

### Context (from Sales Request)
```python
context = {
    'required_material': 'HDPE',
    'required_grade': 'post-consumer',
    'target_mfi': 0.8,
    'required_capacity': 50000,  # kg/month
    'max_tier': 2,
    'lookback_days': 365
}
```

### Evaluation
```python
gates = [
    WhereGate.MATERIAL_MATCH,        # ✅ Produces HDPE
    WhereGate.GRADE_COMPATIBILITY,   # ✅ Post-consumer grade
    WhereGate.MFI_RANGE_MATCH,       # ✅ MFI 0.5-1.5 (target 0.8)
    WhereGate.FACILITY_TIER,         # ✅ Tier 2 facilities
    WhereGate.CAPACITY_THRESHOLD,    # ✅ 150K > 50K required
    WhereGate.COMPLIANCE_STATUS      # ✅ ISO + FDA certified
]

score = engine.evaluate_entity('company_123', gates, context)
```

### Output
```python
EntityScore(
    entity_id='company_123',
    composite_score=0.87,
    gates_passed=6,
    gates_failed=0,
    dimension_scores={
        CAPABILITY: ScoringResult(score=0.85, confidence=0.90),
        COMPATIBILITY: ScoringResult(score=0.92, confidence=0.88),
        CAPACITY: ScoringResult(score=0.81, confidence=0.85),
        COMMITMENT: ScoringResult(score=0.88, confidence=0.92)
    }
)
```

### Downstream Action
```python
# Send to SCORE for ranking
score_packet = PacketEnvelope(
    payload={'entity_score': score.to_dict()},
    source='GRAPH',
    destination='SCORE'
)

# If high score, send to ROUTE for assignment
if score.composite_score > 0.8:
    route_packet = PacketEnvelope(
        payload={
            'entity_id': 'company_123',
            'score': 0.87,
            'recommended_action': 'assign_to_senior_rep'
        },
        source='GRAPH',
        destination='ROUTE'
    )
```

---

## Key Takeaways

1. **GRAPH = Layer 3** — Analysis layer that consumes enriched entities from ENRICH
2. **14 WHERE Gates** — Deterministic filters (pass/fail) before scoring
3. **4 Scoring Dimensions** — Capability, Compatibility, Capacity, Commitment
4. **Convergence Loop** — GRAPH inference creates ENRICH targets creates GRAPH data
5. **Domain KB Injection** — Vertical-specific intelligence (plastics, manufacturing, etc.)
6. **Competitive Moat** — No competitor does schema discovery + deterministic gates + convergence
7. **PacketEnvelope** — Immutable protocol for inter-service communication
8. **Revenue Tiers** — Natural upsell from Seed → Enrich → Discover → Autonomous

**The loop between ENRICH and GRAPH is the product. That's the architectural pattern no one else has.**
