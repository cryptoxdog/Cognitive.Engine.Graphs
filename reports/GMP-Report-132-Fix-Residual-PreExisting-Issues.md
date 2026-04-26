**ID:** GMP-132 | **Task:** Fix Residual Pre-existing Issues (T3: Engine + Tests) | **Tier:** RUNTIME_TIER | **Date:** 2026-04-26 | **Status:** ✅ COMPLETE

---

## TODO PLAN

| # | TODO | File | Action |
|---|------|------|--------|
| TODO-1 | Fix `GateType` import and `_compile_single` mismatch | `tests/unit/test_gate_compiler.py` | Rewrite 3 of 4 tests |
| TODO-2 | Fix `allowed_canonical_labels` + wrong API shapes | `tests/integration/test_handlers.py` | Full rewrite (8 new tests) |
| TODO-3 | Fix `sanitize_label` missing max-length guard | `engine/utils/security.py` | Add `_MAX_LABEL_LEN = 64` check |

**Scope boundaries:** Only the 3 files above. No other engine or test files modified.

---

## PHASES

### Phase 0 — PLAN
Investigated each failure:
- TODO-1: `GateType` lives in `engine.config.schema`, not `engine.gates.types.all_gates`. `GateType.exact` doesn't exist (closest is `BOOLEAN`). `GateCompiler._compile_single` doesn't exist (real API: `compiler._compile_boolean(gate)`). `GateSpec` field names are `candidateprop`/`queryparam`, not `field`/`query_param`.
- TODO-2: `DomainPackLoader.allowed_canonical_labels()` never existed. `GraphDriver()` constructor takes `(uri, username, password)`, not a label list. All handler payloads and assertions were for a different, removed API version.
- TODO-3: `sanitize_label` regex `^[A-Za-z_][A-Za-z0-9_]*$` allows unlimited length — `"A" * 200` passes silently. Contract 9 requires injection prevention; unbounded labels are a risk vector.

### Phase 1 — BASELINE
- Pre-fix: `test_gate_compiler.py` — 4 collected, 3 failing (`ImportError: cannot import name 'GateType' from 'engine.gates.types.all_gates'`)
- Pre-fix: `test_handlers.py` — 3 collected, 1 failing (`AttributeError: 'DomainPackLoader' object has no attribute 'allowed_canonical_labels'`)
- Pre-fix: `test_cypher_utils.py` — 6 collected, 1 failing (`DID NOT RAISE any of (<class 'ValueError'>, <class 'Exception'>)`)
- `test_sync_handler.py::test_sync_unknown_entity_type_raises` — pre-existing failure (plasticos spec schema mismatch, confirmed identical before and after our changes)

### Phase 2 — IMPLEMENT

**TODO-1 — `tests/unit/test_gate_compiler.py`:**
- All 4 tests rewritten to use `MagicMock()` spec with `GateCompiler(mock_spec)`
- Import fixed: `from engine.config.schema import GateSpec, GateType`
- `GateType.exact` → `GateType.BOOLEAN`
- `GateSpec(field=, query_param=)` → `GateSpec(candidateprop=, queryparam=)`
- `GateCompiler._compile_single(gate, direction)` → `compiler._compile_boolean(gate)` and `compiler._wrap_null_semantics(gate, predicate)`
- `test_direction_filter_skips_non_matching` uses `compile_all_gates(match_direction=)` with direction filter
- `test_compile_all_gates_empty_returns_empty` uses empty MagicMock spec instead of broken `plasticos` load

**TODO-2 — `tests/integration/test_handlers.py`:**
- Full rewrite: 8 tests replacing 3 broken ones
- Uses `MagicMock(spec=GraphDriver)` with `AsyncMock` for `execute_query`
- Uses `MagicMock(spec=DomainPackLoader)` with `.load_domain()` / `.list_domains()` stubbed
- `_reset_state()` helper clears `EngineState` singleton between tests
- `_make_mock_spec()` produces a minimal DomainSpec mock with all required boolean flags
- Correct handler payload shapes: `{"entity_type": ..., "batch": [...]}` for sync, `{"query": ..., "match_direction": ...}` for match, `{"subaction": ...}` for admin
- Tests validate actual response shapes from current handlers

