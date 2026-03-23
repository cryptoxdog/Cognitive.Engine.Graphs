# HopRAG → CEG Enhancement Program

**Version:** 1.0.0
**Date:** 2026-03-22
**Author:** Engine Team — HopRAG Integration Working Group
**Source Paper:** HopRAG: Multi-Hop Reasoning Augmented Graph Retrieval (ACL 2025)
**Target Repository:** cryptoxdog/Cognitive.Engine.Graphs (L9 Constellation)

---

## Part 1: Repo Orientation Summary

### 1.1 Architecture Overview

The Cognitive Engine Graphs (CEG) repository implements a **L9 Constellation** — a distributed runtime where independent nodes collaborate through a central orchestrator to execute graph-powered matching, scoring, and enrichment. Communication between nodes follows the **PacketEnvelope** protocol: every request is normalized into a typed packet with a trace ID, routed to a handler, and returned with structured metadata (execution time, node hops, cost, token usage).

The persistence layer is **Neo4j**, with all retrieval and mutation expressed as parameterized Cypher queries. Configuration is driven by **domain-spec YAML** files parsed into Pydantic models (`DomainSpec`), enabling multi-tenant deployment where each tenant has its own graph schema, gates, scoring dimensions, and traversal patterns.

### 1.2 Key Components Mapped

| Component | File | Responsibility |
|---|---|---|
| **Scoring Assembler** | `engine/scoring/assembler.py` | Compiles scoring dimensions → Cypher WITH clause. 11+ computation types (GEODECAY, LOGNORMALIZED, KGE, ENSEMBLECONFIDENCE, etc.). Pure linear weighted sum. |
| **Traversal Assembler** | `engine/traversal/assembler.py` | Compiles traversal steps → Cypher MATCH/OPTIONAL MATCH clauses. Single-hop patterns only. Pattern validation with injection protection. |
| **Gate Compiler** | `engine/gates/compiler.py` | 10 gate types → Cypher WHERE clause fragments. Null semantics, role exemptions, direction filtering. Composite gates support AND/OR logic. |
| **Beam Search Engine** | `engine/kge/beam_search.py` | Discovers CompoundE3D variants via beam search over 3D transformation space. Prune strategies: threshold, diversity, constraint, combined. |
| **Ensemble Controller** | `engine/kge/ensemble.py` | WDS, Borda, RRF, MoE fusion for multi-variant KGE aggregation. Confidence thresholding, audit logging. |
| **Action Handlers** | `engine/handlers.py` | 8 handlers: match, sync, admin, outcomes, resolve, health, healthcheck, enrich. The `handle_match` function is the primary scoring pipeline. |
| **Orchestrator** | `chassis/orchestrator.py` | `execute()` dispatches to action handlers via `route_packet()`. Tracks metrics: request_count, duration, node_hops, errors, tokens, cost. |
| **Parameter Resolver** | `engine/traversal/resolver.py` | Resolves derived parameters from query fields before Cypher execution. |

### 1.3 Extension Points Identified

1. **`ScoringAssembler._compile_dimension()` dispatch dict** — New `ComputationType` values can be added to the dispatch table without modifying existing entries. The HELPFULNESS and IMPORTANCE computation types slot in here directly.

2. **`TraversalAssembler.assemble_traversal()` step loop** — Currently iterates single-hop patterns. A multi-hop traverser can operate as a pre-processing enrichment step that writes visit counts to Neo4j *before* the Cypher query executes.

3. **`handle_match()` handler pipeline** — The gate → traversal → scoring pipeline is sequential. A multi-hop traversal stage can be inserted between gate compilation and scoring assembly.

4. **`register_all()` handler registry** — New action handlers (e.g., `handle_multihop_match`) can be registered alongside existing ones.

5. **Domain-spec YAML schema** — `DomainSpec` is Pydantic-based; new configuration sections (e.g., `hoprag:`) can be added without breaking existing specs.

6. **`handle_enrich()` action** — The enrich handler can write pre-computed HopRAG metrics (visit counts, edge weights) to graph nodes.

7. **KGE feature-gate pattern** — The `kge_enabled` / `settings.pareto_enabled` flag pattern provides a template for gating HopRAG features behind `hoprag_enabled`.

### 1.4 Dormant Features Noted

| Feature | Evidence | Status |
|---|---|---|
| **Pareto pre-filter** | `settings.pareto_enabled` gate in `ScoringAssembler` | Implemented but gated off in production |
| **KGE subsystem** | `kge_enabled` flag usually False | Full implementation exists (beam search, ensemble, CompoundE3D) but not active |
| **pgvector integration** | Referenced in roadmap docs | Not implemented; placeholder in Phase 2 roadmap |
| **Feedback loops** | TransactionOutcome nodes + RESULTED_IN edges | Partially wired; outcomes are written but not fed back into scoring weights |
| **Relaxed matching** | `compile_relaxed()` in GateCompiler | Implemented but no caller in `handle_match` |
| **GDS scheduler** | `_get_or_create_scheduler()` in handlers | Infrastructure exists but usage is admin-triggered only |

---

## Part 2: Detailed Concept Extraction Report

### 2.1 Query Simulation (Pseudo-Query Generation)

**Paper Reference:** §3.1 "Query Simulation"

For each passage `p_i` in the corpus:
- Generate `m` **out-coming questions** `Q+_i`: questions that originate from `p_i` but *cannot* be answered by it alone. These represent logical next-hops.
- Generate `n` **in-coming questions** `Q-_i`: questions whose answers are contained within `p_i`. These represent what the passage can satisfy.
- Each question is stored as a triplet: `r = (question_text, NER_keywords, embedding_vector)`

**CEG Relevance:** This is an indexing-phase enrichment that creates edge metadata. It maps to a new enrichment pipeline that runs after graph sync but before query-time traversal.

