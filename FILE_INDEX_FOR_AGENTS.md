<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [navigation]
tags: [file-index, agent-navigation, lookup]
owner: platform
status: active
/L9_META -->

# FILE_INDEX_FOR_AGENTS.md — Quick File Lookup

**Purpose**: Fast lookup index for agents to find files by category with token estimates and load triggers.

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Agent Governance Files

| File | Tokens | Load When | Purpose |
|------|--------|-----------|---------|
| AGENT_BOOTSTRAP.md | ~800 | First session | Onboarding entrypoint, reading order |
| GUARDRAILS.md | ~1,100 | Every session (TIER 1) | Mandatory safety rules, autonomy limits |
| AGENTS.md (live) | ~1,400 | Every session (TIER 1) | Universal agent instructions |
| CLAUDE.md (live) | ~1,200 | Claude sessions only | Claude-specific examples and .claude/rules delegation |
| ARCHITECTURE.md (live) | ~1,600 | Working in engine/ or chassis/ | System structure, request flow |
| TESTING.md (live) | ~1,800 | Writing/reviewing tests | Test structure, coverage thresholds |
| FEATURE_FLAGS.md | ~800 | Adding new behavior | All 20+ feature flags |
| TROUBLESHOOTING.md | ~1,500 | Debugging errors | Common issues and resolutions |

## Generated Documentation (Reference Only)

| File | Tokens | Load When | Purpose |
|------|--------|-----------|---------|
| INVARIANTS.md | ~3,200 | Contract uncertainty | 24 contracts (C-001 to C-024) |
| EXECUTION_FLOWS.md | ~2,100 | Understanding runtime | Request flow, CI pipeline, error flows |
| CONFIG_ENV_CONTRACT.md | ~1,800 | Env var lookup | Environment variables, feature flags |
| DEPENDENCY_SURFACE.md | ~600 | Dependency questions | Runtime and dev dependencies |
| CI_WHITELIST_REGISTER.md | ~1,600 | CI failure diagnosis | Non-blocking checks, waivers |
| FILE_INDEX_FOR_AGENTS.md | ~400 | File location lookup | This file |

## Live Repository Files (Source of Truth)

| File | Tokens (est.) | Load When | Purpose |
|------|---------------|-----------|---------|
| .cursorrules | ~8,200 | Cursor sessions (TIER 1-5) | Cursor bootstrap, 20-contract summary |
| .claude/rules/contracts.md | ~600 | Contract lookup | 24 contracts tabular reference |
| .claude/rules/feature-flags.md | ~400 | Feature flag lookup | Settings.py flags with defaults |
| .claude/rules/capability-registry.md | Unknown | Before building capability | 18 existing capabilities |
| .claude/rules/subsystems.md | Unknown | Subsystem navigation | Directory structure, handler registry |
| .claude/rules/routing.md | Unknown | Where to put code | Exhaustive routing rules |
| .claude/rules/system-state.md | Unknown | PR status check | Open PRs, dormant subsystems |

## Configuration Files

| File | Purpose | Agent Action |
|------|---------|--------------|
| pyproject.toml | Tool config, dependencies, coverage thresholds | Reference for ruff/mypy/pytest config |
| .github/workflows/ci.yml | CI pipeline definition | Reference for CI failure diagnosis |
| .pre-commit-config.yaml | Pre-commit hooks | Reference for hook exclusions |
| .env.template | Required env vars with placeholders | Copy to .env, populate values |
| .gitleaksignore | Gitleaks secret scan exceptions | Reference for secret scan failures |
| .gitleaks.toml | Gitleaks custom rules | Reference for secret detection rules |

## Contract Documentation

