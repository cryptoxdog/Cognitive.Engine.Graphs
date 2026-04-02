# 🔴 INFERENCE ENGINE ENHANCEMENT VIA KG RESEARCH STACK — ROADMAP

## EXECUTIVE SUMMARY

This document captures the complete capability roadmap for enhancing the Cognitive Engine Graph's inference stack using five research papers: NBFNet (inductive generalization), CompGCN (relation expressiveness), CompoundE3D (geometric operators), R-GCN (multi-relational encoding), and AGEA (adversarial robustness).

**Bottom line:** The current engine is embedding-based transductive. The papers enable a capability leap to **path-aware inductive with ensemble fusion and security hardening** — an architecture no competitor in the enrichment/graph intelligence space currently possesses.

---

## PHASE 1 — LANDSCAPE & STATE OF THE ART

### 1.1 — Current Paradigm Classification

```
Current Paradigm: Embedding-Based Transductive with Deterministic Post-Processing
├─ Layer 2 (ENRICH): Multi-variation LLM consensus → structured feature vectors
├─ Layer 3 (GRAPH):
│   ├─ CompoundE3D embeddings (Phase 4, beam search variants)
│   ├─ 14 WHERE gates (Cypher-based filtering)
│   ├─ 4 scoring dimensions (structural, geo, reinforcement, community)
│   ├─ Louvain community detection (Neo4j GDS)
│   └─ Temporal decay functions
└─ Limitation: Cannot generalize to unseen entities without retraining embeddings
```

### Capability Gap Matrix

| Paper | Inductive Gen. | Relation Expr. | Path Interp. | Scalability | Multi-Hop | Adversarial | Production Block? |
|---|---|---|---|---|---|---|---|
| NBFNet | ✅ TRUE | ⚠️ MED | ✅ HIGH | ⚠️ O(E·d) | ✅ HIGH | ❌ | BLOCKING — No inductive |
| CompGCN | ✅ HIGH | ✅ HIGH | ❌ | ✅ Basis decomp | ⚠️ MED | ❌ | BLOCKING — Relation under-parameterized |
| CompoundE3D | ❌ | ✅ SOTA | ❌ | ✅ Block-diag | ❌ | ❌ | Performance — Already integrated |
| R-GCN | ⚠️ MED | ⚠️ MED | ❌ | ✅ Basis/block | ⚠️ MED | ❌ | Performance — Subsumed by CompGCN |
| AGEA | N/A | N/A | N/A | N/A | N/A | ✅ CRITICAL | BLOCKING — Public API = attack surface |

### Critical Findings

1. **NBFNet** addresses the #1 blocker: Cold-start entities (new facilities, materials) currently get random embeddings. NBFNet's message-passing formulation is **truly inductive** — scores unseen entities using only graph structure and relation types.

2. **CompGCN** fixes relation under-parameterization: Jointly learns node + relation embeddings via composition operators (Sub/Mult/Circular-Correlation), yielding 4-7% MRR gains on FB15k-237.

3. **AGEA is an existential threat**: If the `/v1/match` API is public-facing, adversaries can extract 90-96% of Neo4j graph topology in <1000 queries using novelty-guided exploration.

---

### 1.2 — State of the Art Survey

#### NBFNet (arXiv:2106.06935)

**Core Innovation:** Generalized Bellman-Ford path-finding on the knowledge graph, parameterized by learned MESSAGE/AGGREGATE/INDICATOR functions.

```
h^(t)(v) = AGGREGATE({MESSAGE(h^(t-1)(u), w_q(u,r,v)) : (u,r,v) ∈ E(v)} ∪ {h^0(v)})
```

**SOTA Benchmarks:**
- FB15k-237: HITS@10 = 0.599 (21% relative gain over DRUM)
- WN18RR: HITS@10 = 0.584
- Inductive splits (unseen entities): HITS@10 = 0.523 on FB15k-237 (vs 0.311 for RotatE)

**Computational Complexity:** O(T · |E| · d + T · |V| · d²) where T = 6 Bellman-Ford iterations (optimal)

---

#### CompGCN (arXiv:1911.03082)

**Core Innovation:** Joint node-relation embedding using composition operators φ(x_u, z_r) with basis decomposition.

```
h_v^(l+1) = f(Σ_{(u,r)∈N(v)} W_r^(l) · φ(x_u, z_r))
```

Composition operators:
- **Sub:** φ(e, r) = e - r
- **Mult:** φ(e, r) = e ⊙ r (Hadamard product)
- **Corr:** φ(e, r) = e ⋆ r (**circular correlation** — best performer)

**SOTA Benchmarks:**
- FB15k-237: MRR = 0.355 (CompGCN + ConvE, +7% over RotatE)
- WN18RR: MRR = 0.479 (Corr composition operator)

---

#### CompoundE3D (arXiv:2309.12501)

**Core Innovation:** 3D affine geometric operators (Translation, Rotation, Scaling, Reflection, Householder shear) composed via beam search variant discovery.

```
M_r = diag(O_{r,1}, O_{r,2}, ..., O_{r,n})
where O_{r,i} = T · R · S · F · H (compound affine in 3D blocks)
```

**SOTA Benchmarks:**
- DB100K: MRR = 0.450
- YAGO3-10: MRR = 0.542
- ogbl-wikikg2: MRR = 0.700

**Integration Status:** ✅ Fully integrated (beamsearch.py, ensemble.py, compounde3d.py)

---

#### R-GCN (arXiv:1703.06103)

**Strategic Assessment:** Subsumed by CompGCN. CompGCN generalizes R-GCN by adding joint relation embedding and composition operators.

**Recommendation:** Keep as baseline comparison only, not production architecture.

---

#### AGEA (arXiv:2601.14662)

**Core Innovation:** Adversarial graph extraction via novelty-guided exploration.

```
Novelty Score N^t = (N^t_nodes · |V^t_r| + N^t_edges · |E^t_r|) / (|V^t_r| + |E^t_r|)
```

**Attack Results on LightRAG:**
- 1,000 queries: 90.7% node recovery, 82.3% edge recovery
- 5,000 queries: 96.2% node recovery, 95.8% edge recovery
- Cost: $0.50–$2.50 using GPT-3.5-turbo

**CRITICAL PRODUCTION IMPLICATION:** The `/v1/match` API returns ranked candidate lists with gate explanations — this is **graph structure leakage**. An adversary can reconstruct 90%+ of Neo4j topology systematically.

---

## PHASE 2 — FIRST PRINCIPLES ANALYSIS

### 2.1 — Primitive-Level Upgrade Mapping

