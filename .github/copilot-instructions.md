<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [agent-rules]
tags: [L9_TEMPLATE, agent-rules, copilot]
owner: platform
status: active
/L9_META -->

# GitHub Copilot Instructions — L9 Graph Engine

## Architecture
This is an L9 constellation engine. The chassis handles HTTP; engines handle domain logic.

## Never Suggest
- FastAPI routes, APIRouter, or app factories in `engine/` code
- Tenant resolution functions (`resolve_tenant`, middleware)
- CORS, auth, or rate limiting setup
- Dockerfile, docker-compose, or Terraform modules (use templates)

## Always Suggest
- `async def handle_X(tenant: str, payload: dict) -> dict` for new actions
- `sanitize_label()` before Cypher label interpolation
- Type hints on all function signatures
- Pydantic models for structured data

## Testing
- Unit tests: Pure functions, no Neo4j
- Integration tests: Use `testcontainers-neo4j`, not mocks

## File Patterns
- `engine/handlers.py`: Action handler registration (register_all)
- `engine/config/schema.py`: Pydantic models for domain specs
- `engine/gates/compiler.py`: Gate → WHERE clause compilation
- `engine/scoring/assembler.py`: Scoring → WITH score clause