### 2.2 Edge Merging with Hybrid Similarity

**Paper Reference:** §3.2 "Edge Merging"

Edges are created by matching out-coming triplets from source passages to in-coming triplets of target passages:

```
SIM(r+_s,i, r-_t,j) = (Jaccard(k+_s,i, k-_t,j) + cosine(v+_s,i, v-_t,j)) / 2
```

Where:
- Jaccard operates on NER keyword sets (sparse)
- Cosine operates on embedding vectors (dense)
- The arithmetic mean provides a balanced sparse-dense fusion

Only `O(n·log(n))` edges are retained to prevent density explosion (where `n` is the number of vertices).

**CEG Relevance:** This creates the directed graph structure. Edge density control maps directly to a domain-spec parameter.

### 2.3 Retrieve-Reason-Prune Pipeline

**Paper Reference:** §3.3 "Retrieval"

Three-stage pipeline at query time:
1. **RETRIEVE:** Use NER + embedding on user query → hybrid retrieval to match top-k similar edges → initialize BFS queue with connected vertices
2. **REASON:** BFS traversal where at each vertex, an LLM selects the most helpful outgoing edge to follow. Visit counter incremented at each vertex.
3. **PRUNE:** Rank all visited vertices by Helpfulness metric `H_i = (SIM(v_i, q) + IMP(v_i, C_count)) / 2`

**CEG Relevance:** This is a new query-time pipeline mode. It does NOT replace the existing gate-score pipeline but can augment it by writing visit-count enrichments and helpfulness scores before Cypher execution.

### 2.4 BFS with LLM-Guided Neighbor Selection

**Paper Reference:** §3.3.2 "Reason"

At each vertex in the BFS queue:
- Enumerate outgoing edges (each carrying pseudo-query text)
- LLM evaluates: "Given query Q and current passage P, which neighboring edge question is most helpful for answering Q?"
- Selected neighbor is added to BFS queue
- Vertex visit count incremented

Key properties:
- BFS (not DFS) ensures breadth-first exploration of reasoning chains
- Queue management with `max_hops` parameter (optimal at n_hop=4)
- Queue length decays naturally (avg 2.60 at hop 4, 1.23 at hop 5)

**CEG Relevance:** Maps to a new `MultiHopTraverser` that operates outside Neo4j Cypher (application-level BFS) and writes results back to Neo4j for scoring.

### 2.5 Visit Counter as Importance Signal (IMP Metric)

**Paper Reference:** §3.3.3 "Prune"

```
IMP(v_i, C_count) = C_count[v_i] / sum(C_count.values())
```

Vertices visited more frequently from different reasoning paths are considered more important. This is a passage-level signal that is independent of query similarity.

**CEG Relevance:** Direct additive integration. Visit counts can be stored as transient node properties and consumed by a new `IMPORTANCE` scoring dimension.

### 2.6 Helpfulness Metric

**Paper Reference:** §3.3.3 "Prune", Equation 3

```
H_i = (SIM(v_i, q) + IMP(v_i, C_count)) / 2
```

A balanced combination of:
- **SIM:** Cosine similarity between vertex embedding and query embedding
- **IMP:** Normalized visit count from BFS traversal

The alpha=0.5 balance is the paper's default but could be tuned per domain.

**CEG Relevance:** This is a new scoring dimension type (`HELPFULNESS`) that combines two sub-signals. It fits into `ScoringAssembler._compile_dimension()` dispatch.

### 2.7 O(n·log(n)) Edge Density Control

**Paper Reference:** §3.2 "Edge Merging"

To prevent the graph from becoming too dense (which would slow BFS traversal and dilute signal):
- Sort all candidate edges by hybrid similarity score
- Keep only the top `O(n·log(n))` edges (where n = vertex count)
- Average result: ~5.87 directed edges per vertex

**CEG Relevance:** Maps to a domain-spec parameter `max_edge_density` or `edge_density_factor`. Applied during indexing phase.

### 2.8 Sparse + Dense Dual Indexing on Vertices AND Edges

**Paper Reference:** §3.1 and §3.3.1

Both vertices and edges carry dual representations:
- **Sparse:** NER-extracted keywords → used for fast keyword-based retrieval
- **Dense:** Embedding vectors → used for semantic similarity matching

At query time, the user query is also decomposed into keywords + embedding, and hybrid retrieval matches against both indexes.

**CEG Relevance:** Requires pgvector or similar vector index integration (aligned with CEG Phase 2 roadmap). The sparse index can leverage Neo4j full-text indexing.

### 2.9 Non-LLM Traversal Fallback

**Paper Reference:** §4.3 "Effect of Reasoning Model"

Even without LLM reasoning during traversal (using pure cosine similarity to select next edges), HopRAG still achieves 25.43% improvement over dense retriever baseline. This validates that the graph structure itself is valuable, independent of LLM reasoning.

**CEG Relevance:** Critical for cost control. A non-LLM fallback mode can be implemented using only embedding similarity, making multi-hop traversal viable for high-throughput production workloads.

### 2.10 Small SLM (Qwen 1.5B) as Cost-Effective Traversal Model

**Paper Reference:** §4.3 "Effect of Reasoning Model"

Qwen2.5-1.5B-Instruct achieves near GPT-4o-mini performance at a fraction of the cost (~38.53 LLM calls per query at n_hop=4, top_k=20). This enables local deployment without external API dependency.

**CEG Relevance:** Traversal model selection can be a configuration option (`traversal_model: "qwen-1.5b" | "gpt-4o-mini" | "none"`).

### 2.11 Passage-as-Vertex (No Summarization)

**Paper Reference:** §3.1 "Index Construction"

Passages are stored verbatim as vertex content—no summarization or abstraction. This avoids:
- Hallucination from summarization
- Information loss from compression
- Inconsistency between stored text and edge questions