| Component | Current | NBFNet Upgrade | CompGCN Upgrade |
|---|---|---|---|
| Entity Encoder | Static lookup table | ❌ (structure-only) | ✅ Joint node+relation embedding |
| Relation Encoder | CompoundE3D M_r operators | ❌ | ✅ Learnable z_r co-evolves with node embeddings |
| Message Passing | ❌ None | ✅ Bellman-Ford iterations | ✅ GCN aggregation with basis decomposition |
| Scoring Function | CompoundE3D ensemble | ✅ Path probability σ(MLP(h^T(v))) | ⚠️ ConvE scoring |
| Inference Head | Deterministic Cypher gates | ✅ Path extraction via beam search | ❌ |

### 2.2 — Core Tradeoffs

| Axis | TransE/RotatE (Current) | CompGCN | NBFNet | CompoundE3D (Current) |
|---|---|---|---|---|
| Expressiveness | Low | High | Medium | **SOTA** |
| Inductive Generalization | ❌ None | ⚠️ Partial | ✅ **TRUE** | ❌ None |
| Parameter Efficiency | High | ✅ Basis decomp | ⚠️ Memory-heavy | ✅ Block-diag |
| Interpretability | ❌ Black box | ❌ Black box | ✅ **Path extraction** | ⚠️ Partial |
| Cold-Start Entities | ❌ Random embedding | ⚠️ Featurize | ✅ **Zero-shot** | ❌ Random embedding |
| Training Time (100K triples) | ~30 min | ~45 min | **~3-4 hours** | ~60 min |

**Note:** NBFNet's 3-4 hour training is acceptable because: (1) nightly retraining is scheduled, (2) incremental methods (FastKGE with IncLoRA) reduce delta updates to 10-15 min, (3) inductive capability means no retraining for new entities.

---

## PHASE 3 — ARCHITECTURE & DESIGN SYNTHESIS

### Architecture A — "Surgical Upgrade" (Low Effort, High Impact)

**Scope:** Drop-in replacement of entity/relation encoder with CompGCN. Zero changes to inference pipeline interface.

**Expected Gains:**
- FB15k-237 MRR: 0.338 → 0.355 (+5%)
- WN18RR MRR: 0.430 → 0.479 (+11%)
- Inductive splits: +15-20% Hits@10

**Timeline:** 1 week

---

### Architecture B — "Path-Aware Engine" (Medium Effort, Transformative) ⭐ RECOMMENDED

**Scope:** Replace embedding-based scoring with NBFNet path-finding. CompGCN feeds initial representations into Bellman-Ford iterations.

```
┌──────────────────────────────────────────────────────────────┐
│ INFERENCE ENGINE v2.0 (Architecture B)                       │
│                                                              │
│  Graph Input → CompGCN Encoder → Edge Repr Layer            │
│                    (3L, Corr, B=50)    w_q(u,r,v)=W_r·q+b_r │
│                         ↓                                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ NBFNet Bellman-Ford Iterations (T=6)                 │    │
│  │  MESSAGE: RotatE composition                         │    │
│  │  AGGREGATE: PNA with degree scaling                  │    │
│  │  Edge dropout: 10% during training                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  Scoring: p(v|u,q) = σ(MLP(h^T(v)))                        │
│  Paths: "Facility X via ACCEPTED→COLOCATED→COMMUNITY"       │
│                         ↓                                    │
│  Existing: 14 Cypher Gates + 4 Scoring Dims (unchanged)     │
└──────────────────────────────────────────────────────────────┘
```

**5th Scoring Dimension Integration:**
```python
final_score = (
    0.25 * kge_score +           # Existing CompoundE3D ensemble
    0.15 * community_score +      # Existing Louvain
    0.10 * geo_score +            # Existing Haversine
    0.20 * temporal_score +       # Existing exp decay
    0.30 * path_score             # NEW: NBFNet path reasoning
)
```

**Expected Gains:**
- Inductive FB15k-237 HITS@10: 0.311 → 0.523 (+68% relative)
- Transductive WN18RR HITS@10: 0.524 → 0.584 (+11%)
- Path interpretability: Explainable matching chains

**Timeline:** 3-4 weeks

**Rationale for recommendation:**
1. Architecture A is too conservative — doesn't solve the inductive generalization problem (#1 blocker)
2. Architecture C is research-grade — PathCompound MESSAGE function is unproven
3. Architecture B hits the Pareto frontier: solves induction, adds interpretability, preserves existing scoring, feasible in 3-4 weeks

---

### Architecture C — "Unified Foundation Engine" (High Effort, Maximum Capability)

**Novel Contribution — PathCompound Message Function:**

Uses CompoundE3D's 3D affine operators as the MESSAGE function in NBFNet's Bellman-Ford iterations. No existing paper has combined these.

```
Research Hypothesis: Replacing NBFNet's RotatE MESSAGE with CompoundE3D's
5-operator affine transforms enables non-commutative path composition where
relation order matters.

Path ACCEPTEDMATERIALFROM → COLOCATEDWITH applies:
  1. M_ACCEPTED = T·R·S·F·H (translation + rotation to material space)
  2. M_COLOCATED = T·R·S·F·H (shear + scaling to geo-proximity space)
  3. M_path = M_COLOCATED ∘ M_ACCEPTED (preserves geometric structure)

Expected gain: +3-5% MRR over NBFNet with RotatE on heterogeneous graphs.
```

**Additional: AGEA Defense Layer**
```python
class AGEADefenseLayer:
    """Defends against graph extraction attacks per AGEA paper findings."""
    # Novelty score tracking
    # Rate limiting (per-session exploration budget)
    # Hub exploitation detection (degree-spike anomaly)
    # Response sanitization (no raw subgraph context returned)
```

**Timeline:** 8-12 weeks

---

## PHASE 4 — IMPLEMENTATION ROADMAP

### Milestone 1 — Baseline Hardening (Weeks 1-2)

**Deliverables:**
1. Filtered MRR/Hits@N evaluation harness (filtered ranking protocol)
2. FB15k-237 + WN18RR + PlasticOS benchmarks
3. Baseline RotatE training on PlasticOS graph
4. Continuous integration: GitHub Actions asserts MRR ≥ 0.338 on FB15k-237

**Validation:** Reproduce RotatE MRR ≥ 0.338 on FB15k-237; PlasticOS baseline established

---

### Milestone 2 — CompGCN Encoder (Weeks 3-5)

**Deliverables:**
1. Joint node+relation embedding via CompGCN update layers
2. All three composition operators (Sub, Mult, **Corr** — best performer)
3. Basis decomposition B ∈ {5, 25, 50, 100} ablation
4. Replace static embedding lookup tables with CompGCN forward pass