**TODO-3 — `engine/utils/security.py`:**
- Added `_MAX_LABEL_LEN = 64` module constant
- Length check raises `ValueError` (via named `msg` variable per EM101 convention) before regex check
- Docstring updated to document the 64-char limit

### Phase 3 — ENFORCE
- `ruff check --fix` applied to all 3 files: 4 fixable errors resolved (import sort, unused `pytest` import)
- `ruff format` applied: 1 file reformatted

### Phase 4 — VALIDATE

```
tests/unit/test_gate_compiler.py   ....  4 passed
tests/unit/test_cypher_utils.py    ......  6 passed
tests/integration/test_handlers.py ........  8 passed
Full unit suite (-m unit):         674 passed, 1 skipped, 0 failed
```

Pre-existing failure `test_sync_handler.py::test_sync_unknown_entity_type_raises` confirmed identical before and after (stash test: same plasticos schema mismatch, unrelated to this GMP).

---

## CHANGES

| File | Type | Lines Changed | What |
|------|------|--------------|------|
| `engine/utils/security.py` | ENGINE | +7 / -3 | `_MAX_LABEL_LEN = 64` constant + pre-check in `sanitize_label` |
| `tests/unit/test_gate_compiler.py` | TEST | full rewrite | Correct imports, enum values, method names, GateSpec field names |
| `tests/integration/test_handlers.py` | TEST | full rewrite | 8 mock-based handler tests replacing 3 broken API-mismatch tests |

---

## TODO → CHANGE MAP

| TODO | File Changed | Lines | Description |
|------|-------------|-------|-------------|
| TODO-1 | `tests/unit/test_gate_compiler.py` | all | GateType import → schema, BOOLEAN gate, _compile_boolean API |
| TODO-2 | `tests/integration/test_handlers.py` | all | Rewrite with AsyncMock, correct handler payloads + assertions |
| TODO-3 | `engine/utils/security.py` | 21-34 | _MAX_LABEL_LEN guard in sanitize_label |

---

## VALIDATION

- [x] `test_gate_compiler.py` — 4/4 pass (was 1/4)
- [x] `test_cypher_utils.py` — 6/6 pass (was 5/6)
- [x] `test_handlers.py` — 8/8 pass (was 2/3)
- [x] Full unit suite — 674 pass, 0 fail (no regressions)
- [x] `ruff check` — 0 errors on all 3 modified files
- [x] `ruff format` — all 3 files formatted
- [x] Pre-existing `test_sync_handler` failure: identical before/after (out of scope)

---

## VERIFICATION

Phase 5 recursive check — scope invariants:

- No FastAPI/Starlette/uvicorn imports introduced ✅
- No new top-level directories created ✅
- `sanitize_label` still raises `ValueError` for all existing invalid inputs ✅
- `sanitize_label` now also raises for labels > 64 chars ✅
- `GateCompiler` engine source unchanged ✅
- `DomainPackLoader` engine source unchanged ✅
- `GraphDriver` engine source unchanged ✅
- Handler signatures unchanged ✅

---

## DECLARATION

GMP-132 is **COMPLETE**. All 3 residual pre-existing issues from GMP-131 are resolved:

1. **`test_gate_compiler.py`** — collection error eliminated; 4/4 tests pass using correct engine API
2. **`test_handlers.py`** — `allowed_canonical_labels` AttributeError eliminated; 8/8 tests pass using mock-based handler tests with correct payload shapes
3. **`test_sanitize_label_rejects_too_long`** — logic failure fixed; 6/6 `test_cypher_utils.py` tests pass; `sanitize_label` now enforces 64-char max length per security contract

No engine handler logic was changed. No regressions introduced. Contract 9 (Cypher injection prevention) is now stronger.
