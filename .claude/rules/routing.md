---
paths:
  - "engine/**/*.py"
  - "tests/**/*.py"
---
# Where to Put Code

| Task | Target | Also Update |
|------|--------|-------------|
| New gate type | `engine/gates/types/all_gates.py` (extend BaseGate) | GateType enum in schema.py |
| New scoring computation | `engine/scoring/assembler.py` (add `_compile_*`) | ComputationType enum in schema.py |
| New admin subaction | `engine/handlers.py` handle_admin() dispatch | Admin Subactions table in rules |
| New action handler | `engine/handlers.py` (new handle_*) | register_all() in same file |
| New domain spec section | `engine/config/schema.py` (new Pydantic model) | DomainSpec field |
| New feature flag | `engine/config/settings.py` Settings class | Feature Flags in rules |
| Neo4j queries | ALWAYS through `engine/graph/driver.py` | Never raw driver sessions |
| New unit test | `tests/unit/` | Pure functions — no Neo4j |
| New integration test | `tests/integration/` | testcontainers-neo4j |
| Compliance logic | `engine/compliance/` | Never in chassis/ |
| Startup/shutdown | `engine/boot.py` GraphLifecycle | — |