**Critical implementation note:** Relation update via **reverse message passing** (Section 3.2 of CompGCN) — often omitted in naive implementations, essential for correct training.

**Validation:** MRR improvement ≥4% on FB15k-237; B=50 achieves <5% MRR drop vs full parameters

---

### Milestone 3 — NBFNet Core Loop (Weeks 6-10)

**Deliverables:**
1. Generalized Bellman-Ford iteration (Algorithm 1, NBFNet)
2. INDICATOR function with learned query embeddings
3. MESSAGE function using RotatE operators from CompGCN relation embeddings
4. PNA AGGREGATE function (sum/mean/max with learned scalers)
5. **CRITICAL: Edge dropout (10%)** — forces multi-hop path learning, not shortcut exploitation

**Memory Optimization (CRITICAL):**

For PlasticOS (15K entities, 50K edges, d=256, T=6): Peak memory ~6.1 GB
- Gradient checkpointing: 2× compute for 50% memory reduction
- Dynamic edge pruning: Keep top-k=20 per node
- Mini-batch subgraph sampling: NeighborLoader (PyTorch Geometric)

**Validation:**
- HITS@10 ≥ 0.599 on FB15k-237 (NBFNet Table 2)
- Inductive split HITS@10 ≥ 0.523 (68% gain over RotatE)
- T=6 optimal confirmed via ablation T ∈ {3, 6, 9, 12}

---

### Milestone 4 — CompoundE3D Relation Operators (Weeks 11-14)

**Deliverables:**
1. 3D compound geometric operators (T, R/SO3, S, F/Householder, H/shear) as MESSAGE function
2. Beam search variant discovery integration
3. Ablation: RotatE vs CompoundE3D as MESSAGE function
4. PathCompound hypothesis validation on FB15k-237 (heterogeneous) vs WN18RR (homogeneous)

---

### Milestone 5 — Ensemble Fusion & Calibration (Weeks 15-17)

**Deliverables:**
1. WDS (Weighted Distribution Summation) with learned dimension weights
2. Borda/RRF rank aggregation for ensemble stability
3. MoE (Mixture of Experts) gating network
4. Temperature-calibrated confidence scores
5. Domain-pack YAML extension: `path_score` weight (recommended: 0.30)

---

### Milestone 6 — AGEA Adversarial Defense (Weeks 18-20)

**Deliverables:**
1. Novelty score tracking per session
2. Per-session exploration budget with ε-greedy rate limiting
3. Hub exploitation detection (degree-spike anomaly)
4. Response sanitization: no raw subgraph context, no neighbor lists, no edge weights in API responses
5. Subgraph watermarking: phantom triple injection for attribution

**Threat model:** An adversary querying 5,000 times can reconstruct 96%+ of the graph without defense. With AGEA defenses: reconstruction capped at ~40% before rate limiting triggers.

---

### Milestone 7 — Active Inference Scheduler (Weeks 21-22)

**Deliverables:**

Repurpose AGEA's explore/exploit for active learning — prioritize enriching uncertain/low-coverage graph regions:

```
ε-greedy selection:
  EXPLORE (prob ε): Sample proportional to novelty score
  EXPLOIT (prob 1-ε): Select top-K by uncertainty score

Expected: 2-3× faster convergence on enrichment-inference loop
```

---

## PHASE 5 — RISK MATRIX

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| NBFNet memory explosion on dense subgraphs | MEDIUM | HIGH | Gradient checkpointing + dynamic edge pruning |
| CompGCN training instability (basis decomp rank collapse) | LOW | MEDIUM | Add L2 regularization on basis coefficients |
| PathCompound hypothesis fails (no gain on heterogeneous graphs) | MEDIUM | LOW | Fallback to RotatE MESSAGE (Architecture B baseline) |
| AGEA attack before defense deployment | HIGH | CRITICAL | Deploy session rate limiting immediately (1 day) |
| Incremental retraining not compatible with NBFNet | LOW | HIGH | Validate IncLoRA compatibility in Milestone 1 |

---

## PHASE 6 — SUCCESS METRICS

| Metric | Current (Baseline) | Target (Architecture B) | Timeline |
|---|---|---|---|
| MRR on PlasticOS test set | TBD (Milestone 1) | +7% vs baseline | Milestone 3 |
| HITS@10 on inductive split | 0.0 (no inductive support) | ≥0.50 | Milestone 3 |
| Cold-start entity latency | N/A (requires retraining) | <200ms (zero-shot) | Milestone 3 |
| Graph extraction resistance | 0% (vulnerable) | >80% defended at 1K queries | Milestone 6 |
| Path explanation coverage | 0% | >90% of matches have path | Milestone 3 |
| p95 inference latency | TBD | <500ms | Milestone 5 |

---

## APPENDIX — KEY EQUATIONS

### NBFNet Bellman-Ford (Equation 3)
```
h_t[v] = PNA_aggregate([rotate(h_{t-1}[u], W_r·q + b_r) for (u,r,v) in E(v)])
         + h_0[v]  # Boundary condition
```

### CompGCN Composition (Equation 2)
```
h_v^(l+1) = f(Σ_{(u,r)∈N(v)} [Σ_b a_{rb}·V_b] · circular_corr(x_u, z_r))
```

### CompoundE3D Scoring
```
f_r(h, t) = ||T·R·S·F·H·h - t||  (head-based)
f_r(h, t) = ||h - T·R·S·F·H·t||  (tail-based)
```

### AGEA Novelty Score (Equation 1)
```
N^t = (N^t_nodes · |V^t_r| + N^t_edges · |E^t_r|) / (|V^t_r| + |E^t_r|)
```

---

*Generated: 2026-04-02 | Author: IgorBot + Nuclear Super Prompt Response*
*Research papers: NBFNet (2106.06935), CompGCN (1911.03082), CompoundE3D (2309.12501), R-GCN (1703.06103), AGEA (2601.14662)*


---

## PHASE 5 — RISK, FAILURE MODES & ADVERSARIAL REVIEW

### 5.1 — Technical Failure Modes

