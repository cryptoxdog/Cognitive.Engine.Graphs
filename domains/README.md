# domains/README.md
"""
L9 Graph Cognitive Engine - Domain Pack Repository

This directory contains production-ready domain packs for vertical matching systems.
Each domain pack is a complete, self-contained specification that the engine loads at runtime.

## Domain Pack Structure

```
domains/
├── {domain-id}/
│   ├── spec.yaml          # Complete domain specification (REQUIRED)
│   └── queries/           # Optional custom Cypher overrides
│       └── {gate-name}.cypher
```

## Available Domains

### Production Domains (Stress-Tested)
1. **plasticos** - Recycled plastic buyer-supplier matching (29 edge types, 22 gates)
2. **mortgage-brokerage** - Borrower-lender-product matching (ECOA-compliant)
3. **healthcare-referral** - Provider-patient-specialist matching (HIPAA-compliant)
4. **freight-matching** - Load-carrier matching with ELD integration

### Vertical AI Agents (AI-First Domains)
5. **roofing-company** - Contractor-project-material matching
6. **executive-assistant** - Task-expert-resource matching
7. **research-agent** - Query-paper-dataset matching
8. **aios-god-agent** - Tool-capability-workflow orchestration
9. **repo-as-agent** - Code-contributor-issue matching
10. **legal-discovery** - Case-document-precedent matching

## Creating a New Domain Pack

### Step 1: Create Directory
```bash
mkdir -p domains/my-domain/queries
```

### Step 2: Write spec.yaml
Required sections:
- `domain` - Metadata (id, name, version)
- `ontology` - Nodes and edges
- `matchentities` - Candidate and query entity definitions
- `queryschema` - Input schema for /v1/match
- `traversal` - Graph traversal steps
- `gates` - Filtering logic (10 gate types available)
- `scoring` - Ranking dimensions (9 computation types)

Optional sections:
- `derivedparameters` - Computed query parameters
- `softsignals` - Bonus/penalty adjustments
- `sync` - Batch entity sync endpoints
- `gdsjobs` - Graph Data Science background jobs
- `kge` - Knowledge graph embedding configuration
- `compliance` - Prohibited factors, audit, PII handling
- `plugins` - Pre/post-match hooks

### Step 3: Validate
```bash
# Load domain to validate
curl http://localhost:8000/v1/domains
```

### Step 4: Test
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: my-domain" \
  -d @test-query.json
```

## Domain Pack Best Practices

### Ontology Design
- Use semantic node labels (not generic "Entity")
- Separate capability, taxonomy, transaction, and exclusion edges
- Mark nodes as candidate/queryentity/taxonomy/auxiliary
- Specify managedby (sync, gds, static, api) per node

### Gate Design
- Start with 5-10 core gates (expand later)
- Use `nullbehavior: pass` for optional fields
- Mark invertible gates for bidirectional matching
- Add `strictwhen` for conditional enforcement

### Scoring Design
- 5-8 dimensions is optimal (avoid dimension explosion)
- Weight keys should be intuitive (wgeo, wprice, wquality)
- Use default weights that work without tuning
- Test with weights: {wkey: 0.0} to disable dimensions

### Traversal Design
- Required steps fail if pattern not found
- Optional steps (required: false) allow missing data
- Use meaningful aliases for scoring references
- Keep traversal depth ≤3 for performance

### Sync Design
- UNWINDMERGE for create-or-update
- UNWINDMATCHSET for partial updates (PATCH)
- Use taxonomy edges for auto-linking
- Batch size 100-1000 entities per request

### GDS Design
- Schedule compute-heavy jobs (cron: "0 2 * * *")
- Manual-trigger for on-demand jobs
- Write to separate properties (don't overwrite sync data)
- Test on small graphs before production

## Performance Guidelines

### Query Performance
- Target: p95 < 500ms, p99 < 1s
- Gates compile to single WHERE clause (no iteration)
- Scoring compiles to single WITH clause
- Traversal depth ≤3 recommended

### Sync Performance
- Target: 1000 entities < 2s
- UNWIND batching (single transaction)
- Taxonomy linking adds ~10ms per edge type
- Child sync adds ~50ms per child entity type

### GDS Performance
- Louvain (10K nodes): ~5min
- Cooccurrence (10K nodes, 100K edges): ~10min
- Schedule during low-traffic windows
- Use graph projections to limit scope

## Compliance Considerations

### Prohibited Factors (ECOA, HIPAA, FMCSA, etc.)
```yaml
compliance:
  prohibitedfactors:
    enabled: true
    blockedfields: [race, ethnicity, gender, age, disability]
    enforcement: compiletime  # Blocks gate compilation
```

### Audit Logging
```yaml
compliance:
  audit:
    enabled: true
    logmatchrequests: true
    logmatchresults: true
    retentiondays: 90
```

### PII Handling
```yaml
compliance:
  pii:
    enabled: true
    fields: [ssn, dob, email]
    handling: hash  # or encrypt, redact, tokenize
```

## Multi-Tenant Deployment

Each domain runs in isolated Neo4j database:
- Database name = domain.id
- Zero cross-tenant queries
- Independent GDS job schedules
- Separate KGE embeddings

## Domain Pack Versioning

```yaml
domain:
  id: my-domain
  version: 1.2.0
  alternatedomains: [my-domain-v1, legacy-domain]
```

Use semantic versioning:
- Major: Breaking changes (incompatible query schema)
- Minor: New features (new gates, scoring dimensions)
- Patch: Bug fixes, performance improvements

## Testing Your Domain

### Unit Tests
- Gate compilation (all gates produce valid Cypher)
- Scoring assembly (all dimensions compute)
- Traversal assembly (all patterns valid)
- Sync generation (all endpoints produce valid Cypher)

### Integration Tests
- Full match pipeline (query → candidates)
- NULL semantics (test with missing fields)
- Bidirectional matching (test both directions)
- Multi-tenant isolation (no cross-domain leakage)

### Load Tests
- 100 concurrent queries (target: p95 < 500ms)
- 10K entity sync (target: < 20s)
- GDS job execution (target: < 5min for 10K nodes)

## Support

For domain pack assistance:
- Review existing domains in this directory
- Check engine documentation: ../README.md
- Review schema: ../engine/config/schema.py

## License

All domain packs in this repository are examples for the L9 Graph Cognitive Engine.
Adapt freely for your vertical.
"""