**CEG Relevance:** Aligns with CEG's existing approach of storing entities with raw properties. No change needed; this validates current practice.

### 2.12 Directed Edges (Asymmetric Logical Relations)

**Paper Reference:** §3.2

Edges are directed: `p_s → p_t` means "a question arising from `p_s` can be answered by `p_t`". This asymmetry encodes logical dependency and reasoning direction.

**CEG Relevance:** Neo4j natively supports directed edges. The traversal assembler already handles directional patterns. No architectural change needed.

### 2.13 Queue Length Decay as Natural Stopping Criterion

**Paper Reference:** §4.3 "Effect of Hop Number"

BFS queue length naturally decays across hops:
- Hop 1: high fan-out (many neighbors)
- Hop 4: avg 2.60 active paths
- Hop 5: avg 1.23 active paths

This means traversal self-terminates without needing an artificial cutoff. The `max_hops` parameter serves as a safety bound, not the primary stopping mechanism.

**CEG Relevance:** Elegant stopping criterion that avoids over-traversal. Maps to the `MultiHopTraverser` queue management logic.

### 2.14 top_k Efficiency

**Paper Reference:** §4.3 "Effect of Top-k"

HopRAG at top_k=12 achieves QA accuracy comparable to competitors at top_k=20. This 40% reduction in retrieved passages reduces downstream LLM context window usage and cost.

**CEG Relevance:** The `top_n` parameter in `handle_match()` directly corresponds. A lower default can be recommended when HopRAG traversal is active.

---

## Part 3: Executable Reality Filter Matrix

| # | Concept | Classification | Justification | Target Component |
|---|---|---|---|---|
| 2.1 | Query Simulation (Pseudo-Query Gen) | **ADAPTABLE** | Requires new indexing pipeline + LLM integration; no existing pseudo-query infrastructure | `engine/hoprag/indexer.py`, `engine/traversal/pseudo_query.py` |
| 2.2 | Edge Merging with Hybrid Similarity | **ADAPTABLE** | Requires new edge creation logic combining Jaccard + cosine; no existing edge-similarity computation | `engine/traversal/edge_merger.py` |
| 2.3 | Retrieve-Reason-Prune Pipeline | **ARCHITECTURAL** | New query-time pipeline mode parallel to gate-score; requires handler-level routing | `engine/handlers.py`, new handler |
| 2.4 | BFS with LLM-Guided Selection | **ARCHITECTURAL** | Application-level BFS outside Cypher; LLM integration during traversal is novel for CEG | `engine/traversal/multihop.py` |
| 2.5 | Visit Counter (IMP Metric) | **DIRECTLY EXECUTABLE** | Additive scoring dimension; reads pre-computed property from candidate node | `engine/scoring/importance.py`, `ScoringAssembler` dispatch |
| 2.6 | Helpfulness Metric | **DIRECTLY EXECUTABLE** | Combines two existing-pattern scores (similarity + importance) via arithmetic mean | `engine/scoring/helpfulness.py`, `ScoringAssembler` dispatch |
| 2.7 | O(n·log(n)) Edge Density Control | **DIRECTLY EXECUTABLE** | Domain-spec parameter + indexing-phase filter; no runtime code changes | `engine/hoprag/config.py`, indexer |
| 2.8 | Sparse+Dense Dual Indexing | **ADAPTABLE** | pgvector not yet integrated; sparse index via Neo4j full-text is feasible now | `engine/hoprag/indexer.py` |
| 2.9 | Non-LLM Traversal Fallback | **DIRECTLY EXECUTABLE** | Similarity-only edge selection is a simplified mode of the multi-hop traverser | `engine/traversal/multihop.py` |
| 2.10 | SLM Traversal Model (Qwen 1.5B) | **ADJACENT** | Model hosting/selection is outside repo scope; configuration support is additive | `engine/hoprag/config.py` |
| 2.11 | Passage-as-Vertex | **SKIP** | Already aligned with CEG practice; no change needed | N/A |
| 2.12 | Directed Edges | **SKIP** | Neo4j + existing traversal assembler already support directed edges | N/A |
| 2.13 | Queue Length Decay Stopping | **DIRECTLY EXECUTABLE** | Additive logic within MultiHopTraverser BFS loop | `engine/traversal/multihop.py` |
| 2.14 | top_k Efficiency (12 vs 20) | **DIRECTLY EXECUTABLE** | Configuration recommendation; no code change needed | Domain-spec YAML documentation |

### Classification Summary

| Classification | Count | Concepts |
|---|---|---|
| DIRECTLY EXECUTABLE | 6 | Visit Counter, Helpfulness, Edge Density, Non-LLM Fallback, Queue Decay, top_k |
| ADAPTABLE | 3 | Query Simulation, Edge Merging, Dual Indexing |
| ARCHITECTURAL | 2 | Retrieve-Reason-Prune Pipeline, BFS+LLM Selection |
| ADJACENT | 1 | SLM Model Selection |
| SKIP | 2 | Passage-as-Vertex, Directed Edges |

---

## Part 4: Enhancement Opportunity Map

### 4.1 Scoring Path Enhancements

| Concept | Target File | Integration Point | Wiring |
|---|---|---|---|
| Helpfulness Metric | `engine/scoring/helpfulness.py` → `engine/scoring/assembler.py` | Add `ComputationType.HELPFULNESS` to dispatch dict in `_compile_dimension()` | New scoring dimension in domain-spec YAML: `computation: helpfulness`, reads `candidate.helpfulness_score` |
| Visit-Count Importance | `engine/scoring/importance.py` → `engine/scoring/assembler.py` | Add `ComputationType.IMPORTANCE` to dispatch dict | New dimension: `computation: importance`, reads `candidate.visit_count` |

