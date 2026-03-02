
**Closes:** Agents inventing random environment variable names

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Environment Variable Contract

## Rule
All L9 env vars use the prefix `L9_` for constellation-wide settings.
Engine-specific vars use `{ENGINE}_` prefix. Names are UPPER_SNAKE_CASE.

## Constellation-Wide (every node reads these)
```bash
# Auth
L9_API_KEY_HASH=sha256:...           # SHA-256 hash of the API key
L9_API_KEY_PREFIX=pk_plasticos_      # Key prefix for tenant detection

# Tenant
L9_DEFAULT_TENANT=plasticos          # Fallback tenant ID
L9_TENANT_RESOLUTION=header          # header | subdomain | key_prefix | envelope

# Observability
L9_LOG_LEVEL=info                    # debug | info | warning | error
L9_LOG_FORMAT=json                   # json | text (json for prod, text for dev)
L9_TRACE_ENABLED=true                # W3C trace context propagation
L9_METRICS_PORT=9090                 # Prometheus metrics endpoint port

# Database
L9_POSTGRES_URL=postgresql://...     # Memory substrate connection
L9_REDIS_URL=redis://...             # Rate limiting, idempotency cache

# Constellation
L9_NODE_NAME=graph-engine            # This node's registered name
L9_CONSTELLATION_REGISTRY_URL=...    # Where to discover other nodes
```


## Engine-Specific (examples)

```bash
# Graph Engine
GRAPH_NEO4J_URI=bolt://localhost:7687
GRAPH_NEO4J_USERNAME=neo4j
GRAPH_NEO4J_PASSWORD=...
GRAPH_DOMAINS_DIR=domains

# Enrichment Engine
ENRICH_SONAR_API_KEY=pplx-...
ENRICH_MAX_VARIATIONS=5
ENRICH_CONSENSUS_THRESHOLD=0.75
ENRICH_KB_DIR=knowledge_bases

# Score Engine
SCORE_MODEL_PATH=models/scoring_v1.pkl
SCORE_DECAY_ENABLED=true
```


## WRONG

```bash
NEO4J_URI=...              # WRONG → GRAPH_NEO4J_URI (needs engine prefix)
neo4j_url=...              # WRONG → UPPER_SNAKE_CASE
DATABASE_URL=...           # WRONG → L9_POSTGRES_URL (use canonical name)
REDIS_HOST=...             # WRONG → L9_REDIS_URL (full URL, not host)
API_KEY=...                # WRONG → L9_API_KEY_HASH (hash, not plaintext)
```

```

