<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [audit, harness]
owner: engine-team
status: active
/L9_META -->

# L9 Audit Harness & Spec Coverage Extractor

Run **`make audit`** for full architecture compliance + spec coverage. Reports go to `artifacts/`.

---

## What the Audit Harness Does (and Doesn't)

### ✅ What It Does

| Capability | How | Example |
| :-- | :-- | :-- |
| **Banned pattern detection** | Walks every `.py` file via `pathlib.rglob()`, matches string/regex patterns per rule | Finds `from fastapi import APIRouter` in `engine/scoring/assembler.py` line 3 |
| **Forbidden structure checks** | Verifies directories/files that must NOT exist | Fails if `engine/api/` or `engine/middleware.py` reappears |
| **Required structure checks** | Verifies directories/files/tokens that MUST exist | Fails if `engine/handlers.py` is missing or doesn't contain `register_all` |
| **Cypher injection pattern detection** | Regex-scans f-strings for label interpolation without `sanitize_label()` | Flags `f"MERGE (n:{spec.target_node} ...)"` with evidence snippet |
| **Lifecycle anchor verification** | Checks that match/sync/GDS flows reference expected components | Warns if `GateCompiler`, `TraversalAssembler`, `ScoringAssembler` aren't referenced in handler chain |
| **Evidence-based output** | Every finding includes file path + line range + 7-line code snippet | You see the exact code, not a vague description |
| **Severity-gated CI exit codes** | Returns exit code 1 if CRITICAL or HIGH findings exist | CI blocks merge; `make audit` fails locally |
| **Markdown report generation** | Writes `artifacts/audit_report.md` with grouped findings | Attach to PR, review with team, or feed back to Cursor |

### ❌ What It Does NOT Do

| Limitation | Why | What Covers It Instead |
| :-- | :-- | :-- |
| **Does not execute your code** | It's pure static analysis — never imports, never runs, never starts services | `pytest`, `make test` |
| **Does not validate Cypher syntax** | Can't parse Cypher grammar — only detects f-string interpolation patterns | Integration tests with real Neo4j (`testcontainers`) |
| **Does not test runtime behavior** | Can't verify `handle_match` returns correct candidates or scores | Unit tests (gate math), integration tests (full pipeline) |
| **Does not check Neo4j connectivity** | No database interaction whatsoever | `make dev` + `scripts/health.sh` |
| **Does not do type checking** | That's a different analysis pass entirely | `mypy --strict` (runs in CI separately) |
| **Does not validate domain spec semantics** | Can check YAML loads, but can't verify gates reference valid ontology properties | Pydantic validators in `engine/config/schema.py` + integration tests |
| **Does not format code** | Not a formatter | `ruff format .` |
| **Does not replace code review** | Catches mechanical violations, not design mistakes | CodeRabbit + human review |

### When to Run It

| Trigger | How | Why |
| :-- | :-- | :-- |
| **Before every commit** | `make audit` locally | Catch violations before they hit remote |
| **On every PR** (automated) | `.github/workflows/audit.yml` | Gate: blocks merge if CRITICAL/HIGH |
| **After scaffolding a new engine** | `make audit` on fresh clone | Verify template compliance before writing domain code |
| **After any refactor** | `make audit` | Catch regressions (e.g., someone re-adds FastAPI imports) |
| **When debugging agent drift** | Read `artifacts/audit_report.md` | Shows exactly what an agent broke and where |

### When NOT to Run It

- **Not for "does my code work?"** — that's tests
- **Not for "is my Cypher correct?"** — that's integration tests against Neo4j
- **Not for "is my domain spec valid?"** — that's Pydantic schema validation (though the spec extractor adds partial coverage)

---

## The Spec Coverage Extractor: `tools/spec_extract.py`

This is the second half of the harness. It reads your `graph-cognitive-engine-spec-v1.1.0.yaml` and generates a structured checklist, then scans your code to produce a **coverage matrix** showing IMPLEMENTED / PARTIAL / MISSING for every spec feature.

### Usage

```bash
python tools/spec_extract.py                          # default spec path
python tools/spec_extract.py --spec path/to/spec.yaml # custom spec path
python tools/spec_extract.py --fail-on MISSING        # exit 1 if any MISSING
```

### Outputs

- `artifacts/spec_checklist.json` — extracted features from spec
- `artifacts/coverage_matrix.json` — IMPLEMENTED / PARTIAL / MISSING per feature
- `artifacts/coverage_report.md` — human-readable markdown report

---

## How the Two Tools Work Together

```
make audit
  │
  ├─→ tools/audit_engine.py          (architecture compliance)
  │     ├─ Reads: tools/audit_rules.yaml
  │     ├─ Scans: engine/**/*.py
  │     ├─ Checks: banned imports, forbidden dirs, Cypher injection patterns
  │     └─ Writes: artifacts/audit_report.md
  │
  └─→ tools/spec_extract.py          (spec feature coverage)
        ├─ Reads: graph-cognitive-engine-spec-v1.1.0.yaml
        ├─ Extracts: gates, scoring, ontology, v1.1 additions, actions, GDS
        ├─ Scans: engine/**/*.py + domains/**/*.yaml
        └─ Writes: artifacts/coverage_report.md
                   artifacts/coverage_matrix.json
                   artifacts/spec_checklist.json
```

**`audit_engine.py`** answers: *"Does this repo comply with L9 architecture rules?"*

**`spec_extract.py`** answers: *"Does this repo implement everything the spec requires?"*

Together they produce a complete picture. The architecture audit catches structural violations (wrong imports, missing handlers, injection risks). The spec coverage catches functional gaps (missing gate types, unimplemented scoring dimensions, absent v1.1 nodes).

---

## Makefile Targets

| Target | Command | Purpose |
|--------|---------|---------|
| `audit` | `make audit` | Run full architecture audit + spec coverage |
| `audit-strict` | `make audit-strict` | Audit with strict failure (blocks on MISSING spec features) |
| `coverage` | `make coverage` | Spec coverage matrix only (no architecture audit) |

---

## CI Integration

The `.github/workflows/audit.yml` workflow runs both tools on every PR and push to main:

1. Architecture audit (`python tools/audit_engine.py`)
2. Spec coverage (`python tools/spec_extract.py --fail-on NONE`)
3. Upload reports to artifacts

Use `--fail-on MISSING` when you're ready to enforce full spec coverage (CI will block merge if any feature is MISSING). Use `--fail-on NONE` during active development so you can see the matrix without blocking. When all features are IMPLEMENTED or PARTIAL, switch to `--fail-on MISSING` to gate merges on spec coverage.