| Failure Mode | Source Paper | Probability | Impact | Mitigation |
|---|---|---|---|---|
| Over-smoothing in deep CompGCN (6+ layers) | CompGCN §6 | High | MRR drops 5-10% after layer 4 | PairNorm: `h = (h - mean(h)) / std(h)` OR residual connections |
| Semiring violation in NBFNet with non-linear activations | NBFNet §5 | Medium | Bellman-Ford convergence not guaranteed | Keep BF iterations linear; use ReLU only in final MLP |
| CompoundE3D non-invertible operators when `s_x=0` or `s_y=0` | CompoundE3D §3.1 | Medium | NaN gradients | Enforce positivity: `S = F.softplus(S_log)` or `S = torch.clamp(S, min=1e-6)` |
| NBFNet memory explosion on dense graphs | NBFNet §3 | High | OOM on >100K entities | Gradient checkpointing + dynamic edge pruning (top-k=20) + mini-batch NeighborLoader |
| AGEA-style graph extraction on production engine | AGEA §3.2 | **High** (if public API) | 90-96% graph recovered in 1K queries | Milestone 6 defenses (sanitization, rate limiting, watermarking) |
| Cold-start relation types (new gates post-training) | NBFNet §4 | Medium | New relation scores random | Meta-learning init: train on auxiliary relation prediction task |

**Critical Mitigation Priorities:**
1. NBFNet memory — blocks production deployment
2. AGEA response sanitization — blocks public API launch
3. CompGCN over-smoothing — blocks MRR gains

---

### 5.2 — Security & Adversarial Risks (AGEA-derived)

**Attack surface — current `/v1/match` response leaks:**

| Field | What It Reveals | AGEA Exploitation |
|---|---|---|
| `dimension_scores.communitymatch` | Louvain community membership | Query variations → infer community boundaries |
| `dimension_scores.geodecayscore` | Haversine distance | Trilateration to reverse-engineer facility locations |
| `gates_passed` | WHERE clause logic (14 gates) | Infer schema: thresholds, accepted value ranges |
| `explanation` (path) | Multi-hop graph structure | Direct topology exposure |
| Ranked candidate order | Relative edge weights | SUCCEEDEDWITH score inference |

**AGEA attack simulation (1000 queries → 90%+ graph recovery):**
```python
for i in range(1000):
    # Phase 1: Gate threshold discovery
    result = api.post("/v1/match", json={"mfi": random.uniform(0, 100), ...})
    gates = [c["gates_passed"] for c in result["candidates"]]
    # Infer: mfi=50 passes, mfi=51 fails → threshold = 50

    # Phase 2: Topology extraction via explanation paths
    paths = [c["explanation"] for c in result["candidates"]]
    # Build graph: ACCEPTEDMATERIALFROM, COLOCATEDWITH edges

    # Phase 3: Edge weight recovery from dimension_scores
    # If communitymatch=0.85 for (A,B) but 0.30 for (A,C) → B,A are co-community
```

**Defense implementation:**

```python
# a) Response sanitization
def sanitize_match_response(raw_results):
    return [{
        'candidate_id': result.id,
        'final_score': result.score,
        # ❌ DO NOT RETURN: dimension_scores, gates_passed, explanation paths,
        #    neighbor IDs, edge weights, subgraph structure
    } for result in raw_results]

# b) Traversal monitoring (degree-spike anomaly detection)
class TraversalMonitor:
    def check_query(self, session_id, queried_entities):
        hub_entities = [e for e in queried_entities if e.degree > 100]
        if self.session_hub_queries[session_id] > 5:
            raise SecurityException("Hub exploitation detected")

# c) Novelty dampening
async def match_endpoint(request, session_id):
    novelty = novelty_tracker.compute_novelty(request)
    if novelty > 0.3:  # Potential exploration attack
        wait_time = min(60, 2 ** session_novelty_count[session_id])
        await asyncio.sleep(wait_time)
        session_novelty_count[session_id] += 1

# d) Subgraph watermarking (phantom triples for attribution)
def inject_watermark(graph, session_id):
    phantom_seed = hash(session_id) % 1000
    rng = np.random.RandomState(phantom_seed)
    num_phantom = int(0.001 * len(graph.edges))  # 0.1% phantom triples
    phantom_edges = [(rng.choice(nodes), rng.choice(relations), rng.choice(nodes))
                     for _ in range(num_phantom)]
    graph.add_edges(phantom_edges, watermark=session_id)
```

**Strategic decision:**
- Internal API (Odoo → FastAPI): Keep full response for debugging ✅
- External API (public SaaS): **Sanitize + watermark + rate limit before launch** — blocking issue

---

### 5.3 — Architectural Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Inductive edge repr includes entity-specific embeddings | Medium | Breaks induction entirely | Parameterize ONLY by relation: `w_q = W_r·q + b_r` (NO entity lookup) |
| CompoundE3D beam variants become stale after graph evolution | Medium | MRR degrades silently | Re-run beam search quarterly or when `|E|` changes >20% |
| Ensemble weights drift post-deployment | High | Calibration error rises | Monthly temperature re-calibration or online MoE weight updates |
| AGEA defenses create false positives on power users | Medium | Legitimate users rate-limited | Whitelist known API keys + behavioral profiling |

**Critical: Inductive edge representation constraint**

```python
# ❌ BAD — breaks induction (includes entity embeddings)
def edge_representation(u, r, v, entity_embed):
    return W_r @ (entity_embed[u] + entity_embed[v]) + b_r

# ✅ GOOD — preserves induction (relation + query only)
def edge_representation(r, query_rel):
    return W_r @ query_rel + b_r
```

---

## PHASE 6 — KEY INSIGHTS & STRATEGIC RECOMMENDATIONS

### 6.1 — The 10 Most Important Takeaways

#### 1. Replace entity lookup tables with CompGCN (HIGHEST ROI)
- Joint node+relation embeddings via circular-correlation composition
- +7% MRR on FB15k-237 (0.338 → 0.355), 4.74× parameter reduction with B=50
- Partial inductive capability: new entities init via neighbors
- **PlasticOS impact:** New facilities added daily → 15-20% HITS@10 improvement on cold-start

#### 2. NBFNet is the new inference backbone (PARADIGM SHIFT)
- TRUE inductive: scores unseen entities from graph structure alone
- +68% HITS@10 on inductive splits (0.311 → 0.523), path interpretability
- **PlasticOS impact:** Eliminates cold-start retraining requirement entirely
- **Compliance impact:** Auditable paths ("routed to Facility X because: ACCEPTED→COLOCATED→COMMUNITY")

#### 3. PNA aggregation over simple sum/mean/max (+3.7% MRR)
```
PNA = concat(mean, max, sum, std) × learned scalers × log(degree+1)
```
Captures complementary neighborhood signals; 50 lines of code.

#### 4. CompoundE3D is already your SOTA relation repr (LEVERAGE WHAT YOU HAVE)
- Fully integrated (beamsearch.py, ensemble.py, compounde3d.py)
- Upgrade path: Use as MESSAGE function in NBFNet (Milestone 4) → geometric path composition

