<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [agent-onboarding]
tags: [agent-governance, bootstrap, onboarding]
owner: platform
status: active
/L9_META -->

# AGENT_BOOTSTRAP.md — CEG Agent Onboarding

**Purpose**: Single entrypoint for all AI agents (Cursor, Claude, Copilot, CodeRabbit, Qodo) joining the Cognitive.Engine.Graphs repository.

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Mandatory Reading Order

All agents MUST read the following files in exact order before generating or reviewing code:

### TIER 1: Safety & Boundaries (ALWAYS LOAD)
1. **GUARDRAILS.md** (~1,100 tokens)
   - Load when: Every session, before any code generation or review
   - Contains: 10 mandatory safety rules, agent autonomy limits, forbidden primitives
   - Critical sections: § Cypher Injection Prevention, § Engine/Chassis Boundary, § Agent Autonomy Limits

2. **AGENTS.md** (~1,400 tokens)  
   - Load when: Every session, after GUARDRAILS.md
   - Contains: Universal agent instructions, commands, git workflow, code style, boundary rules
   - Source: Live repository file (SHA: 51f44c5)

### TIER 2: Architecture Context (LOAD ON TRIGGER)
3. **ARCHITECTURE.md** (~1,600 tokens)
   - Load when: Working in engine/, chassis/, or handlers.py
   - Contains: System identity, directory map, request flow, feature flags, where-to-put-code guide
   - Source: Live repository file (SHA: 8635bd1)

4. **TESTING.md** (~1,800 tokens)
   - Load when: Writing or reviewing tests
   - Contains: Test structure, coverage thresholds, patterns, fixtures
   - Source: Live repository file (SHA: c9368d9)

5. **.claude/rules/contracts.md**
   - Load when: Adding/modifying behavioral contracts or uncertain about a contract rule
   - Contains: All 24 contracts (C-001 to C-024) in tabular format
   - Source: Live repository file (SHA: 1211d8e)

6. **FEATURE_FLAGS.md** (see this pack)
   - Load when: Adding new behavior or modifying conditional logic
   - Contains: All feature flags with defaults and purposes

### TIER 3: Subsystem-Specific (LOAD WHEN WORKING IN SUBSYSTEM)
7. **.claude/rules/capability-registry.md**
   - Load when: Building any new capability
   - Contains: 18 existing capabilities to avoid duplication

8. **Relevant contract file from docs/contracts/**
   - Load when: See `.cursorrules` TIER 5 for mapping of subsystem → contract files

### TIER 4: Reference Only (QUERY BY SECTION AS NEEDED)
9. **CONFIG_ENV_CONTRACT.md** — lookup specific env var
10. **DEPENDENCY_SURFACE.md** — lookup specific dependency version
11. **CI_WHITELIST_REGISTER.md** — lookup waiver justification
12. **FILE_INDEX_FOR_AGENTS.md** — file location lookup
13. **EXECUTION_FLOWS.md** — runtime flow diagrams

---

## Token Budget (32K Practical Limit)

| Load Tier | Total Tokens | % of 32K Budget | Remaining for Code |
|-----------|--------------|-----------------|-------------------|
| TIER 1 (always load) | ~2,500 | 8% | 29,500 |
| TIER 2 (typical session) | +3,000–5,000 | +9–16% | 24,500–26,500 |
| TIER 3 (subsystem work) | +1,000–2,000 | +3–6% | 22,500–25,500 |

**Strategy**: Never load all documentation at once. Use TIER system to stay under 10,000 tokens of governance context.

---

## Critical Facts (Verified Against Live Repo)

- **Contracts**: 24 total (C-001 to C-024), not 20
- **Scoring Computations**: 13 types, not 9
- **Action Handlers**: 8 (match, sync, admin, outcomes, resolve, health, healthcheck, enrich)
- **Gate Types**: 10
- **HTTP Entry Point**: `POST /v1/{tenant}/{action}` (not `/v1/execute`)
- **Feature Flags**: 20+ (see FEATURE_FLAGS.md)

---

## Unknown Handling Protocol

If a section in any documentation states "Unknown":
1. Do NOT infer or guess the unknown value
2. If the unknown is required for current task → STOP and report to Founder
3. If the unknown is NOT required → proceed and note the gap in commit message
4. Never write code that depends on an undocumented invariant

---

## Contradiction Escalation

If you encounter contradictory guidance between two documents:
1. Live repository files (AGENTS.md, ARCHITECTURE.md, GUARDRAILS.md, TESTING.md) take precedence over generated files
2. `.cursorrules` and `.claude/rules/` take precedence over generated documentation
3. If CI reports a contract violation not listed in your context → reference `docs/contracts/` or `.claude/rules/contracts.md`
4. Report contradiction to Founder; do not attempt to resolve autonomously

---

## Agent-Specific Notes

### Cursor
- Read `.cursorrules` TIER 1-2 files at session start
- Follow GMP (Grand Master Prompt) phases for PR workflow
- Consult `agents/cursor/cursor_workflow_kernel.yaml` for decision matrix

### Claude Code  
- Use `@AGENTS.md` delegation pattern from live CLAUDE.md
- Load `.claude/rules/*.md` files for subsystem-specific guidance

### GitHub Copilot
- Inline context: AGENTS.md only (~1,400 tokens)
- For complex tasks, escalate to Cursor or Claude

### CodeRabbit / Qodo (PR Review Agents)
- Load: GUARDRAILS.md + AGENTS.md + AI_AGENT_REVIEW_CHECKLIST.md (~5,000 tokens)
- Use checklist scoring rubric for APPROVE/REQUEST_CHANGES decisions

---

## First-Time Agent Setup

```bash
# 1. Verify you can access the repository
ls -la AGENTS.md GUARDRAILS.md ARCHITECTURE.md

# 2. Load TIER 1 files into context (GUARDRAILS.md, AGENTS.md)

# 3. Verify contract count
grep -c "^| [0-9]" .claude/rules/contracts.md
# Expected output: 24

# 4. Run local validation
make lint
make test-unit

# 5. You are ready to work
```

---

## Source of Truth Hierarchy

```
.cursorrules                   → Cursor-specific bootstrap and contract summary
.claude/rules/                 → Claude-specific subsystem routing
AGENTS.md (live)               → Universal agent instructions
GUARDRAILS.md                  → Safety rules and autonomy limits
ARCHITECTURE.md                → System structure
TESTING.md                     → Test patterns
pyproject.toml                 → Tool configuration
ci.yml                         → CI enforcement
docs/contracts/                → Detailed contract definitions
```

**Rule**: When in doubt, consult the file higher in this hierarchy.
