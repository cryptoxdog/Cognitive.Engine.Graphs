# Inference Engine Enhancement — KG Research Roadmap

**Stack context:** CompoundE3D Phase 4 (integrated) · Neo4j 5.x Enterprise · PyTorch Geometric 2.4 · FastAPI 0.104 · ~15K entities, 50K edges, 31 relation types, ~150 triples/day growth · Multi-tenant Kubernetes  
**Research papers:** NBFNet (2106.06935) · CompGCN (1911.03082) · CompoundE3D (2309.12501) · R-GCN (1703.06103) · AGEA (2601.14662)  
**Recommended architecture:** B — Path-Aware Engine

---

## Executive Summary

The current engine is **embedding-based transductive** (CompoundE3D + static RotatE/TransE lookup). The five papers provide a clear upgrade path to **path-aware inductive with ensemble fusion and adversarial hardening**:

1. **CompGCN** (Weeks 3-5): Joint node+relation embeddings. +7% MRR, cold-start fix via neighbor initialization.
2. **NBFNet** (Weeks 6-10): True inductive generalization. +68% HITS@10 on unseen entities, path interpretability.
3. **CompoundE3D** (already integrated): Upgrade to NBFNet MESSAGE function for +2-4% MRR on heterogeneous graphs.
4. **AGEA** (Weeks 18-20): Adversarial defense layer — prevents 90%+ graph extraction if public API is planned.
5. **R-GCN**: Subsumed by CompGCN. Benchmarks only.

---

## Current State vs. Target

```
Current:
  Graph Input → static RotatE/TransE lookup → CompoundE3D ensemble → 14 Cypher gates + 4 dims
  Limitation: Cannot score new entities without full retraining

Target (Architecture B):
  Graph Input → CompGCN encoder → NBFNet Bellman-Ford (T=6) → path score (5th dim) → 14 Cypher gates + 4 dims
  Gain: Zero-shot scoring of new entities; auditable matching paths
```

---

## Capability Gap Matrix

| Paper | Inductive | Relation Expr. | Path Interp. | Scalability | Adversarial | Production Blocker? |
|---|---|---|---|---|---|---|
| NBFNet | ✅ TRUE | ⚠️ MED | ✅ HIGH | ⚠️ O(E·d) | ❌ | **YES** — no inductive |
| CompGCN | ✅ HIGH | ✅ HIGH | ❌ | ✅ basis decomp | ❌ | **YES** — under-parameterized |
| CompoundE3D | ❌ | ✅ SOTA | ❌ | ✅ block-diag | ❌ | Already integrated |
| R-GCN | ⚠️ | ⚠️ | ❌ | ✅ | ❌ | Subsumed by CompGCN |
| AGEA | N/A | N/A | N/A | N/A | ✅ CRITICAL | **YES** if public API |

---

## Paper Summaries

### NBFNet — Generalized Bellman-Ford for Link Prediction

**Core:** Formulates link prediction as message-passing over graph paths, parameterized by learned MESSAGE/AGGREGATE/INDICATOR functions.

```
h^(t)(v) = AGGREGATE({MESSAGE(h^(t-1)(u), w_q(u,r,v)) : (u,r,v) ∈ E(v)} ∪ {h^0(v)})
w_q(u,r,v) = W_r · q + b_r   # Edge repr depends ONLY on relation type + query — enables induction
```

**Key results:** FB15k-237 HITS@10 = 0.599; inductive splits HITS@10 = 0.523 (vs 0.311 for RotatE, +68%)  
**Critical hyperparameter:** T=6 layers optimal (T=12 → +2× memory for -0.8% MRR)  
**Single most important trick:** 10% edge dropout during training — forces multi-hop path learning  
Without dropout: HITS@10 = 0.521. With dropout: HITS@10 = 0.599 (+15% absolute)

### CompGCN — Joint Node+Relation Embedding

**Core:** GCN with relation-specific composition operators + basis decomposition for parameter efficiency.

