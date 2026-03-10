# {{PROJECT_NAME}} Repository Style Guide for AI Code Assist

> Copy this template into your repo and fill in the `{{...}}` sections.
> Universal rules (Python style, security, testing) are pre-filled.

---

## Project Overview

{{PROJECT_DESCRIPTION — 2-3 sentences describing your system architecture}}

## Protected Files — DO NOT MODIFY

<!-- List files that require explicit approval before changes -->

{{PROTECTED_FILES — e.g.:
- `core/kernel_loader.py` — Kernel initialization
- `docker-compose.yml` — Infrastructure configuration
- `core/schemas/packet_envelope.py` — Protocol definitions
}}

---

## Code Quality Standards

### Python Style (Universal)

- **Type hints:** Required on all public functions/methods
- **Docstrings:** Google style with Args/Returns/Raises
- **Error handling:** No bare `except`; always specify exception types
- **Async patterns:** Use `async`/`await` for IO operations
- **Imports:** Absolute imports from project root (`from core.schemas import ...`)

### Project Architectural Patterns

{{ARCHITECTURAL_PATTERNS — describe your key patterns, e.g.:
- **Inter-component messaging:** All communication uses PacketEnvelope protocol
- **Data access:** Never write to databases directly; use the substrate service layer
- **Authorization:** All tool executions must pass governance checks before running
}}

### Production Readiness (Universal)

- No TODOs/FIXMEs: Remove or convert to GitHub issues
- No placeholders: Implement complete logic or raise `NotImplementedError` with issue link
- No print statements: Use structured logging (`logger.info/warning/error`)
- Environment variables: Always provide defaults or fail-fast validation

---

## Security Requirements (Universal)

- **Input validation:** Sanitize all external inputs (API, WebSocket, file uploads)
- **Secret management:** Never hardcode API keys — use environment variables
- **SQL injection:** Use parameterized queries (SQLAlchemy/asyncpg)
- **Path traversal:** Validate file paths against allowed directories

---

## Testing Expectations (Universal)

- **Critical paths:** Add tests for auth checks, data operations, message routing
- **Edge cases:** Test error conditions, malformed inputs, boundary values
- **Async tests:** Use `pytest-asyncio` with proper fixtures

---

## Performance Considerations (Universal)

- **Async IO:** Database/API calls should be async
- **Caching:** Use Redis (or equivalent) for frequently accessed data
- **Batch operations:** Prefer bulk inserts/updates over loops
- **Connection pooling:** Reuse DB connections

---

## Review Priorities (Ordered by Impact)

{{REVIEW_PRIORITIES — ordered list for your project, e.g.:
1. Authorization violations (bypassing approval checks)
2. Data layer misuse (direct DB writes bypassing service layer)
3. Protected file modifications
4. Security issues (injection, secrets exposure)
5. Type safety (missing type hints)
6. Documentation (missing docstrings)
7. Code style (formatting, naming conventions)
}}

---

## Common Anti-Patterns to Flag

{{ANTI_PATTERNS — project-specific bad practices, e.g.:
- Direct database access bypassing the service layer
- Synchronous blocking calls in async functions
- Hardcoded entity IDs (use registry lookups)
- Missing error handling for external API calls
}}

---

## Enhancement Opportunities

When reviewing code, suggest:
- **Performance:** Async patterns, caching opportunities, batch operations
- **Architecture:** Better separation of concerns, dependency injection
- **Observability:** Add metrics, tracing spans, structured logs
- **Resilience:** Retry logic, circuit breakers, graceful degradation