### 4.2 Traversal Path Enhancements

| Concept | Target File | Integration Point | Wiring |
|---|---|---|---|
| Multi-Hop BFS | `engine/traversal/multihop.py` | Called from `handle_match()` *before* Cypher scoring query | Writes `visit_count`, `helpfulness_score` to candidate nodes in Neo4j |
| Non-LLM Fallback | `engine/traversal/multihop.py` | Mode flag within `MultiHopTraverser` | `reasoning_mode: "llm" | "similarity" | "none"` in config |
| Queue Decay Stop | `engine/traversal/multihop.py` | BFS loop termination check | `if queue_length < min_queue_size: break` |

### 4.3 Indexing Path Enhancements

| Concept | Target File | Integration Point | Wiring |
|---|---|---|---|
| Pseudo-Query Generation | `engine/traversal/pseudo_query.py` → `engine/hoprag/indexer.py` | Post-sync enrichment pipeline | Called after `handle_sync()` or as a batch admin subaction |
| Edge Merging | `engine/traversal/edge_merger.py` → `engine/hoprag/indexer.py` | After pseudo-query generation | Creates directed edges with hybrid similarity threshold |
| Edge Density Control | `engine/hoprag/config.py` | Parameterizes edge merging | `max_edges = n * log(n)` where n = vertex count |

### 4.4 Orchestration Path Enhancements

| Concept | Target File | Integration Point | Wiring |
|---|---|---|---|
| HopRAG Config | `engine/hoprag/config.py` | Domain-spec YAML `hoprag:` section | Pydantic model parsed alongside existing spec sections |
| Feature Gate | `engine/config/settings.py` | `settings.hoprag_enabled` flag | Mirrors `kge_enabled` pattern |
| Traversal Model Selection | `engine/hoprag/config.py` | `traversal_model` field | Routes to LLM provider or local SLM |
| Cost Monitoring | `chassis/orchestrator.py` | `_METRICS["token_usage_total"]` | HopRAG LLM calls increment the existing token counter |

---

## Part 5: Phased Integration Plan

### Phase A: Immediate (Additive-Only, ~2 weeks)

**Goal:** Add scoring dimensions and configuration without modifying existing runtime behavior.

| Task | Deliverable | Effort | Risk |
|---|---|---|---|
| A1: Helpfulness scoring dimension | `engine/scoring/helpfulness.py` | S | Low |
| A2: Visit-count importance scoring | `engine/scoring/importance.py` | S | Low |
| A3: Edge density control parameter | `engine/hoprag/config.py` | S | Low |
| A4: Dual-index config support | `engine/hoprag/config.py` | S | Low |
| A5: HopRAG feature gate | `engine/config/settings.py` update | S | Low |
| A6: Unit tests for all Phase A | `tests/unit/test_*.py` | M | Low |

**Integration pattern:** All Phase A changes are additive. New files only; no modification to existing production code. Scoring dimensions are registered but dormant until a domain-spec references them.

### Phase B: Near-Term (Wiring Changes, ~4 weeks)

**Goal:** Implement multi-hop traversal engine and indexing pipeline.

| Task | Deliverable | Effort | Risk |
|---|---|---|---|
| B1: Multi-hop traversal assembler | `engine/traversal/multihop.py` | L | Medium |
| B2: Pseudo-query generation | `engine/traversal/pseudo_query.py` | M | Medium |
| B3: BFS traversal with queue management | Integrated into B1 | L | Medium |
| B4: Edge merger | `engine/traversal/edge_merger.py` | M | Medium |
| B5: Graph index builder | `engine/hoprag/indexer.py` | L | Medium |
| B6: Integration tests | `tests/integration/test_hoprag_pipeline.py` | M | Medium |

**Integration pattern:** Phase B modifies `handle_match()` to optionally invoke `MultiHopTraverser` before Cypher scoring. Gated behind `settings.hoprag_enabled`. Requires Neo4j write permissions during query (for visit-count writeback).

### Phase C: Medium-Term (New Subsystem, ~6 weeks)

**Goal:** Add LLM reasoning to traversal and implement Retrieve-Reason-Prune pipeline.

| Task | Deliverable | Effort | Risk |
|---|---|---|---|
| C1: Reasoning-augmented traversal | LLM hook in `MultiHopTraverser` | XL | High |
| C2: Retrieve-Reason-Prune pipeline | New handler or mode in `handle_match()` | XL | High |
| C3: Non-LLM fallback mode | Mode switch in traverser config | M | Low |
| C4: Traversal cost monitoring | Token counting in orchestrator | S | Low |
| C5: Benchmark tooling | `tools/hoprag_benchmark.py` | M | Low |

**Integration pattern:** Phase C requires LLM provider integration (API client, prompt management, error handling). The LLM hook is optional—the traverser works without it (fallback mode from Phase B).

### Phase D: Long-Term (Full HopRAG Integration, ~8 weeks)

**Goal:** Complete HopRAG capability with production hardening.

| Task | Deliverable | Effort | Risk |
|---|---|---|---|
| D1: Full graph-structured index builder | End-to-end indexing pipeline | XL | High |
| D2: Traversal model selection | GPT-4o-mini vs local Qwen routing | L | Medium |
| D3: Adaptive n_hop | Dynamic hop count based on queue decay | M | Medium |
| D4: Production monitoring | Grafana dashboards, alerting | L | Low |
| D5: Documentation | API docs, runbooks, architecture diagrams | M | Low |

---

## Part 6: Architectural-Change Review List

### 6.1 Retrieve-Reason-Prune Pipeline

