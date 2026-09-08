# IdeaOS Idea Portfolio Domain

## Authority boundary

`idea-portfolio` is the CEG-owned graph intelligence surface for the first-class IdeaOS corpus.

- **IdeaOS owns:** idea identity, source lineage, lifecycle state, Dream / Invariant / Wedge / Proof, decisions, proof state, execution state, and semantic `IdeaGraphProjection` emission.
- **CEG owns:** graph persistence of that projection, cross-idea traversal, overlap/leverage matching, portfolio ranking, graph-derived relationships, communities, and learned graph signals.
- **Transport adapters own neither:** they may serialize, route, and translate only.

CEG must not parse raw files from IdeaOS `Ideas/`, infer an idea from a filename, or become a second lifecycle source of truth.

## Graph model

The first implementation intentionally uses two durable node classes:

```text
Idea --PRODUCES----> PortfolioFacet
     --REQUIRES----> PortfolioFacet
     --TARGETS-----> PortfolioFacet
     --USES--------> PortfolioFacet
     --DEPENDS_ON--> PortfolioFacet
```

`PortfolioFacet` is globally content-addressed by the exact `(kind, key)` pair. The source assertion's epistemic state, source references, projection digest, and graph revision live on the relationship, because those facts belong to the assertion between an Idea and a facet, not to the shared facet itself.

No inferred Idea-to-Idea edge is persisted by hydration. That keeps source projection separate from graph-derived intelligence.

## Why there is a dedicated hydration compiler

The generic `SyncGenerator` can MERGE nodes and fixed child/taxonomy edges, but it cannot express all of the required semantics for IdeaGraphProjection hydration:

1. the relationship type varies by assertion relation;
2. evidence/provenance belongs on each relationship;
3. replacing a projection must remove relationships that no longer exist;
4. corpus mutations need replayable revision-chain semantics;
5. deletions need an explicit tombstone rather than silent absence.

Those are current, evidenced responsibilities. `engine/sync/idea_portfolio.py` therefore owns the smallest domain-specific persistence compiler needed to bridge that expressiveness gap. It still uses the shared `GraphDriver`; it does not introduce a graph client, queue, database, or second scoring engine.

## Hydration contract

CEG accepts `ceg.idea-portfolio-hydration/v1`:

```json
{
  "schema": "ceg.idea-portfolio-hydration/v1",
  "source_snapshot_ref": "Quantum-L9/IdeaOS@<commit>",
  "source_snapshot_digest": "sha256:<64 hex>",
  "expected_graph_revision": null,
  "records": [
    {
      "schema": "ceg.idea-portfolio-sync-record/v1",
      "operation": "upsert",
      "projection": {
        "schema": "ideaos.idea-graph-projection/v1",
        "idea_id": "example",
        "source_refs": ["Ideas/..."],
        "source_digest": "sha256:<64 hex>",
        "lifecycle": {
          "stage": "expanded",
          "decision": null,
          "proof_state": null,
          "execution_state": null
        },
        "assertions": [],
        "unknowns": []
      }
    }
  ]
}
```

A tombstone record is explicit:

```json
{
  "schema": "ceg.idea-portfolio-sync-record/v1",
  "operation": "tombstone",
  "idea_id": "example"
}
```

The envelope contains at most one record per `idea_id`.

## Revision chain

Every successful hydration computes:

```text
batch_digest = sha256(canonical(records))
new_graph_revision = sha256(
    protocol_version
    + expected_graph_revision_or_GENESIS
    + source_snapshot_digest
    + batch_digest
)
```

The current committed revision is stored in `IdeaPortfolioHydrationState`. A batch can start only when its `expected_graph_revision` equals the committed revision. An exact interrupted revision can resume; an exact committed revision is an idempotent replay.

This gives the graph a replayable parent-linked mutation chain without inventing a timestamp-based ordering authority.

Hydration state remains `in_progress` if a write fails. A future context-read seam must refuse to label an in-progress graph as a committed snapshot. Retrying the exact same envelope resumes the interrupted revision.

