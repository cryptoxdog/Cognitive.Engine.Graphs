# L9 Graph Cognitive Engine

**Domain-agnostic, graph-native matching engine.** Define rules in YAML. Get a deployed, multi-tenant matching API with zero custom code.

[![Tests](https://img.shields.io/badge/tests-200%2B-green)]()
[![Coverage](https://img.shields.io/badge/coverage-70%25%2B-green)]()
[![License](https://img.shields.io/badge/license-proprietary-blue)]()

---

## What It Does

L9 ingests a **domain specification** (YAML) describing entities, gates (hard filters), scoring dimensions (soft ranking), and sync rules — then compiles them into a live matching API backed by Neo4j.

```
YAML Domain Spec → L9 Engine → Multi-Tenant Matching API
```

One engine. Any vertical. No custom code per domain.

### Proven Domains

| Domain | Query Entity | Candidate Entity | Gates | Scoring |
|--------|-------------|-----------------|-------|---------|
| Mortgage Brokerage | Borrower | Loan Product | credit, DTI, LTV, FICO | rate, speed, approval odds |
| Plastics Marketplace | Buyer RFQ | Supplier | polymer, MOQ, certs, geo | price, distance, reliability |
| Healthcare Matching | Patient | Provider | insurance, specialty, panel | distance, availability, rating |

## Quick Start

```bash
# 1. Clone & setup
git clone <repo-url> && cd l9-engine
./scripts/setup.sh

# 2. Start local stack (Neo4j + Redis + API)
./scripts/dev.sh

# 3. Seed sample data
./scripts/seed.sh plasticos

# 4. Match!
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: plasticos" \
  -H "Content-Type: application/json" \
  -d '{"query": {"polymertype": "HDPE", "quantitylbs": 5000, "lat": 33.45, "lon": -84.39}, "top_n": 5}'
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                │
│  /v1/match  /v1/sync  /v1/admin  /v1/health         │
├──────────────────────────────────────────────────────┤
│              Tenant Resolver Middleware               │
│         X-Domain-Key → database isolation            │
├──────────┬───────────┬───────────┬───────────────────┤
│  Gate    │  Scoring  │   Sync    │  GDS Scheduler    │
│ Compiler │ Assembler │ Generator │  (PageRank, etc)  │
├──────────┴───────────┴───────────┴───────────────────┤
│                Domain Spec Loader                     │
│           YAML → Pydantic → Compiled Cypher          │
├──────────────────────────────────────────────────────┤
│  Neo4j (multi-database)  │  Redis (cache/scheduler)  │
└──────────────────────────┴───────────────────────────┘
```

### Core Concepts

- **Gate** — Hard pass/fail filter compiled to Cypher WHERE clauses. 10 types: threshold, range, boolean, enum_map, exclusion, self_range, freshness, temporal_range, traversal, composite.
- **Scoring Dimension** — Soft ranking factor (geodecay, inverse linear, etc.) compiled to Cypher WITH expressions. Weighted, direction-scoped.
- **Sync** — UNWIND-based bulk upsert from any source into Neo4j. Handles taxonomy edges, child entities, derived properties.
- **Domain Spec** — Single YAML file defining an entire matching domain: ontology, gates, scoring, sync, compliance.
- **Multi-Tenant** — One engine, N databases. Tenant resolved from `X-Domain-Key` header or subdomain.
- **Bidirectional** — Gates and scoring invert for reverse matching (supplier finds buyers).

## Project Structure

```
l9-engine/
├── engine/                        # Core application
│   ├── api/                       # FastAPI routes + middleware
│   │   ├── app.py                 # Application factory
│   │   ├── routes/                # /match, /sync, /admin, /health
│   │   └── middleware.py          # Tenant resolution, error handling
│   ├── gates/                     # Gate compiler
│   │   ├── compiler.py            # YAML → Cypher WHERE
│   │   └── types/                 # 10 gate type implementations
│   ├── scoring/                   # Scoring assembler
│   │   ├── assembler.py           # Dimensions → Cypher WITH
│   │   └── computations/          # geodecay, inverselinear, etc.
│   ├── sync/                      # Sync generator
│   │   └── generator.py           # UNWIND MERGE/MATCH SET
│   ├── gds/                       # GDS scheduler
│   │   └── scheduler.py           # APScheduler + Neo4j GDS
│   ├── config/                    # Domain spec loader
│   │   ├── schema.py              # Pydantic models
│   │   └── loader.py              # YAML → validated config
│   ├── compliance/                # Regulatory enforcement
│   │   ├── prohibited_factors.py  # ECOA/HIPAA field blocking
│   │   ├── pii.py                 # PII hash/encrypt/redact
│   │   └── audit.py               # Audit logging
│   └── db/                        # Database layer
│       ├── neo4j.py               # Async Neo4j driver pool
│       └── redis.py               # Redis connection
├── domains/                       # Domain specification packs
│   ├── plasticos/
│   ├── mortgage-brokerage/
│   └── healthcare-matching/
├── tests/                         # 200+ tests, 70%+ coverage
│   ├── unit/
│   ├── compliance/
│   ├── integration/
│   └── performance/
├── iac/                           # Terraform (reusable across repos)
│   ├── main.tf
│   └── modules/
├── dashboards/                    # Grafana JSON dashboards
├── scripts/                       # Operational scripts
├── docker-compose.yml             # Local dev stack
├── Dockerfile                     # Multi-stage production build
├── pyproject.toml                 # Poetry dependencies
├── .env.example                   # Env var template
├── .gitignore
├── .dockerignore
├── CHANGELOG.md
├── LICENSE
└── README.md                      # ← You are here
```

## Environment Variables

Consistent across all L9 repos. Set in `.env` (local) or SSM Parameter Store (prod).

| Variable | Default | Description |
|----------|---------|-------------|
| `L9_PROJECT` | `l9-engine` | Project/repo identifier |
| `L9_ENV` | `dev` | Environment (dev/staging/prod) |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | — | Neo4j password (SSM in prod) |
| `NEO4J_DATABASE` | `neo4j` | Default database |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `API_PORT` | `8000` | API listen port |
| `API_WORKERS` | `4` | Uvicorn workers |
| `DOMAINS_ROOT` | `./domains` | Path to domain specs |
| `LOG_LEVEL` | `INFO` | Logging level |
| `GDS_ENABLED` | `true` | Enable GDS scheduler |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/match` | Execute matching query |
| `POST` | `/v1/sync/{entity}` | Bulk sync entities |
| `GET` | `/v1/health` | Health check |
| `GET` | `/v1/admin/domains` | List loaded domains |
| `POST` | `/v1/admin/gds/trigger/{job}` | Trigger GDS job |
| `GET` | `/v1/metrics` | Prometheus metrics |

## Development

```bash
# Run tests
./scripts/test.sh              # Full suite + coverage
./scripts/test.sh unit         # Unit only (fast)
./scripts/test.sh compliance   # Compliance only (critical)

# Code quality
poetry run ruff check engine/
poetry run mypy engine/

# Local monitoring
docker compose -f dashboards/docker-compose.monitoring.yml up -d
open http://localhost:3000     # Grafana (admin/admin)
```

## Deployment

```bash
# Build & push
./scripts/build.sh v1.0.0

# Deploy (Terraform)
./scripts/deploy.sh prod apply
```

See [iac/README.md](iac/README.md) for full infrastructure docs.

## Adding a New Domain

1. Create `domains/<name>/spec.yaml` following the domain spec schema
2. Add seed data in `domains/<name>/seeds/`
3. Add migrations in `domains/<name>/migrations/`
4. Deploy — no code changes required

See existing domains for examples.

## License

Proprietary. All rights reserved.