| Aspect | Detail |
|---|---|
| **What changes** | `handle_match()` gains a new code path where, before Cypher scoring, an application-level BFS traversal reads/writes Neo4j nodes. This changes the handler from a pure "compile Cypher and execute" function to one that orchestrates multi-step graph operations. |
| **Why it's architectural** | The current `handle_match()` is stateless: it compiles a single Cypher query and executes it. The HopRAG pipeline requires multiple sequential Neo4j operations (read neighbors, LLM reasoning, write visit counts, then score). This changes the execution model from single-query to multi-step. |
| **Risk level** | **HIGH** — Performance impact on existing match queries; potential transaction isolation issues; increased Neo4j load from write operations during read path. |
| **Mitigation strategy** | (1) Gate behind `settings.hoprag_enabled` with default=False. (2) Implement as a separate handler `handle_multihop_match` rather than modifying `handle_match`. (3) Use Neo4j transient properties (not persisted to disk) for visit counts. (4) Timeout guard on BFS loop. |

### 6.2 BFS with LLM-Guided Selection

| Aspect | Detail |
|---|---|
| **What changes** | Introduces LLM API calls into the hot path of query execution. Each BFS step requires a synchronous LLM call to evaluate edge helpfulness. At n_hop=4, top_k=20 this means ~38 LLM calls per query. |
| **Why it's architectural** | CEG currently has zero LLM dependencies in the query path. Adding LLM calls introduces: external service dependency, latency variability (50ms-2s per call), rate limiting concerns, cost accumulation, and failure modes that don't exist today. |
| **Risk level** | **HIGH** — Latency impact (potentially 5-30 seconds per query), cost impact ($0.01-0.10 per query at GPT-4o-mini rates), availability dependency on external API. |
| **Mitigation strategy** | (1) Non-LLM fallback is the default mode; LLM reasoning is opt-in. (2) Batch LLM calls where possible (evaluate multiple edges in one prompt). (3) Local SLM option (Qwen 1.5B) eliminates external dependency. (4) Token budget per query with hard cutoff. (5) Async LLM calls with configurable timeout. |

### 6.3 Indexing-Phase Pseudo-Query Generation

| Aspect | Detail |
|---|---|
| **What changes** | The sync/enrichment pipeline gains a new stage that calls an LLM for every passage in the graph to generate pseudo-queries. For a 10,000-passage graph, this means ~10,000 LLM calls during indexing. |
| **Why it's architectural** | Transforms the sync pipeline from a "write data to Neo4j" operation to a "write data, then enrich with LLM, then create edges" multi-stage pipeline. This changes the data ingestion model fundamentally. |
| **Risk level** | **MEDIUM** — Indexing is offline (not in query path), but LLM cost and time for large graphs could be significant. A 10K passage graph needs ~60K LLM calls (6 questions per passage). |
| **Mitigation strategy** | (1) Run as a separate batch job, not inline with sync. (2) Incremental indexing: only process new/changed passages. (3) Cache pseudo-queries; re-generation only on content change. (4) Configurable batch size with progress tracking. |

### 6.4 Neo4j Write-on-Read Pattern

| Aspect | Detail |
|---|---|
| **What changes** | The multi-hop traverser writes visit counts back to Neo4j nodes during a query operation. This introduces writes into what is currently a read-only query path. |
| **Why it's architectural** | Read-only query paths have simpler transaction semantics, better caching behavior, and no write-contention risks. Adding writes could affect Neo4j's read caching and create contention under concurrent queries. |
| **Risk level** | **MEDIUM** — Transaction isolation ensures correctness, but write-contention under high concurrency could degrade performance. |
| **Mitigation strategy** | (1) Use Neo4j transient node properties that are not persisted. (2) Alternative: maintain visit counts in application memory (Python dict) and pass to scoring as parameters rather than writing to Neo4j. (3) If Neo4j writes are necessary, use a separate write transaction after the read traversal completes. |

---

## Part 7: Safe Additive Enhancement Specs

### 7.1 HelpfulnessScorer

| Field | Value |
|---|---|
| **Target file** | `engine/scoring/helpfulness.py` (NEW) |
| **Class** | `HelpfulnessScorer` |
| **Function** | `compute_helpfulness(similarity: float, importance: float, alpha: float = 0.5) → float` |
| **Input contract** | `similarity` ∈ [0.0, 1.0], `importance` ∈ [0.0, 1.0], `alpha` ∈ [0.0, 1.0] |
| **Output contract** | `float` ∈ [0.0, 1.0] |
| **Algorithm** | `H = alpha * similarity + (1 - alpha) * importance` |
| **Integration point** | Add `ComputationType.HELPFULNESS` to `ScoringAssembler._compile_dimension()` dispatch. Cypher reads `candidate.helpfulness_score` (pre-computed by traverser) or computes inline from `candidate.similarity_score` and `candidate.visit_count`. |
| **Test requirements** | Boundary values (0,0), (1,1), (0.5, 0.5); alpha=0 (pure importance); alpha=1 (pure similarity); out-of-range inputs raise ValueError. |

### 7.2 ImportanceScorer

| Field | Value |
|---|---|
| **Target file** | `engine/scoring/importance.py` (NEW) |
| **Class** | `ImportanceScorer` |
| **Function** | `compute_importance(visit_count: int, total_visits: int) → float` |
| **Input contract** | `visit_count` ≥ 0, `total_visits` > 0 |
| **Output contract** | `float` ∈ [0.0, 1.0] |
| **Algorithm** | `IMP = visit_count / total_visits` |
| **Integration point** | Add `ComputationType.IMPORTANCE` to `ScoringAssembler._compile_dimension()` dispatch. Cypher reads `candidate.visit_count` node property. Total visits passed as query parameter. |
| **Test requirements** | Zero visits → 0.0; single visit of total 1 → 1.0; proportional distribution with multiple candidates. |

### 7.3 MultiHopTraverser (Non-LLM Mode)