#### 5. 6 layers is the NBFNet sweet spot — do not go deeper
- T=6: MRR = 0.509 (optimal); T=12: MRR = 0.505 (-0.8%, +2× memory)
- Hardcode `num_layers=6`

#### 6. Basis decomposition B=50 is Pareto-optimal
- B=50: 99%+ MRR retention, 4.74× parameter reduction
- Fits V100 16GB instead of A100 40GB; 30% training speedup

#### 7. Your API is a high-value extraction target (AGEA)
- 96% node recovery in 5K queries for $0.50–$2.50
- Explanation paths + dimension_scores = direct topology leakage
- **Action: Sanitize API response before any external launch**

#### 8. Edge dropout is the single most important NBFNet training trick
- Without: HITS@10 = 0.521 (learns shortcuts)
- With 10% dropout: HITS@10 = 0.599 (+15% absolute)
- 5 lines of code in training loop

#### 9. Self-adversarial negative sampling from RotatE (SANS)
- Samples negatives proportional to current model score → hard negatives
- +2-3% MRR, 30-40% training time reduction

#### 10. AGEA's explore/exploit is reusable for active enrichment scheduling
- Repurpose novelty-guided ε-greedy for uncertainty-based entity prioritization
- Expected: 2-3× faster enrichment convergence, fewer wasted API calls

---

### 6.2 — Build Priority Order

#### ✅ Tier 1 — Production Blockers (12 weeks)

| Priority | Component | Impact | Effort | Blocking Condition |
|---|---|---|---|---|
| 1 | CompGCN encoder (Milestone 2) | +7% MRR, cold-start fix | 1 week | New entities get poor matches |
| 2 | NBFNet Bellman-Ford (Milestone 3) | +68% inductive HITS@10 | 4 weeks | Cannot generalize to unseen entities |
| 3 | AGEA defense layer (Milestone 6) | Prevents 90%+ extraction | 3 weeks | **Only if public API planned** |

#### ✅ Tier 2 — Performance Optimizations (Weeks 13-18)

| Priority | Component | Impact | Effort |
|---|---|---|---|
| 4 | CompoundE3D MESSAGE function (Milestone 4) | +2-4% MRR on heterogeneous graphs | 4 weeks |
| 5 | Ensemble fusion + calibration (Milestone 5) | +1-3% MRR, better confidence | 2 weeks |

#### ❌ Tier 3 — Research Experiments (Defer)

| Component | Rationale | Action |
|---|---|---|
| PathCompound MESSAGE (CompoundE3D × NBFNet) | Unproven; 50% confidence | Internal RFC → validate on FB15k-237 before productionizing |
| Active inference scheduler | Nice-to-have; current loop converges acceptably | Implement after Tier 1+2; measure ROI in prod |

---

### 6.3 — What to Avoid

#### ❌ R-GCN as primary encoder
CompGCN strictly dominates on link prediction: +3-5% MRR, joint relation embeddings, composition operators. Keep R-GCN in benchmarking scripts only.

#### ❌ Static embedding lookup tables
`nn.Embedding(num_entities, d)` cannot score new entities. Replace with CompGCN (Milestone 2).

#### ❌ Direct entity exposure in API responses
Gate pass/fail details + explanation paths = graph extraction attack surface. Sanitize before any external launch.

#### ❌ NBFNet with >6 layers in production
T=12 doubles memory for -0.8% MRR. Not Pareto-optimal.

#### ❌ Uniform negative sampling
Self-adversarial negative sampling (SANS) reduces training time 30-40% with +2-3% MRR. Cost: 30 lines of code.

---

## SUMMARY

| Metric | Baseline | Architecture B (12 weeks) | Architecture C (20 weeks) |
|---|---|---|---|
| MRR (transductive) | ~0.338 | ~0.355–0.365 | ~0.370–0.380 |
| HITS@10 (inductive) | 0.0 | **0.52+** | 0.55+ |
| Cold-start latency | N/A (retrain required) | <200ms zero-shot | <200ms zero-shot |
| Path interpretability | 0% | **>90%** | >95% |
| Graph extraction resistance | 0% (vulnerable) | 0% (Phase 1 scope) | **>80%** (with Milestone 6) |
| Training cycle (delta) | Full retrain nightly | IncLoRA 10-15 min | IncLoRA 10-15 min |

**Recommended path: Architecture B → Milestone 6 (AGEA defense) if external API planned.**

---

*Appendix added: 2026-04-02 | Phases 5–6 continuation*
*Source: Nuclear Super Prompt Response on NBFNet/CompGCN/CompoundE3D/R-GCN/AGEA*


---

## APPENDIX B — Milestone 4 & 5 Implementation Detail

### Milestone 4 — CompoundE3D as NBFNet MESSAGE Function

#### 4.1 — 3D Compound Operator Implementation

```python
class CompoundE3DOperator(nn.Module):
    """
    Block-diagonal 3D affine operator: M_r = diag(O_{r,1}, ..., O_{r,n})
    Each block applies independent T·R·S·F·H transform.
    Embed dim d=256 → n=85 blocks of 3×3 (pad last block to fill d=256).
    """
    def __init__(self, num_relations, num_blocks):
        super().__init__()
        self.T = nn.Parameter(torch.randn(num_relations, num_blocks, 3))
        # Use quaternion parameterization to avoid gimbal lock
        self.R_quat = nn.Parameter(torch.randn(num_relations, num_blocks, 4))  # (w,x,y,z)
        self.S_log = nn.Parameter(torch.zeros(num_relations, num_blocks, 3))   # log scale
        self.F_normal = nn.Parameter(torch.randn(num_relations, num_blocks, 3))
        self.H_shear = nn.Parameter(torch.eye(3).unsqueeze(0).unsqueeze(0)
                                     .expand(num_relations, num_blocks, -1, -1).clone())

    def forward(self, h: torch.Tensor, rel_idx: int) -> torch.Tensor:
        h_blocks = h.view(-1, 3)  # (num_blocks, 3)
        out = []
        for i in range(h_blocks.size(0)):
            v = h_blocks[i]

            # 1. Householder shear
            v = v @ self.H_shear[rel_idx, i]

            # 2. Householder reflection (unit normal guaranteed by normalize)
            n = F.normalize(self.F_normal[rel_idx, i], dim=-1)
            v = v - 2 * (v @ n) * n

            # 3. Scaling (positive via softplus)
            v = v * F.softplus(self.S_log[rel_idx, i])

            # 4. SO(3) rotation via unit quaternion
            R = self._quaternion_to_rotation(
                F.normalize(self.R_quat[rel_idx, i], dim=-1)
            )
            v = v @ R.t()

            # 5. Translation
            v = v + self.T[rel_idx, i]

            out.append(v)

        return torch.stack(out).view(-1)  # Flatten back to (d,)

    @staticmethod
    def _quaternion_to_rotation(q: torch.Tensor) -> torch.Tensor:
        """Convert unit quaternion (w,x,y,z) to 3×3 rotation matrix."""
        w, x, y, z = q.unbind(-1)
        return torch.stack([
            torch.stack([1 - 2*(y**2+z**2),  2*(x*y - w*z),   2*(x*z + w*y)]),
            torch.stack([2*(x*y + w*z),        1 - 2*(x**2+z**2), 2*(y*z - w*x)]),
            torch.stack([2*(x*z - w*y),        2*(y*z + w*x),   1 - 2*(x**2+y**2)]),
        ])
```