## Epistemic rules

Hydration is stricter than filename ingestion:

- a hydrated projection must have at least one root `source_ref`;
- non-`UNKNOWN` assertions must have at least one assertion source reference;
- duplicate semantic assertions are rejected;
- relation/kind combinations are validated;
- keys are Unicode-NFC normalized and trimmed only, not lower-cased, synonym-expanded, or guessed;
- source relationships remain source relationships;
- graph-derived Idea-to-Idea relationships are not written by hydration.

The v1 kind/relation matrix is:

| Kind | Allowed relations |
| --- | --- |
| capability | produces, requires, uses |
| substrate | produces, requires, uses |
| proof_asset | produces, requires, uses |
| data_asset | produces, requires, uses |
| market | targets |
| customer_type | targets |
| dependency | depends_on |

## Portfolio matching

`build_portfolio_match_query()` compiles an IdeaGraphProjection into the flat query contract consumed by the current CEG match handler. It never calculates rank itself.

The domain ranks candidate Ideas using six graph-native dimensions:

1. candidate produces something the query idea requires;
2. candidate requires something the query idea produces;
3. shared `USES` facets;
4. shared `TARGETS` facets;
5. query idea explicitly depends on the candidate;
6. candidate explicitly depends on the query idea.

Weights sum to 1.0. The candidate itself is excluded, and tombstoned/inactive ideas fail the admission gate.

The result is **portfolio ranking evidence**, not IdeaOS lifecycle authorization.

## Centrality and learned graph signals

They deliberately do not exist in v0.1. The current CEG scheduler supports Louvain, co-occurrence, reinforcement, temporal recency, geo proximity, equipment sync, feedback recalculation, and causal chain scoring. It does not currently execute PageRank even though older documentation mentions it.

Declaring a PageRank job now would advertise a capability the runtime skips. Centrality is therefore deferred until an executable current owner path exists.

## Initial activation

1. Validate the domain:

   ```bash
   python tools/validate_domain.py domains/idea-portfolio/spec.yaml --strict
   ```

2. Ensure the `idea-portfolio` Neo4j database exists according to the deployment topology.
3. Initialize schema constraints through the existing admin `init_schema` path for domain `idea-portfolio`.
4. Produce a hydration envelope from source-bound IdeaOS projections.
5. Dry-run it first:

   ```bash
   python tools/hydrate_idea_portfolio.py hydration.json
   ```

6. Apply deliberately:

   ```bash
   python tools/hydrate_idea_portfolio.py hydration.json --apply
   ```

7. Persist the hydration receipt and its `graph_revision`. Use that revision as the `expected_graph_revision` parent of the next corpus delta.

## Corpus rule

Raw historical corpus hydration remains an IdeaOS semantic task:

```text
Ideas/ artifact
  -> deterministic source identity
  -> IdeaOS semantic extraction / expansion
  -> IdeaGraphProjection
  -> CEG hydration envelope
  -> CEG idea-portfolio graph
```

A raw ZIP, Markdown filename, or directory name is never sufficient evidence for semantic Idea identity or graph assertions.

## Failure boundaries

- **Bad projection:** reject before graph mutation.
- **Wrong parent revision:** reject the hydration revision.
- **Different revision already in progress:** reject rather than interleave two writers.
- **Mid-run failure:** keep `in_progress=true`; exact replay resumes.
- **Tombstone:** mark Idea inactive and remove its source-projection edges; do not delete shared facet nodes.
- **Orphan facets:** tolerated as non-authoritative derived residue. Garbage collection is deferred rather than mixed into the critical write transaction.

The v0.1 hydration transaction is atomic per graph write, while a multi-record hydration revision consists of multiple Neo4j write transactions guarded by the hydration state. The committed graph revision advances only after every record succeeds. Consumers must treat `in_progress=true` as an uncommitted snapshot boundary. A future live context adapter must enforce that read gate.