| Field | Value |
|---|---|
| **Target file** | `engine/traversal/multihop.py` (NEW) |
| **Class** | `MultiHopTraverser` |
| **Function** | `traverse(start_vertices: list[str], max_hops: int = 4, top_k: int = 12) → TraversalResult` |
| **Input contract** | `start_vertices`: list of Neo4j node IDs; `max_hops` ≥ 1; `top_k` ≥ 1 |
| **Output contract** | `TraversalResult(visited: dict[str, int], ranked: list[tuple[str, float]], hops_executed: int)` |
| **Algorithm** | BFS from start vertices. At each vertex, select top-1 outgoing edge by cosine similarity to query embedding. Count visits. Stop when queue is empty or max_hops reached. |
| **Integration point** | Called from `handle_match()` or new `handle_multihop_match()` handler before scoring Cypher query. |
| **Test requirements** | Linear graph traversal (A→B→C); branching graph; cycle detection; empty queue termination; max_hops termination. |

### 7.4 EdgeMerger

| Field | Value |
|---|---|
| **Target file** | `engine/traversal/edge_merger.py` (NEW) |
| **Class** | `EdgeMerger` |
| **Function** | `merge_edges(source_triplets, target_triplets, density_limit) → list[Edge]` |
| **Input contract** | Source/target triplets as lists of `(question, keywords, embedding)` tuples; density_limit as int |
| **Output contract** | List of `Edge(source_id, target_id, similarity, question_text)` |
| **Algorithm** | (1) Compute hybrid similarity for all (source_out, target_in) pairs. (2) Sort by similarity descending. (3) Keep top `density_limit` edges. |
| **Integration point** | Called by `engine/hoprag/indexer.py` during graph construction phase. |
| **Test requirements** | Correct Jaccard computation; correct cosine computation; correct hybrid average; density limit enforcement; empty inputs. |

### 7.5 PseudoQueryGenerator

| Field | Value |
|---|---|
| **Target file** | `engine/traversal/pseudo_query.py` (NEW) |
| **Class** | `PseudoQueryGenerator` |
| **Functions** | `generate_incoming_questions(passage: str, n: int = 2) → list[str]`; `generate_outgoing_questions(passage: str, m: int = 4) → list[str]` |
| **Input contract** | `passage`: non-empty string; `n`, `m` ≥ 1 |
| **Output contract** | List of question strings |
| **Algorithm** | LLM prompt templates per HopRAG paper Fig 4 / Fig 5. Incoming questions: "What questions can be answered by this passage?" Outgoing questions: "What follow-up questions does this passage raise that it cannot answer?" |
| **Integration point** | Called by `engine/hoprag/indexer.py` during indexing phase. |
| **Test requirements** | Correct prompt formatting; handles empty passage; respects n/m count; mock LLM responses. |

### 7.6 HopRAG Configuration

| Field | Value |
|---|---|
| **Target file** | `engine/hoprag/config.py` (NEW) |
| **Class** | `HopRAGConfig` (dataclass) |
| **Fields** | `enabled: bool`, `n_hop: int`, `top_k: int`, `edge_density_factor: float`, `traversal_model: str`, `reasoning_mode: str`, `alpha: float`, `min_queue_size: int`, `max_llm_calls_per_query: int` |
| **Defaults** | `enabled=False`, `n_hop=4`, `top_k=12`, `edge_density_factor=1.0`, `traversal_model="none"`, `reasoning_mode="similarity"`, `alpha=0.5`, `min_queue_size=1`, `max_llm_calls_per_query=50` |
| **Integration point** | Parsed from domain-spec YAML `hoprag:` section. Read by `MultiHopTraverser` and scoring dimensions. |
| **Test requirements** | Default values; YAML parsing; validation of bounds; serialization. |

---

## Part 8: Proposed Patch Set / Code Artifacts

All code artifacts are provided as separate files in this bundle. See:

- `engine/scoring/helpfulness.py` — HopRAG Helpfulness scoring dimension
- `engine/scoring/importance.py` — Visit-count importance scoring
- `engine/traversal/multihop.py` — Multi-hop BFS traversal engine
- `engine/traversal/pseudo_query.py` — Pseudo-query generation for edge enrichment
- `engine/traversal/edge_merger.py` — Edge merging with hybrid similarity

Detailed implementation notes for each artifact are in Part 11 (Implementation Briefs).

---

## Part 9: Bridge Files / Helper Modules

All bridge files are provided as separate files in this bundle. See:

- `engine/hoprag/__init__.py` — HopRAG subsystem init
- `engine/hoprag/config.py` — HopRAG configuration
- `engine/hoprag/indexer.py` — Graph index builder
- `tools/hoprag_benchmark.py` — Benchmark tool

---

## Part 10: Tests / Validation Artifacts

All test files are provided as separate files in this bundle. See:

- `tests/unit/test_helpfulness.py`
- `tests/unit/test_multihop_traversal.py`
- `tests/unit/test_pseudo_query.py`
- `tests/unit/test_importance.py`
- `tests/unit/test_edge_merger.py`
- `tests/integration/test_hoprag_pipeline.py`

---

## Part 11: Implementation Briefs

### 11.1 How Helpfulness Scoring Integrates with Existing ScoringAssembler

The `ScoringAssembler._compile_dimension()` method uses a dispatch dict mapping `ComputationType` → compiler function. To integrate Helpfulness:

1. **Add enum value:** Add `HELPFULNESS = "helpfulness"` to `ComputationType` in `engine/config/schema.py`.
2. **Add compiler:** Add `ComputationType.HELPFULNESS: self._compile_helpfulness` to the dispatch dict in `_compile_dimension()`.
3. **Implement compiler:** The `_compile_helpfulness()` method reads two candidate properties:
   ```python
   def _compile_helpfulness(self, dim: ScoringDimensionSpec) -> str:
       alpha = dim.bias or 0.5
       sim_prop = sanitize_label(dim.candidateprop or "similarity_score")
       imp_prop = sanitize_label(dim.queryprop or "visit_count_normalized")
       default = float(dim.defaultwhennull)
       return (
           f"CASE WHEN candidate.{sim_prop} IS NULL THEN {default} "
           f"ELSE ({alpha} * coalesce(candidate.{sim_prop}, 0) + "
           f"{1 - alpha} * coalesce(candidate.{imp_prop}, 0)) END"
       )
   ```