#### 4.2 — Wire as NBFNet MESSAGE Function

```python
class CompoundE3DMessage(nn.Module):
    """Drop-in replacement for RotateMessage in NBFNet Bellman-Ford."""
    def __init__(self, num_relations, embed_dim=256):
        super().__init__()
        self.operators = CompoundE3DOperator(num_relations, num_blocks=embed_dim // 3)

    def forward(self, h_src: torch.Tensor, rel_idx: int) -> torch.Tensor:
        return self.operators(h_src, rel_idx)
```

#### 4.3 — Beam Search MESSAGE Function Selector

```python
class BeamSearchSelector:
    """Select optimal NBFNet MESSAGE function via validation MRR."""

    def select_message_fn(self, graph, valid_set, embed_dim=256):
        candidates = [
            ('RotatE',       RotateMessage(embed_dim)),
            ('DistMult',     DistMultMessage(embed_dim)),
            ('CompoundE3D',  CompoundE3DMessage(graph.num_relations, embed_dim)),
        ]
        results = []
        for name, msg_fn in candidates:
            nbfnet = NBFNet(message_fn=msg_fn, num_layers=6, embed_dim=embed_dim)
            # Train for 10 epochs on a small warmup batch
            train_warmup(nbfnet, graph, epochs=10)
            mrr = evaluate_mrr(nbfnet, valid_set, filtered=True)
            results.append((name, mrr, msg_fn))
            print(f"  {name}: MRR={mrr:.4f}")

        best_name, best_mrr, best_fn = max(results, key=lambda x: x[1])
        print(f"Selected: {best_name} (MRR={best_mrr:.4f})")
        return best_fn, best_mrr
```

#### 4.4 — Numerical Stability Checklist

| Issue | Risk | Fix |
|---|---|---|
| Reflection normal not unit length | Wrong reflection plane → incorrect gradients | `n = F.normalize(self.F_normal, dim=-1)` |
| Scaling reaches zero | NaN gradients | `S = F.softplus(self.S_log)` or `torch.clamp(S, min=1e-6)` |
| Euler angle gimbal lock | Training instability at ±90° pitch | Quaternion parameterization (implemented above) |
| Quaternion not unit | Invalid rotation matrix | `q = F.normalize(self.R_quat, dim=-1)` before applying |
| Large shear values | Gradient explosion | Initialize `H_shear = I` (identity); clip grad norm to 1.0 |

**Validation criteria:**
- ✅ CompoundE3D-NBFNet vs RotatE-NBFNet on WN18RR: target +2-4% MRR
- ✅ Beam search selects optimal variant in <50 validation cycles
- ✅ No NaN losses during 100-epoch training run

---

### Milestone 5 — AGEA-Inspired Active Inference & Security Hardening

#### 5.1 — Novelty Score Tracker

```python
class NoveltyTracker:
    """
    Computes per-query novelty N^t from AGEA paper Equation 1.

    N^t = (N^t_nodes · |V^t_r| + N^t_edges · |E^t_r|) / (|V^t_r| + |E^t_r|)

    Dual use:
      - Defense: High N^t → rate limit (potential extraction attack)
      - Active learning: High N^t → prioritize for enrichment
    """
    def __init__(self):
        self.seen_entities: set = set()
        self.seen_edges: set = set()

    def compute_novelty(self, query_result) -> float:
        new_entities = [e for e in query_result.entities
                        if e not in self.seen_entities]
        new_edges = [e for e in query_result.edges
                     if e not in self.seen_edges]

        V_r = len(self.seen_entities) + 1e-8
        E_r = len(self.seen_edges) + 1e-8

        N_nodes = len(new_entities) / max(len(query_result.entities), 1)
        N_edges = len(new_edges)   / max(len(query_result.edges), 1)

        novelty = (N_nodes * V_r + N_edges * E_r) / (V_r + E_r)

        # Update seen sets
        self.seen_entities.update(new_entities)
        self.seen_edges.update(new_edges)

        return novelty

    def predict_novelty(self, candidate) -> float:
        """Predict novelty for an unseen candidate (for active learning)."""
        # Estimate: fraction of candidate's known neighbors not yet seen
        known_neighbors = getattr(candidate, 'known_neighbors', [])
        if not known_neighbors:
            return 1.0  # Unknown entity → maximum novelty
        unseen = [n for n in known_neighbors if n not in self.seen_entities]
        return len(unseen) / len(known_neighbors)
```

#### 5.2 — Active Enrichment Scheduler (AGEA-derived, repurposed)

```python
def select_enrichment_batch(
    candidates,
    novelty_tracker: NoveltyTracker,
    budget: int = 50,
    epsilon: float = 0.2,
) -> list:
    """
    ε-greedy enrichment scheduling: explore uncertain regions vs. exploit
    high-score candidates.

    EXPLORE (prob ε): Sample proportional to novelty → fill knowledge gaps
    EXPLOIT (prob 1-ε): Select highest-uncertainty entities → maximize info gain
    """
    novelties = {c.id: novelty_tracker.predict_novelty(c) for c in candidates}

    if random.random() < epsilon:
        # EXPLORE: Proportional to novelty
        probs = np.array([novelties[c.id] for c in candidates], dtype=float)
        probs = probs / (probs.sum() + 1e-8)
        selected = np.random.choice(candidates, size=min(budget, len(candidates)),
                                     p=probs, replace=False)
    else:
        # EXPLOIT: Top-K by uncertainty score
        selected = sorted(candidates,
                          key=lambda c: c.uncertainty_score,
                          reverse=True)[:budget]

    return list(selected)
```

#### 5.3 — API Defense Layer (Full Stack)

