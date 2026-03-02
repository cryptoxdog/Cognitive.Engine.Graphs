
**Closes:** Agents not knowing how to register a new constellation node

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Constellation Node Registration Contract

## Rule
Every node in the constellation has a fixed registration record. New nodes
MUST register before they can send or receive packets.

## Required Registration Fields
```yaml
node:
  name: "score-engine"                   # Unique, lowercase, hyphenated
  display_name: "SCORE — Lead/Deal Scoring Engine"
  version: "0.1.0"
  owner: "revopsos"                      # GitHub org or team
  repo: "Score.Engine"                   # GitHub repo name
  actions:                               # Actions this node handles
    - "score"
    - "score_batch"
    - "explain"
    - "score_profile"
  accepts_delegation_from:               # Which nodes can delegate to this one
    - "enrichment-engine"
    - "route-engine"
    - "forecast-engine"
    - "health-monitor"
    - "signal-capture"
  delegates_to:                          # Which nodes this one calls
    - "enrichment-engine"               # missing_fields → re-enrichment
    - "graph-engine"                    # graph_affinity scoring dimension
  port: 8003                            # Default port in docker-compose
  health_endpoint: "/v1/health"         # Standard — always this
  api_endpoint: "/v1/execute"           # Standard — always this
```


## Node Naming Convention

```
{domain}-engine     → domain-specific: "graph-engine", "score-engine"
{domain}-{function} → functional: "signal-capture", "health-monitor"
{vertical}          → vertical product: "plasticos", "mortgageos"
```


## BANNED

```python
"ScoreEngine"       # WRONG → "score-engine" (lowercase, hyphenated)
"score_engine"      # WRONG → "score-engine" (hyphens, not underscores)
"SCORE"             # WRONG → "score-engine" (full name, not abbreviation)
```

```