```
h_v^(l+1) = f(Σ_{(u,r)∈N(v)} W_r^(l) · φ(x_u, z_r))
W_r = Σ_b a_{rb} · V_b    # Basis decomposition: B=50 → 4.74× fewer params, <1% MRR loss
```

Composition operators (best → worst): **Corr** > Mult > Sub  
**Key results:** FB15k-237 MRR = 0.355 (+7% over RotatE); WN18RR MRR = 0.479  
**Critical implementation:** Relation update via **reverse message passing** (§3.2) — omitting this breaks training

### CompoundE3D — 3D Geometric Relation Operators

**Core:** Block-diagonal affine operators T·R·S·F·H in 3D, discovered via beam search.

```
M_r = diag(O_{r,1}, ..., O_{r,n})   where O = T · R · S · F · H (5 transforms)
Scoring: f_r(h,t) = ||M_r·h - t||  or  ||h - M_r·t||
```

**Integration status:** ✅ Fully integrated (beamsearch.py, ensemble.py, compounde3d.py)  
**Upgrade path:** Use as NBFNet MESSAGE function (Milestone 4) for geometric path composition

### AGEA — Adversarial Graph Extraction

**Core:** Novelty-guided ε-greedy exploration to reconstruct graph topology from API responses.

```
N^t = (N^t_nodes · |V^t_r| + N^t_edges · |E^t_r|) / (|V^t_r| + |E^t_r|)
```

**Results on LightRAG:** 90.7% nodes + 82.3% edges recovered in 1,000 queries ($0.50–$2.50)  
**Your attack surface:** `dimension_scores`, `gates_passed`, `explanation` paths → direct topology leakage  
**Dual use:** Novelty score also useful as active enrichment scheduler (see §Active Learning below)

---

## Three Architectures

### Architecture A — Surgical Upgrade (1 week)
Drop-in CompGCN encoder. Preserves all downstream logic.  
**Gain:** +5% MRR, +15-20% HITS@10 on cold-start. Does **not** solve inductive generalization.

### Architecture B — Path-Aware Engine (3-4 weeks) ⭐ RECOMMENDED

```
Graph Input
    ↓
CompGCN Encoder (3 layers, Corr, B=50)
    ↓
Edge Representation: w_q = W_r · q + b_r
    ↓
NBFNet Bellman-Ford (T=6 iterations)
  MESSAGE: RotatE composition
  AGGREGATE: PNA(mean, max, sum, std) × log(degree+1)
  Edge dropout: 10% during training
    ↓
p(v|u,q) = σ(MLP(h^T(v)))   +   path extraction: ∂p/∂path
    ↓
5-dim scoring:
  final = 0.25·kge + 0.15·community + 0.10·geo + 0.20·temporal + 0.30·path
    ↓
Existing: 14 Cypher gates (unchanged)
```

**Gains:** Inductive HITS@10: 0.311 → 0.523 (+68%); transductive: +11%; path interpretability for every match

### Architecture C — Unified Foundation (8-12 weeks)
Adds CompoundE3D as NBFNet MESSAGE function (PathCompound), ensemble calibration, and AGEA defenses. Research-grade; PathCompound is unproven hypothesis.

---

## Implementation Milestones

### M1 — Baseline Hardening (Weeks 1-2)
- Filtered MRR/HITS@N evaluation harness
- Benchmark datasets: FB15k-237, WN18RR, PlasticOS triples
- CI: GitHub Actions asserts MRR ≥ 0.338 on FB15k-237
- **Exit:** Reproduce RotatE MRR ≥ 0.338; PlasticOS baseline established

### M2 — CompGCN Encoder (Weeks 3-5)
- Circular-correlation composition (Corr operator)
- Basis decomposition B=50 (Pareto-optimal: 99%+ MRR, 4.74× fewer params)
- **Do not skip:** Relation update via reverse message passing (CompGCN §3.2)
- Replaces static `nn.Embedding` lookup tables
- **Exit:** MRR ≥ +4% on FB15k-237; B=50 achieves <5% MRR drop vs full params

