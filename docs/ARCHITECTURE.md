# L9 Graph Engine Architecture

## Overview
The Graph Cognitive Engine is a multi-domain matching system that performs gate-then-score graph traversal across Neo4j knowledge graphs. It integrates with the L9 chassis (universal FastAPI shell) via action handlers and uses domain-specific YAML specs to configure gates, scoring, traversal, and GDS jobs.

## Design Principles
1. **Chassis owns HTTP.** Engine never imports FastAPI or implements auth/tenant/CORS.
2. **Action handlers, not routes.** Engine exposes `async def handle_X(tenant, payload) -> dict`, registered with chassis.
3. **Domain-driven configuration.** All matching behavior (gates, scoring, traversal) declared in YAML specs.
4. **Security by default.** All Cypher labels/types pass `sanitize_label()` before interpolation.
5. **PacketEnvelope for persistence.** All events wrapped in immutable PacketEnvelope with content_hash idempotency.

## Directory Structure
[... detailed breakdown of every subdirectory ...]

## Chassis Integration Contract
[... exact signature of handlers, registration pattern, tenant flow ...]

## Gate Compilation Pipeline
[... traversal → gates → scoring → Cypher assembly ...]

## Security Model
[... sanitize_label implementation, injection vectors, domain spec validation ...]

## Testing Strategy
[... unit/integration/compliance/performance test breakdown ...]

## Deployment
[... Docker, Terraform, Railway/ArgoCD flow ...]

## References
- L9 Platform Architecture: Single ingress contract, chassis modules
- L9 Infrastructure Reference: PacketEnvelope schema, memory substrate