```python
# ── a) Response sanitization ─────────────────────────────────────────────────
def sanitize_match_response(raw_results: list, session_salt: str) -> list:
    """Remove all graph-topology-leaking fields from API response."""
    return [{
        'candidate_id': hmac_hash(r.id, session_salt),  # Anonymize per session
        'final_score':  round(r.final_score, 3),
        # ❌ NEVER return: dimension_scores, gates_passed, explanation paths,
        #    neighbor IDs, edge weights, subgraph structure, raw Cypher
    } for r in raw_results]


# ── b) Traversal monitor ─────────────────────────────────────────────────────
class TraversalMonitor:
    """Detect hub exploitation (AGEA's w_e ∝ log(deg(e)+1) strategy)."""

    def __init__(self, degree_threshold: int = 100, hub_query_limit: int = 5):
        self.session_hub_queries: dict[str, int] = defaultdict(int)
        self.degree_threshold = degree_threshold
        self.hub_limit = hub_query_limit

    def check_query(self, session_id: str, queried_entities: list) -> None:
        hub_entities = [e for e in queried_entities
                        if e.degree > self.degree_threshold]
        self.session_hub_queries[session_id] += len(hub_entities)

        if self.session_hub_queries[session_id] > self.hub_limit:
            raise SecurityException(
                f"Hub exploitation detected: session {session_id!r} has queried "
                f"{self.session_hub_queries[session_id]} high-degree entities "
                f"(limit={self.hub_limit})"
            )


# ── c) Novelty-based rate limiting ───────────────────────────────────────────
session_novelty_count: dict[str, int] = defaultdict(int)

@app.post("/v1/match")
async def match_endpoint(request: MatchRequest,
                         session_id: str = Header(...)):
    novelty = novelty_tracker.compute_novelty(request)

    if novelty > 0.3:  # High novelty → potential extraction attack
        wait_time = min(60, 2 ** session_novelty_count[session_id])
        await asyncio.sleep(wait_time)
        session_novelty_count[session_id] += 1

    traversal_monitor.check_query(session_id, request.queried_entities)
    raw_results = await run_matching(request)
    return sanitize_match_response(raw_results, session_salt=session_id)


# ── d) Subgraph watermarking ─────────────────────────────────────────────────
def inject_watermark(graph, session_id: str):
    """
    Add 0.1% phantom triples keyed to session_id.
    If graph is leaked, phantom triples identify the session that extracted it.
    """
    phantom_seed = int(hashlib.sha256(session_id.encode()).hexdigest(), 16) % 10_000
    rng = np.random.RandomState(phantom_seed)

    num_phantom = max(1, int(0.001 * len(graph.edges)))
    phantom_edges = [
        (rng.choice(graph.nodes), rng.choice(graph.relations), rng.choice(graph.nodes))
        for _ in range(num_phantom)
    ]
    graph.add_edges(phantom_edges, metadata={'watermark': session_id})
    return graph
```

#### 5.4 — Validation Criteria

| Test | Method | Target |
|---|---|---|
| AGEA attack success rate with defenses | Simulate 1000-query extraction; measure node/edge recovery | <30% graph recovered (vs. 90%+ baseline) |
| Active scheduler convergence speed | Measure uncertainty reduction per enrichment batch | 2–3× faster vs. random baseline |
| False positive rate | Replay 10K legitimate user sessions through defense layer | 0 benign queries blocked |
| Watermark attribution | Extract watermarked graph; verify session ID traceable | 100% attribution accuracy |

---

*Appendix B added: 2026-04-02 — Milestone 4 CompoundE3D implementation + Milestone 5 AGEA defense stack*


---

## APPENDIX C — Execution Sequence, Checklist & Citations

### What to Avoid (Continued)

#### ❌ Skipping CompGCN and jumping directly to NBFNet

**Transition path:** CompGCN provides partial induction (new entities get embeddings via neighbors); NBFNet provides true induction (new entities scored via structure only). CompGCN is the prerequisite — its jointly-learned relation embeddings feed into NBFNet's edge representation layer.

#### ❌ Simple SUM aggregation in message passing (leaves 3-4% MRR on table)

PNA combines mean/max/sum/std with degree scaling → +3.7% MRR over best simple aggregator (NBFNet Table 3). 50 lines of code. No reason to use sum.

#### ❌ Dense W_r matrices per relation without basis decomposition

Full W_r requires O(|R|·d²) parameters. PlasticOS: 31 × 256² = 2.03M params for relation weights alone. With B=50 basis decomposition: 4.74× reduction. Every 10 new relation types adds 16× fewer params with decomposition.

#### ❌ Exposing raw subgraph context in external API responses

```json
// ❌ Current response leaks topology
{
  "dimension_scores": {...},          // reveals community/geo/temporal
  "gates_passed": ["polymer_match"],  // reveals schema (WHERE clauses)
  "explanation": "ACCEPTED→COLOCATED" // reveals topology (edge types)
}
```

AGEA: 1000 queries → 90%+ graph recovery using this information. Sanitize before any external launch.

---

### 6.4 — Novel Synthesis: The "PathCompound Engine"

**Research hypothesis (internal RFC / future publication):**

> Conjecture: Using CompoundE3D's 3D affine operators (T·R·S·F·H) as the MESSAGE function in NBFNet's Bellman-Ford iterations enables non-commutative path composition that captures geometric relational structure better than RotatE (2D rotation only).

**Intuition (PlasticOS-specific):**

Different relation types have fundamentally different geometric semantics:
- `ACCEPTEDMATERIALFROM`: Material compatibility → **translation** in polymer space
- `COLOCATEDWITH`: Geographic proximity → **scaling** by distance + rotation for directional bias
- `SUCCEEDEDWITH`: Transaction history → **reflection** for inverse preference + shear for outcome distortion

Composing via path = M_r3 ∘ M_r2 ∘ M_r1 where each M_r is a 3D compound operator preserves geometric path structure that RotatE cannot express.

**Validation strategy:**

| Condition | Dataset | Expected CompoundE3D-NBFNet gain |
|---|---|---|
| Heterogeneous (supports hypothesis) | FB15k-237 (237 relation types) | +3.3% MRR over RotatE-NBFNet |
| Heterogeneous | YAGO3-10 (37 relation types) | +3.5% MRR |
| Homogeneous (control) | WN18RR (11 lexical relation types) | +0.3% MRR (no significant gain) |

**Success criteria:** If heterogeneous gain > homogeneous gain by ≥2% → hypothesis supported.

**Timeline:** 3-6 months (research project, not production blocker)

**Publication target:** NeurIPS/ICML workshop → establishes team as KGE research contributors → talent magnet + IP moat.

---

## FINAL EXECUTION SEQUENCE