### M3 — NBFNet Core (Weeks 6-10)
- Bellman-Ford iterations (T=6, hardcoded)
- INDICATOR: learned query embeddings per relation
- MESSAGE: RotatE (uses CompGCN relation embeddings as edge repr)
- AGGREGATE: PNA with 4 aggregators + degree scaling (+3.7% over sum)
- **CRITICAL:** 10% edge dropout during training
- Memory: gradient checkpointing + top-k=20 edge pruning + mini-batch NeighborLoader
- **Exit:** HITS@10 ≥ 0.599 (FB15k-237); ≥ 0.523 inductive; confirm T=6 optimal via ablation

### M4 — CompoundE3D MESSAGE Function (Weeks 11-14, optional)
- 3D block-diagonal operators (T·R·S·F·H) as drop-in MESSAGE replacement
- Quaternion parameterization for rotation (avoids gimbal lock)
- Beam search over {RotatE, DistMult, CompoundE3D} → select best by validation MRR
- Validate PathCompound hypothesis: heterogeneous gain > homogeneous gain by ≥2%
- **Numerical stability:** `S = F.softplus(S_log)`, `n = F.normalize(F_normal)`, init `H_shear = I`
- **Exit:** +2-4% MRR over RotatE-NBFNet on FB15k-237

### M5 — Ensemble Fusion & Calibration (Weeks 15-17, optional)
- WDS + Borda/RRF + MoE gating with temperature calibration
- Adds `path_score` weight to domain-pack YAML (recommended: 0.30)
- Monthly re-calibration to prevent drift

### M6 — AGEA Adversarial Defense (Weeks 18-20, **required if public API**)
- Response sanitization: remove `dimension_scores`, `gates_passed`, `explanation` from external responses
- Traversal monitor: rate-limit sessions querying >5 hub entities (degree > 100)
- Novelty rate limiting: exponential backoff when session novelty > 0.3
- Subgraph watermarking: 0.1% phantom triples per session for attribution
- **Exit:** <30% graph recovery after 1,000 adversarial queries; 0 false positives on legitimate sessions

### M7 — Active Inference Scheduler (Weeks 21-22, optional)
Repurpose AGEA's novelty-guided ε-greedy for enrichment prioritization:
```python
# EXPLORE (prob ε): sample proportional to novelty → fill knowledge gaps
# EXPLOIT (prob 1-ε): select top-K by uncertainty score → maximize info gain
# Expected: 2-3× faster enrichment convergence, fewer wasted API calls
```

---

## Key Code Patterns

### CompGCN Layer (Corr composition + basis decomp)
```python
class CompGCNLayer(nn.Module):
    def forward(self, x, rel, edge_index, edge_type, basis, coeff):
        out = torch.zeros_like(x)
        for r in range(len(rel)):
            mask = (edge_type == r)
            src, dst = edge_index[:, mask]
            composed = circular_corr(x[src], rel[r].expand(len(src), -1))  # φ(x_u, z_r)
            W_r = torch.einsum('b,boi->oi', coeff[r], basis)               # basis decomp
            out[dst] += W_r @ composed.t()
        # CRITICAL: also update relation embeddings via reverse aggregation
        return F.relu(out), updated_rel
```

### NBFNet Bellman-Ford
```python
def bellman_ford(h_prev, graph, W_r, query_rel, T=6):
    for t in range(T):
        h_next = torch.zeros_like(h_prev)
        for v in graph.nodes:
            msgs = []
            for (u, r, v_) in graph.incoming_edges(v):
                if v_ == v and random() > 0.1:          # 10% edge dropout
                    w_q = W_r[r] @ query_rel + b_r[r]   # relation-only edge repr (inductive)
                    msgs.append(rotate(h_prev[u], w_q))  # RotatE MESSAGE
            if msgs:
                h_next[v] = pna_aggregate(msgs, degree=len(msgs))
        h_prev = h_next
    return h_prev

def pna_aggregate(messages, degree):
    M = torch.stack(messages)
    aggs = torch.cat([M.mean(0), M.max(0)[0], M.sum(0), M.std(0)])  # 4 aggregators
    return mlp(aggs * learned_scalers * math.log(degree + 1))        # degree scaling
```

