<!-- L9_TEMPLATE: true -->
# L9 Audit Harness — What It Does (and Doesn't)

The audit harness (`tools/audit_harness.py`) is the **single entrypoint** for all
static analysis. It orchestrates three existing tools in sequence and produces a
consolidated report.

## Architecture

```
make harness
    └── tools/audit_harness.py
            ├── [1] tools/audit_engine.py      → artifacts/audit_report.md
            ├── [2] tools/spec_extract.py       → artifacts/coverage_report.md
            ├── [3] tools/verify_contracts.py   → (stdout)
            └── [*] Consolidated               → artifacts/harness_report.md
```

## ✅ What It Does

| Capability | How | Example |
| :-- | :-- | :-- |
| **Banned pattern detection** | Walks every `.py` file via `pathlib.rglob()`, matches string/regex patterns per rule | Finds `from fastapi import APIRouter` in `engine/scoring/assembler.py` line 3 |
| **Forbidden structure checks** | Verifies directories/files that must NOT exist | Fails if `engine/api/` or `engine/middleware.py` reappears |
| **Required structure checks** | Verifies directories/files/tokens that MUST exist | Fails if `engine/handlers.py` is missing or doesn't contain `register_all` |
| **Cypher injection pattern detection** | Regex-scans f-strings for label interpolation without `sanitize_label()` | Flags `f"MERGE (n:{spec.target_node} ...)"` with evidence snippet |
| **Lifecycle anchor verification** | Checks that match/sync/GDS flows reference expected components | Warns if `GateCompiler`, `TraversalAssembler`, `ScoringAssembler` aren't referenced in handler chain |
| **Spec coverage scanning** | Extracts features from spec YAML, scans codebase for implementation evidence | Reports which gates, scoring types, ontology nodes are IMPLEMENTED / PARTIAL / MISSING |
| **Contract wiring verification** | Checks all 20 contract docs exist and are referenced in `.cursorrules` / `CLAUDE.md` | Fails if `FIELD_NAMES.md` exists but isn't wired into agent rules |
| **Evidence-based output** | Every finding includes file path + line range + 7-line code snippet | You see the exact code, not a vague description |
| **Severity-gated CI exit codes** | Returns exit code 1 if CRITICAL or HIGH findings exist | CI blocks merge; `make harness` fails locally |
| **Consolidated report** | Writes `artifacts/harness_report.md` combining all step results | Single doc for PR review |

## ❌ What It Does NOT Do

| Limitation | Why | What Covers It Instead |
| :-- | :-- | :-- |
| **Does not execute your code** | Pure static analysis — never imports, runs, or starts services | `pytest`, `make test` |
| **Does not validate Cypher syntax** | Can't parse Cypher grammar — only detects f-string interpolation patterns | Integration tests with real Neo4j (`testcontainers`) |
| **Does not test runtime behavior** | Can't verify `handle_match` returns correct candidates or scores | Unit tests (gate math), integration tests (full pipeline) |
| **Does not check Neo4j connectivity** | No database interaction whatsoever | `make dev` + `scripts/health.sh` |
| **Does not do type checking** | That's a different analysis pass entirely | `mypy --strict` (runs in CI separately) |
| **Does not validate domain spec semantics** | Can check YAML loads, but can't verify gates reference valid ontology properties | Pydantic validators in `engine/config/schema.py` + integration tests |
| **Does not format code** | Not a formatter | `ruff format .` |
| **Does not replace code review** | Catches mechanical violations, not design mistakes | CodeRabbit + human review |

## When to Run It

| Trigger | How | Why |
| :-- | :-- | :-- |
| **Before every commit** | `make harness` locally | Catch violations before they hit remote |
| **On every PR** (automated) | `.github/workflows/audit.yml` | Gate: blocks merge if CRITICAL/HIGH |
| **After scaffolding a new engine** | `make harness` on fresh clone | Verify template compliance before writing domain code |
| **After any refactor** | `make harness` | Catch regressions (e.g., someone re-adds FastAPI imports) |
| **When debugging agent drift** | Read `artifacts/harness_report.md` | Shows exactly what an agent broke and where |

## When NOT to Run It

- **Not for "does my code work?"** — that's tests
- **Not for "is my Cypher correct?"** — that's integration tests against Neo4j
- **Not for "is my domain spec valid?"** — that's Pydantic schema validation

## CLI Flags

```bash
# Default: blocks on CRITICAL/HIGH arch findings only
python tools/audit_harness.py

# Strict: also blocks if spec features are MISSING
python tools/audit_harness.py --strict

# Skip contract check (useful for early dev)
python tools/audit_harness.py --skip-contracts

# JSON output for CI integration
python tools/audit_harness.py --json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed |
| 1 | CRITICAL/HIGH findings, or contract failures |
| 2 | Infrastructure error (missing tool, bad YAML) |