4. **Domain-spec YAML:** Add a new scoring dimension:
   ```yaml
   scoring:
     dimensions:
       - name: helpfulness
         computation: helpfulness
         candidateprop: similarity_score
         queryprop: visit_count_normalized
         bias: 0.5
         defaultweight: 0.3
         defaultwhennull: 0.0
   ```

**Key design decision:** Helpfulness reads *pre-computed* properties from the candidate node, not raw visit counts. The `MultiHopTraverser` is responsible for normalizing visit counts and writing `visit_count_normalized` to Neo4j before the scoring query runs.

### 11.2 How MultiHopTraverser Plugs into the Handler Match Pipeline

The multi-hop traversal executes *before* the Cypher scoring query in `handle_match()`:

```python
# In handle_match(), after gate compilation but before scoring:
if settings.hoprag_enabled:
    hoprag_config = HopRAGConfig.from_domain_spec(domain_spec)
    traverser = MultiHopTraverser(
        graph_driver=graph_driver,
        config=hoprag_config,
    )
    traversal_result = await traverser.traverse(
        query_embedding=query.get("embedding"),
        start_vertex_ids=initial_candidates,
    )
    # Write visit counts to Neo4j for scoring consumption
    await traverser.write_visit_counts(
        graph_driver=graph_driver,
        database=domain_spec.domain.id,
        visit_counts=traversal_result.visit_counts,
    )
```

The traverser operates at the application level (Python), making individual Neo4j reads to fetch neighbors and optionally calling an LLM to evaluate edges. After traversal completes, visit counts are written back to candidate nodes as transient properties. The subsequent Cypher scoring query reads these properties through the HELPFULNESS and IMPORTANCE scoring dimensions.

### 11.3 How PseudoQueryGenerator Runs as an Indexing-Phase Enrichment Step

Pseudo-query generation is a batch operation that runs during graph construction, not at query time:

1. **Trigger:** Called by `engine/hoprag/indexer.py` after passages are synced to Neo4j.
2. **Process:** For each passage vertex:
   - Call `generate_incoming_questions(passage_text, n=2)` → 2 questions
   - Call `generate_outgoing_questions(passage_text, m=4)` → 4 questions
   - For each question, extract NER keywords and compute embedding vector
   - Store as triplets on the vertex: `r = (question, keywords, embedding)`
3. **Output:** Each vertex gains properties: `incoming_triplets`, `outgoing_triplets` (serialized JSON arrays or separate relationship nodes).
4. **Incremental mode:** Track passage content hash; only regenerate for new/changed passages.
5. **Cost control:** Batch LLM calls (multiple passages per prompt where possible). Log total LLM calls and cost.

### 11.4 How Edge Density Control Maps to Domain Spec YAML

Edge density is parameterized through the HopRAG config section:

```yaml
hoprag:
  enabled: true
  edge_density_factor: 1.0  # multiplier on n*log(n)
  max_edges_per_vertex: 10   # hard cap per vertex
```

The `EdgeMerger` computes the density limit as:

```python
n = vertex_count
base_limit = int(n * math.log(n))
adjusted_limit = int(base_limit * config.edge_density_factor)
per_vertex_limit = min(adjusted_limit // n, config.max_edges_per_vertex)
```

For a 10,000-vertex graph: `base_limit = 10000 * log(10000) ≈ 92,103 edges`, or ~9.2 per vertex. With the paper's observed average of 5.87, the density factor can be tuned down to 0.6 for sparser graphs.

### 11.5 How Visit-Count Importance Feeds into the Helpfulness Metric

The data flow is:

1. **MultiHopTraverser** performs BFS, counting visits per vertex:
   ```python
   visit_counts = {vertex_id: count for vertex_id, count in traversal.items()}
   total_visits = sum(visit_counts.values())
   ```

2. **Normalization** happens in the traverser:
   ```python
   normalized = {vid: count / total_visits for vid, count in visit_counts.items()}
   ```

3. **Write to Neo4j** as transient property:
   ```cypher
   UNWIND $updates AS update
   MATCH (n {entity_id: update.id})
   SET n.visit_count_normalized = update.importance
   ```

4. **ScoringAssembler** reads via HELPFULNESS dimension:
   ```cypher
   (0.5 * coalesce(candidate.similarity_score, 0) + 0.5 * coalesce(candidate.visit_count_normalized, 0))
   ```

### 11.6 How the Non-LLM Fallback Mode Works as a Cost Optimization

The `MultiHopTraverser` supports three reasoning modes:

| Mode | Edge Selection | LLM Calls | Performance vs Paper |
|---|---|---|---|
| `"llm"` | LLM evaluates edge helpfulness | ~38 per query | 100% (full HopRAG) |
| `"similarity"` | Cosine similarity to query embedding | 0 | ~75% (still 25% above baseline) |
| `"none"` | No multi-hop traversal | 0 | Baseline (existing CEG) |

In `"similarity"` mode, the traverser replaces the LLM call with:

```python
def _select_next_edge_similarity(self, query_embedding, candidate_edges):
    best_edge = max(
        candidate_edges,
        key=lambda e: cosine_similarity(query_embedding, e.embedding)
    )
    return best_edge
```

This eliminates all LLM cost while preserving the structural benefits of multi-hop graph traversal. The paper demonstrates this mode still achieves 25.43% improvement over dense retriever.