### CompoundE3D Operator (Milestone 4)
```python
class CompoundE3DOperator(nn.Module):
    def forward(self, h, rel_idx):
        h_blocks = h.view(-1, 3)  # d=256 → 85 blocks of 3×3
        out = []
        for i, v in enumerate(h_blocks):
            v = v @ self.H_shear[rel_idx, i]                                 # shear
            n = F.normalize(self.F_normal[rel_idx, i], dim=-1)
            v = v - 2 * (v @ n) * n                                           # reflection
            v = v * F.softplus(self.S_log[rel_idx, i])                       # scaling (positive)
            v = v @ self._quaternion_to_rotation(                              # SO(3) rotation
                F.normalize(self.R_quat[rel_idx, i], dim=-1)).t()
            v = v + self.T[rel_idx, i]                                        # translation
            out.append(v)
        return torch.stack(out).view(-1)
```

### AGEA Defense Stack
```python
# Sanitize external API response
def sanitize(results, session_salt):
    return [{'id': hmac(r.id, session_salt), 'score': round(r.score, 3)} for r in results]
    # Never return: dimension_scores, gates_passed, explanation paths, neighbor IDs

# Rate limit high-novelty sessions
async def match_endpoint(request, session_id=Header(...)):
    if novelty_tracker.compute_novelty(request) > 0.3:
        await asyncio.sleep(min(60, 2 ** novelty_count[session_id]))
        novelty_count[session_id] += 1
    traversal_monitor.check_query(session_id, request.queried_entities)
    return sanitize(await run_matching(request), session_salt=session_id)

# Watermark: 0.1% phantom triples per session for attribution
def inject_watermark(graph, session_id):
    rng = np.random.RandomState(int(sha256(session_id.encode()).hexdigest(), 16) % 10_000)
    for _ in range(max(1, len(graph.edges) // 1000)):
        graph.add_edge(rng.choice(graph.nodes), rng.choice(graph.relations),
                       rng.choice(graph.nodes), watermark=session_id)
```

### Active Enrichment Scheduler (M7)
```python
def select_enrichment_batch(candidates, novelty_tracker, budget=50, epsilon=0.2):
    novelties = {c.id: novelty_tracker.predict_novelty(c) for c in candidates}
    if random.random() < epsilon:
        probs = np.array([novelties[c.id] for c in candidates])
        probs /= probs.sum()
        return np.random.choice(candidates, size=budget, p=probs, replace=False)
    return sorted(candidates, key=lambda c: c.uncertainty_score, reverse=True)[:budget]
```

---

## Risk Matrix

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| NBFNet memory explosion | HIGH | HIGH | Gradient checkpointing + top-k=20 pruning + NeighborLoader |
| AGEA attack before defense | HIGH | CRITICAL | Deploy sanitization immediately (1 day); full stack before public launch |
| CompGCN over-smoothing (>3 layers) | HIGH | MEDIUM | PairNorm `h = (h-mean)/std` or residual connections; use 3 layers |
| Inductive edge repr includes entity embeddings | MEDIUM | HIGH | `w_q = W_r·q + b_r` ONLY — no entity-specific terms |
| PathCompound hypothesis fails | MEDIUM | LOW | Fallback to RotatE MESSAGE; Architecture B baseline unaffected |
| CompoundE3D NaN gradients (zero scaling) | MEDIUM | MEDIUM | `S = F.softplus(S_log)`; quaternion for rotation |
| IncLoRA incompatible with NBFNet | LOW | HIGH | Validate in M1 before M3 build |

**Critical inductive constraint:**
```python
# ❌ Breaks induction — entity-specific
edge_repr(u, r, v) = W_r @ (entity_embed[u] + entity_embed[v]) + b_r

# ✅ Preserves induction — relation + query only
edge_repr(r, query_rel) = W_r @ query_rel + b_r
```

---

## Success Metrics

