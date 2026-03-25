---
paths:
  - "engine/**/*.py"
  - "chassis/**/*.py"
  - "tools/**/*.py"
---
# CEG Contracts (1–24)

Enforced by `tools/contract_scanner.py` and `tools/verify_contracts.py`.

## Layer 1 — Chassis Boundary (1–5)
| # | Name | Rule |
|---|------|------|
| 1 | Single Ingress | Only POST /v1/execute and GET /v1/health. Engine NEVER imports FastAPI/Starlette. |
| 2 | Handler Interface | `async def handle_*(tenant: str, payload: dict) -> dict`. handlers.py is the ONLY engine file importing chassis (plus boot.py). |
| 3 | Tenant Isolation | Tenant resolved BY chassis. Every Neo4j query scopes to tenant database. No cross-tenant reads. |
| 4 | Observability Inherited | Engine NEVER configures structlog/Prometheus. Uses `structlog.get_logger(__name__)` only. |
| 5 | Infrastructure is Template | Engine NEVER creates Dockerfile, docker-compose, CI pipeline. All in l9-template. |

## Layer 2 — Packet Protocol (6–8)
| # | Name | Rule |
|---|------|------|
| 6 | PacketEnvelope Only | Every inter-service payload is a PacketEnvelope. inflate_ingress() at entry, deflate_egress() at exit. |
| 7 | Immutability + Hash | PacketEnvelope frozen. Mutations via .derive(). content_hash SHA-256 UNIQUE constraint. |
| 8 | Lineage + Audit | Derived packets set parent_id, root_id, increment generation. hop_trace append-only. |

## Layer 3 — Security (9–11)
| # | Name | Rule |
|---|------|------|
| 9 | Cypher Injection Prevention | Labels pass sanitize_label() regex ^[A-Za-z_][A-Za-z0-9_]*$. Values always parameterized. |
| 10 | Prohibited Factors | race, ethnicity, religion, gender, age, disability, familial_status, national_origin blocked at compile-time. |
| 11 | PII Handling | PII fields declared in spec compliance.pii.fields. Engine NEVER logs PII values. |

## Layer 4 — Engine Architecture (12–16)
| # | Name | Rule |
|---|------|------|
| 12 | Domain Spec Source of Truth | All behavior from YAML → DomainConfig Pydantic. Never raw YAML/dicts. |
| 13 | Gate-Then-Score | 10 gate types, 13 scoring computations. All in Cypher WHERE/WITH — no Python post-filtering. |
| 14 | NULL Semantics | Every gate declares null_behavior: pass or fail. Compiler handles it. |
| 15 | Bidirectional Matching | invertible: true swaps candidate ↔ query. match_directions scopes to direction. |
| 16 | File Structure Fixed | No new top-level directories without architectural approval. |

## Layer 5 — Testing + Quality (17–18)
| # | Name | Rule |
|---|------|------|
| 17 | Test Requirements | Unit for pure functions, integration with testcontainers-neo4j, compliance for prohibited factors, <200ms p95. |
| 18 | L9_META Headers | Every file carries L9_META header. Injected by tools/l9_meta_injector.py. |

## Layer 6 — Graph Intelligence (19–20)
| # | Name | Rule |
|---|------|------|
| 19 | GDS Declarative | Algorithms in spec.gds_jobs. Schedule: cron or manual. Projections spec-driven. |
| 20 | KGE Embeddings | CompoundE3D 256-dim, beam search width=10 depth=3. Domain-specific, never cross-tenant. |

## Layer 7 — Hardening (21–24)
| # | Name | Rule |
|---|------|------|
| 21 | Feature Flag Discipline | Every behavioral change gated by bool flag in settings.py. True for safety, False for experimental. |
| 22 | Scoring Weight Ceiling | Default weights sum ≤ 1.0. Enforced at startup. Reduce existing when adding new. |
| 23 | Admin Subaction Registration | snake_case, return {status, subaction}, log with tenant, validate with _require_key(). |
| 24 | Resilience Patterns | All Neo4j via GraphDriver. Circuit breaker 3/30s. Bounded caches only. No module-level globals. |
