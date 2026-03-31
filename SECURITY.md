# Security Policy — Cognitive Engine Graphs (CEG)

## Scope

This policy covers the CEG engine (`engine/`), chassis (`chassis/`), domain specs (`domains/`), and all CI/CD infrastructure in this repository.

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ Active |
| Tagged releases | ✅ Per tag |
| Older feature branches | ❌ No |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Report privately via GitHub's [Security Advisories](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/security/advisories/new) or email the maintainer directly.

Include:
- Description of the vulnerability and affected component
- Reproduction steps or proof-of-concept
- Potential impact assessment
- Suggested remediation (optional)

**Response SLA:** Acknowledgement within 48 hours. Patch or mitigation within 14 days for critical issues.

## Security Model

### Critical Boundaries
- All Cypher label interpolation MUST use `sanitize_label()` — raw label injection is a critical vulnerability
- All Neo4j queries MUST route through `engine/graph/driver.py` — raw session access bypasses circuit breakers and audit logging
- PII values MUST NOT appear in logs — structlog filters are enforced by chassis
- Domain specs are **untrusted input** — validate all fields before loading
- KGE embeddings MUST NOT be shared cross-tenant

### Secrets
- Never commit `.env`, API keys, or credentials — `.gitleaks.toml` scans every commit
- Use `.env.template` for documenting required vars; populate via environment or secrets manager (AWS Secrets Manager / Hetzner env injection)

### Agent & AI Code Review
- All AI-generated code that touches `engine/`, `contracts/`, or `domains/` requires human review before merge
- `CODEOWNERS` enforces mandatory review on governance files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`)

## Dependency Management
- Dependabot is configured for pip and GitHub Actions (`.github/dependabot.yml`)
- Run `make audit` to check for known CVEs in current dependencies
- Lock file (`poetry.lock`) must be committed and kept current