| Metric | Baseline | Architecture B Target | Milestone |
|---|---|---|---|
| MRR (transductive) | ~0.338 | ~0.355–0.365 | M3 |
| HITS@10 (inductive) | 0.0 | ≥0.52 | M3 |
| Cold-start latency | N/A (retrain required) | <200ms zero-shot | M3 |
| Path explanation coverage | 0% | >90% of matches | M3 |
| Graph extraction resistance | 0% | >80% at 1K queries | M6 |
| p95 inference latency | TBD | <500ms | M5 |
| Training cycle (delta) | Full nightly retrain | IncLoRA 10-15 min | M3 |

---

## Build Priority

### Tier 1 — Production Blockers (Weeks 1-10)
| # | Component | Blocking Condition | Effort |
|---|---|---|---|
| 1 | CompGCN encoder | Cold-start entities get poor matches | 1 week |
| 2 | NBFNet Bellman-Ford | Cannot generalize to new entities | 4 weeks |
| 3 | AGEA defense | **Only if public API is planned** | 3 weeks |

### Tier 2 — Performance (Weeks 11-17)
| # | Component | Gain | Effort |
|---|---|---|---|
| 4 | CompoundE3D MESSAGE function | +2-4% MRR heterogeneous | 4 weeks |
| 5 | Ensemble fusion + calibration | +1-3% MRR, better confidence | 2 weeks |

### Tier 3 — Research / Defer
| Component | Rationale |
|---|---|
| PathCompound (CompoundE3D × NBFNet) | Unproven; 50% confidence. Internal RFC → validate on FB15k-237 first |
| Active inference scheduler (M7) | Nice-to-have; current enrichment loop converges acceptably |

### What to Avoid
- **R-GCN as primary encoder** — subsumed by CompGCN (+3-5% MRR deficit). Benchmarks only.
- **Static `nn.Embedding` lookup** — cannot score new entities. Replace in M2.
- **Simple sum/mean/max aggregation** — PNA is +3.7% MRR for 50 lines of code.
- **Dense W_r matrices** — basis decomp B=50 is 4.74× smaller with <1% MRR cost.
- **NBFNet with >6 layers** — T=12 doubles memory for -0.8% MRR.
- **Exposing `dimension_scores`, `gates_passed`, `explanation` in external API** — direct AGEA attack surface.
- **Skipping CompGCN → jumping to NBFNet** — CompGCN relation embeddings feed NBFNet edge repr.

---

## GO/NO-GO Gates (Week 12)

| Signal | GO | NO-GO |
|---|---|---|
| NBFNet HITS@10 on FB15k-237 | ≥0.599 | <0.580 |
| Inductive split HITS@10 | ≥0.523 | <0.450 |
| PlasticOS MRR | ≥0.35 | <0.30 |
| Peak GPU memory (V100 16GB) | ≤10GB | >16GB |
| p99 inference latency | <500ms | >1,000ms |

On NO-GO: reassess memory optimization (gradient checkpointing depth, subgraph size) before proceeding to Tier 2.

---

## Research Hypothesis: PathCompound Engine

> **Conjecture:** CompoundE3D's 3D affine operators (T·R·S·F·H) as NBFNet MESSAGE function enables non-commutative path composition — different relation semantics preserved geometrically across hops.

**PlasticOS intuition:**
- `ACCEPTEDMATERIALFROM`: translation in polymer space
- `COLOCATEDWITH`: scaling + rotation for geo proximity
- `SUCCEEDEDWITH`: reflection + shear for transaction history

M_path = M_COLOCATED ∘ M_ACCEPTED preserves structure RotatE cannot express.

**Validation:** Train on FB15k-237 + YAGO3-10 (heterogeneous) vs WN18RR (homogeneous control). If heterogeneous gain > homogeneous by ≥2% → hypothesis supported. Expected: +3.3% on FB15k-237, +0.3% on WN18RR (control).

**Target:** NeurIPS/ICML workshop paper. Timeline: 3-6 months. Not a production blocker.

---

## Production Readiness Checklist