| File | Purpose | Load When |
|------|---------|-----------|
| docs/contracts/FIELD_NAMES.md | Naming conventions | Before touching schema |
| docs/contracts/CYPHER_SAFETY.md | Cypher injection prevention | Before writing Cypher |
| docs/contracts/BANNED_PATTERNS.md | Forbidden code patterns | Before writing engine code |
| docs/contracts/PYDANTIC_YAML_MAPPING.md | YAML ↔ Pydantic mapping | Before modifying DomainSpec |
| docs/contracts/HANDLER_PAYLOADS.md | Handler input/output contracts | Before modifying handlers |
| docs/contracts/METHOD_SIGNATURES.md | Function signature rules | Before adding public methods |
| docs/contracts/DEPENDENCY_INJECTION.md | DI patterns | Before using Depends() |
| docs/contracts/RETURN_VALUES.md | Return type conventions | Before writing handlers |
| docs/contracts/PACKET_ENVELOPE_FIELDS.md | PacketEnvelope schema | Before touching packet/ |
| docs/contracts/SHARED_MODELS.md | Cross-service data models | Before redefining shared types |
| docs/contracts/DELEGATION_PROTOCOL.md | Inter-service calling patterns | Before using httpx in engine |
| docs/contracts/PACKET_TYPE_REGISTRY.md | Registered packet types | Before adding packet_type |
| docs/contracts/TEST_PATTERNS.md | Test writing conventions | Before writing tests |
| docs/contracts/ERROR_HANDLING.md | Exception handling rules | Before adding try/except |
| docs/contracts/OBSERVABILITY.md | Logging and metrics rules | Before adding logs |
| docs/contracts/MEMORY_SUBSTRATE_ACCESS.md | Memory DB access patterns | Before querying memory substrate |
| docs/contracts/DOMAIN_SPEC_VERSIONING.md | Domain spec migration rules | Before changing spec schema |
| docs/contracts/FEEDBACK_LOOPS.md | Outcome recording patterns | Before implementing feedback |
| docs/contracts/NODE_REGISTRATION.md | Service registry patterns | Before registering new service |
| docs/contracts/ENV_VARS.md | Environment variable naming | Before adding env vars |

**Total**: 20 contract files in `docs/contracts/`

---

## File Modification Rules

### NEVER Modify
- `.cursorrules` (Cursor bootstrap protocol — Founder only)
- `.github/workflows/ci.yml` (CI pipeline — platform team only)
- `pyproject.toml` [build-system] section (Poetry config — platform team only)
- `PacketEnvelope`, `TenantContext`, `ExecuteRequest` class definitions (shared models — violates C-007)
- Any file in `l9-template/` subdirectory (template inheritance — violates C-005)

### Always Ask Before Modifying
- `engine/config/schema.py` (affects all domain specs)
- `engine/handlers.py` (handler signature changes)
- `engine/boot.py` (startup/shutdown lifecycle)
- Creating new top-level directories under `engine/` (violates C-016)
- `.claude/rules/*.md` (Claude governance — ask Founder)

### Safe to Modify (With Tests)
- `engine/gates/types/*.py` (gate implementations)
- `engine/scoring/*.py` (scoring dimensions)
- `engine/traversal/*.py` (traversal logic)
- `engine/sync/*.py` (sync generators)
- `tests/**/*.py` (test files)
- `domains/*.yaml` (domain specs, with validation)
- `docs/contracts/*.md` (contract documentation improvements)

---

## Quick Lookups

**Q**: Where is the handler registration code?  
**A**: `engine/handlers.py::register_all()`

**Q**: Where are gate types defined?  
**A**: `engine/gates/types/` (10 gate type implementations)

**Q**: Where is Cypher sanitization?  
**A**: `engine/utils/security.py::sanitize_label()`

**Q**: Where are feature flags defined?  
**A**: `engine/config/settings.py::Settings` class

**Q**: Where is the contract scanner?  
**A**: `tools/contract_scanner.py`

**Q**: Where are pre-commit hooks configured?  
**A**: `.pre-commit-config.yaml`

**Q**: Where is CI configured?  
**A**: `.github/workflows/ci.yml`

**Q**: Where are domain specs loaded?  
**A**: `engine/config/loader.py::DomainPackLoader`

**Q**: Where is the PacketEnvelope defined?  
**A**: `engine/packet/packet_envelope.py` (shared model, NEVER redefine)

**Q**: Where are prohibited factors enforced?  
**A**: `engine/compliance/prohibited_factors.py` + `tests/compliance/`

---

## Bootstrap Reading Order for New Agents

1. AGENT_BOOTSTRAP.md (this reading order)
2. GUARDRAILS.md (safety rules)
3. AGENTS.md (universal instructions)
4. ARCHITECTURE.md (system structure)
5. .claude/rules/contracts.md (24 contracts quick reference)
6. Subsystem-specific files as needed

**Total TIER 1 load**: ~2,500 tokens (8% of 32K context window)

---

## Missing Files (Known Gaps)

- `.claude/rules/capability-registry.md` exists but token estimate unknown
- `.claude/rules/subsystems.md` exists but token estimate unknown
- `.claude/rules/routing.md` exists but token estimate unknown
- `.claude/rules/system-state.md` exists but token estimate unknown
- `docs/contracts/` — 20 files listed, not all verified to exist

**Agent Action**: If a referenced file is missing, report to Founder. Do not invent contents.

---

## Related Documents

- **AGENT_BOOTSTRAP.md** — Source for TIER 1-5 loading order
- **ARCHITECTURE.md** — Source for directory structure
- **GUARDRAILS.md** — Source for file modification safety rules