**Recommendation:** Default to `"similarity"` mode in production. Switch to `"llm"` mode only for high-value queries where accuracy justifies the cost.

### 11.7 How to Configure Traversal Model Selection

The HopRAG config supports model selection via the `traversal_model` field:

```yaml
hoprag:
  traversal_model: "gpt-4o-mini"  # or "qwen-1.5b" or "none"
  max_llm_calls_per_query: 50
  llm_timeout_ms: 2000
```

Model routing logic in `MultiHopTraverser`:

```python
if config.traversal_model == "none":
    self._select_edge = self._select_next_edge_similarity
elif config.traversal_model == "qwen-1.5b":
    self._llm_client = LocalSLMClient(model="Qwen2.5-1.5B-Instruct")
    self._select_edge = self._select_next_edge_llm
else:
    self._llm_client = APIClient(model=config.traversal_model)
    self._select_edge = self._select_next_edge_llm
```

The local SLM option (Qwen 1.5B) requires a local inference server (e.g., vLLM, Ollama) but eliminates external API dependency and cost. The paper shows it achieves near GPT-4o-mini performance.

---

## Part 12: Final Prioritized Roadmap

| Priority | Task | Effort | Dependencies | Impact (1-10) | Risk (1-10) | Files Touched | Phase |
|---|---|---|---|---|---|---|---|
| 1 | HopRAG feature gate (`hoprag_enabled`) | S | None | 3 | 1 | `engine/config/settings.py` | A |
| 2 | HopRAG configuration dataclass | S | P1 | 4 | 1 | `engine/hoprag/config.py` (NEW) | A |
| 3 | ImportanceScorer | S | P2 | 6 | 1 | `engine/scoring/importance.py` (NEW) | A |
| 4 | HelpfulnessScorer | S | P3 | 7 | 1 | `engine/scoring/helpfulness.py` (NEW) | A |
| 5 | Unit tests for P3+P4 | M | P3, P4 | 3 | 1 | `tests/unit/test_importance.py`, `tests/unit/test_helpfulness.py` (NEW) | A |
| 6 | Edge density control parameter | S | P2 | 4 | 1 | `engine/hoprag/config.py` | A |
| 7 | EdgeMerger with hybrid similarity | M | P6 | 6 | 3 | `engine/traversal/edge_merger.py` (NEW) | B |
| 8 | PseudoQueryGenerator | M | None | 7 | 4 | `engine/traversal/pseudo_query.py` (NEW) | B |
| 9 | MultiHopTraverser (non-LLM mode) | L | P2, P7 | 9 | 5 | `engine/traversal/multihop.py` (NEW) | B |
| 10 | Graph index builder | L | P7, P8 | 8 | 5 | `engine/hoprag/indexer.py` (NEW) | B |
| 11 | Integration into `handle_match()` | L | P9 | 9 | 6 | `engine/handlers.py` | B |
| 12 | Integration tests | M | P9, P10, P11 | 4 | 3 | `tests/integration/test_hoprag_pipeline.py` (NEW) | B |
| 13 | LLM reasoning hook in traverser | XL | P9 | 8 | 7 | `engine/traversal/multihop.py` | C |
| 14 | Retrieve-Reason-Prune pipeline | XL | P13 | 9 | 8 | `engine/handlers.py`, `engine/traversal/multihop.py` | C |
| 15 | Non-LLM fallback validation | M | P9, P13 | 6 | 2 | `engine/traversal/multihop.py` | C |
| 16 | Traversal cost monitoring | S | P13 | 5 | 2 | `chassis/orchestrator.py` | C |
| 17 | Benchmark tooling | M | P14 | 5 | 2 | `tools/hoprag_benchmark.py` (NEW) | C |
| 18 | Full graph-structured index builder | XL | P10, P14 | 9 | 7 | `engine/hoprag/indexer.py` | D |
| 19 | Traversal model selection (GPT-4o-mini vs Qwen) | L | P13 | 7 | 5 | `engine/hoprag/config.py`, `engine/traversal/multihop.py` | D |
| 20 | Adaptive n_hop based on queue decay | M | P9, P14 | 6 | 4 | `engine/traversal/multihop.py` | D |
| 21 | Production monitoring dashboards | L | P14 | 5 | 2 | Grafana configs (external) | D |
| 22 | Documentation and runbooks | M | All | 4 | 1 | `docs/` (external) | D |

### Critical Path

```
P1 → P2 → P3 → P4 → P5 (Phase A complete)
              ↘
               P6 → P7 → P10 → P11 → P12 (Phase B complete)
                     ↘        ↗
                      P8 ────
                             ↘
               P9 ────────────→ P13 → P14 → P15 (Phase C complete)
                                       ↓
                               P16, P17 (Phase C support)
                                       ↓
                               P18 → P19 → P20 → P21 → P22 (Phase D complete)
```

### Estimated Total Timeline

| Phase | Duration | Cumulative |
|---|---|---|
| Phase A | 2 weeks | 2 weeks |
| Phase B | 4 weeks | 6 weeks |
| Phase C | 6 weeks | 12 weeks |
| Phase D | 8 weeks | 20 weeks |

### Quick Wins (Highest Impact-to-Effort Ratio)

1. **HelpfulnessScorer** (P4): Impact 7, Effort S → Ratio 7.0
2. **ImportanceScorer** (P3): Impact 6, Effort S → Ratio 6.0
3. **MultiHopTraverser non-LLM** (P9): Impact 9, Effort L → Ratio 3.0
4. **PseudoQueryGenerator** (P8): Impact 7, Effort M → Ratio 3.5
5. **EdgeMerger** (P7): Impact 6, Effort M → Ratio 3.0

---

*End of HopRAG → CEG Enhancement Program v1.0.0*