**Technical**
- [ ] RotatE MRR ≥ 0.338 reproduced on FB15k-237
- [ ] CompGCN MRR ≥ 0.355 on FB15k-237
- [ ] NBFNet HITS@10 ≥ 0.599 (transductive) + ≥ 0.523 (inductive)
- [ ] PlasticOS baseline MRR established; target ≥ 0.35 post-M3
- [ ] Peak memory < 10GB on V100 16GB
- [ ] Inference latency < 500ms p95
- [ ] Regression suite: MRR degradation < 2% from baseline

**Integration**
- [ ] CompGCN outputs → NBFNet edge representations
- [ ] NBFNet path score wired as 5th scoring dimension (weight 0.30)
- [ ] 14 Cypher gates + 4 scoring dimensions unchanged
- [ ] Louvain/GDS jobs continue to run
- [ ] Neo4j → FastAPI → Odoo data flow unbroken

**Security (if public API)**
- [ ] External responses: no `dimension_scores`, `gates_passed`, `explanation`
- [ ] TraversalMonitor: blocks sessions with >5 hub queries
- [ ] Novelty rate limiting active (budget=100, exponential backoff)
- [ ] Watermarking: 0.1% phantom triples per session
- [ ] Red team: <30% graph recovery after 1,000 queries

**Production**
- [ ] End-to-end test: Odoo → /v1/match → Neo4j → FastAPI → NBFNet → response
- [ ] Load test: 100 concurrent queries, <1s p99
- [ ] Graceful degradation: OOM → fallback to CompGCN embeddings
- [ ] Monitoring + alerting: MRR drops >5% → page on-call

---

## Stack Reference

| Component | Value |
|---|---|
| Runtime | Python 3.11, PyTorch 2.1, PyTorch Geometric 2.4, FastAPI 0.104 |
| Graph DB | Neo4j 5.x Enterprise, multi-database per tenant |
| Current encoder | CompoundE3D Phase 4 (beamsearch.py, ensemble.py, compounde3d.py) + static embeddings |
| Current scoring | CompoundE3D ensemble (WDS/Borda/MoE) + 14 Cypher gates + 4 scoring dims |
| Graph scale | ~15K entities, ~50K edges, 31 relation types, ~150 triples/day growth |
| Deployment | Kubernetes + Terraform IaC, multi-tenant |
| #1 blocker | Inductive generalization — new entities daily, no retraining |
| Public API | PLANNED → AGEA defense required before launch |

---

## Key Equations

```
# NBFNet MESSAGE+AGGREGATE
h^(t)(v) = PNA({RotatE(h^(t-1)(u), W_r·q+b_r) : (u,r,v) ∈ E(v)}) + h^0(v)

# CompGCN composition (Corr) + basis decomp
h_v^(l+1) = f(Σ [Σ_b a_rb · V_b] · circular_corr(x_u, z_r))

# CompoundE3D scoring
f_r(h,t) = ||T·R·S·F·H·h - t||   (head)   /   ||h - T·R·S·F·H·t||   (tail)

# AGEA novelty score
N^t = (N_nodes · |V_r| + N_edges · |E_r|) / (|V_r| + |E_r|)

# PNA aggregation
PNA(M, deg) = MLP(concat(mean,max,sum,std)(M) × scalers × log(deg+1))
```

---

## Citations

1. Zhu et al. (2021). **NBFNet.** *NeurIPS 2021.* arXiv:2106.06935
2. Vashishth et al. (2020). **CompGCN.** *ICLR 2020.* arXiv:1911.03082
3. Ge et al. (2023). **CompoundE3D.** *AAAI 2023.* arXiv:2304.00378
4. Schlichtkrull et al. (2018). **R-GCN.** *ESWC 2018.* arXiv:1703.06103
5. [AGEA] arXiv:2601.14662
6. Sun et al. (2019). **RotatE.** *ICLR 2019.* arXiv:1902.10197
7. Corso et al. (2020). **PNA.** *NeurIPS 2020.* arXiv:2004.05718

---

*Last updated: 2026-04-02 · Recommended: Architecture B → M6 AGEA defense if public API planned*