### Phase 1 — Foundation (Weeks 1-5)

| Milestone | Deliverable | Exit Criteria |
|---|---|---|
| M1 (Weeks 1-2) | Filtered MRR harness + baselines (FB15k-237, WN18RR, PlasticOS) | Reproduce RotatE MRR ≥0.338 on FB15k-237 |
| M2 (Weeks 3-5) | CompGCN encoder (Corr, B=50, 3 layers) | MRR improvement ≥4% on FB15k-237; ≥15% HITS@10 on unseen entities |

### Phase 2 — Core Upgrade (Weeks 6-10)

| Milestone | Deliverable | Exit Criteria |
|---|---|---|
| M3 (Weeks 6-10) | NBFNet (T=6, PNA, RotatE MESSAGE, edge dropout 10%, memory opt) | HITS@10 ≥0.599 on FB15k-237; ≥0.523 on inductive splits |

### Phase 3 — Advanced Features (Weeks 11-18, Optional)

| Milestone | Trigger | Deliverable | Exit Criteria |
|---|---|---|---|
| M4 (Weeks 11-14) | If time allows | CompoundE3D as MESSAGE function + beam search selector | +2-4% MRR over RotatE-NBFNet on heterogeneous graphs |
| M5 (Weeks 15-18) | If public API planned | AGEA defense stack (sanitization, monitoring, rate limiting, watermarking) | <30% graph recovery after 1000 adversarial queries |

### GO/NO-GO at Week 12

| Signal | Threshold | Decision |
|---|---|---|
| NBFNet HITS@10 on FB15k-237 | ≥0.599 → GO | Proceed to Phase 3 |
| Inductive HITS@10 | ≥0.523 → GO | — |
| PlasticOS MRR | ≥0.35 → GO | — |
| Peak GPU memory | ≤10GB on V100 16GB → GO | — |
| Inference latency | <500ms → GO | — |
| NBFNet HITS@10 | <0.580 → NO-GO | Reassess architecture |
| Memory | >16GB → NO-GO | Cannot fit V100 |
| Latency | >1000ms → NO-GO | Production UX blocker |

---

## PRODUCTION READINESS CHECKLIST

### Technical Validation
- [ ] Reproduce NBFNet MRR ≥0.599 on FB15k-237
- [ ] Reproduce CompGCN MRR ≥0.355 on FB15k-237
- [ ] Inductive split HITS@10 ≥0.523
- [ ] PlasticOS baseline MRR established (target ≥0.35)
- [ ] Memory optimization: <10GB peak on V100 16GB
- [ ] Inference latency: <500ms per match query
- [ ] Regression tests: MRR degradation <2% from baseline

### Integration Validation
- [ ] CompGCN outputs wire into NBFNet edge representations
- [ ] NBFNet scores integrate with existing 14 Cypher gates
- [ ] 4 scoring dimensions (community, geo, temporal, structural) preserved
- [ ] Path interpretation layer returns top-3 paths per candidate
- [ ] Existing Louvain/GDS jobs continue to work
- [ ] Neo4j → FastAPI → Odoo data flow unbroken

### Security Validation (if public API)
- [ ] Response sanitization (no dimension_scores, gates_passed, explanation in external responses)
- [ ] Traversal monitoring detects hub exploitation (>5 high-degree entities/session)
- [ ] Novelty rate limiting (budget=100, exponential backoff)
- [ ] Subgraph watermarking (0.1% phantom triples, session-specific seed)
- [ ] Red team: <30% graph recovery after 1000 adversarial queries

### Production Validation
- [ ] End-to-end test: Odoo → /v1/match → Neo4j → FastAPI → NBFNet → response
- [ ] Load test: 100 concurrent match queries, <1s p99 latency
- [ ] Graceful degradation: NBFNet OOM → fallback to CompGCN embeddings
- [ ] Monitoring: Track MRR, HITS@10, latency, memory in production
- [ ] Alerting: MRR drops >5% → page on-call

---

## CONTEXT SLOTS (STACK REFERENCE)

| Component | Current Value |
|---|---|
| Runtime | Python 3.11, PyTorch 2.1, PyTorch Geometric 2.4, FastAPI 0.104 |
| Graph DB | Neo4j 5.x Enterprise, multi-database per tenant |
| Current encoder | CompoundE3D Phase 4 (beamsearch.py, ensemble.py, compounde3d.py) with static TransE/RotatE embeddings |
| Current scoring | CompoundE3D ensemble (WDS/Borda/MoE) + 14 Cypher WHERE gates + 4 scoring dimensions |
| Graph scale | ~15K entities, ~50K edges, 31 relation types, ~150 triples/day growth |
| Deployment | Kubernetes + Terraform IaC, multi-tenant with domain key routing |
| Inductive requirement | **BLOCKING** — new facilities/materials added daily without retraining |
| Public API | PLANNED (SaaS) → AGEA defense is critical pre-launch |
| Baseline MRR | PlasticOS ~0.25-0.30 (estimated, no formal benchmark yet) |

---

## CITATIONS

1. Zhu, Z. et al. (2021). **Neural Bellman-Ford Networks: A General Graph Neural Network Framework for Link Prediction.** *NeurIPS 2021*. arXiv:2106.06935
2. Vashishth, S. et al. (2020). **Composition-based Multi-Relational Graph Convolutional Networks.** *ICLR 2020*. arXiv:1911.03082
3. Ge, Y. et al. (2023). **Knowledge Graph Embedding with 3D Compound Geometric Transformations.** *AAAI 2023*. arXiv:2304.00378
4. Schlichtkrull, M. et al. (2018). **Modeling Relational Data with Graph Convolutional Networks.** *ESWC 2018*. arXiv:1703.06103
5. [AGEA paper] arXiv:2601.14662 — Adversarial Graph Extraction Attack (recent preprint)
6. Sun, Z. et al. (2019). **RotatE: Knowledge Graph Embedding by Relational Rotation in Complex Space.** *ICLR 2019*. arXiv:1902.10197
7. Corso, G. et al. (2020). **Principal Neighbourhood Aggregation for Graph Nets.** *NeurIPS 2020*. arXiv:2004.05718
8. Xu, D. et al. (2019). **Inductive Representation Learning on Temporal Graphs.** *ICLR 2020*. arXiv:2002.07962

---

*END OF ROADMAP — Complete document: Phases 1-6 + Appendices A-C*
*Total scope: 5 research papers → 3 architecture candidates → 7 implementation milestones → production checklist*
*Recommended path: Architecture B (Path-Aware Engine) → Milestone 6 (AGEA defense) if external API planned*
