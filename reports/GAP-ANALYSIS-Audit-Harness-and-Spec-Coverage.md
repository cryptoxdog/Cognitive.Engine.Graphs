# GAP ANALYSIS: Audit Harness & Spec Coverage

**Scope:** Audit harness explanation, spec coverage extractor, and “what the harness does / doesn’t do” (from `current work/yes that sounds like the logical next step - i ena.md`).  
**Date:** 2026-03-02  
**Status:** Gaps 1 and 2 closed (0 MISSING; harness doc complete in repo).

---

## Target state (from doc)

| Dimension | Target |
|-----------|--------|
| **Harness explanation** | Clear doc: what it does, what it doesn’t, when/how to use it |
| **Spec coverage extractor** | `tools/spec_extract.py` exists, runs, produces IMPLEMENTED/PARTIAL/MISSING |
| **Integration** | `audit_engine.py` calls spec_extract; Makefile has `audit`, `audit-strict`, `coverage`; CI runs both |
| **Manifest** | `tools/l9_template_manifest.yaml` includes `spec_extract.py` |
| **Spec coverage** | All spec features IMPLEMENTED (or at least 0 MISSING) |
| **Docs** | Full “harness + spec extractor” explanation available in repo for team/Cursor |

---

## Current vs target

| Dimension | Current | Target | Gap |
|-----------|---------|--------|-----|
| **Harness behavior** | `audit_engine.py` + `spec_extract.py` present; `make audit` runs both | Same | None |
| **Harness explanation** | `docs/Audit Harness-Explained.md` has “what it does/doesn’t” and “when to run” | Full explanation in repo | Doc in repo is abbreviated; full version only in `current work/` |
| **Spec extractor** | `tools/spec_extract.py` exists; manifest + Makefile + CI wired | Same | None |
| **Spec coverage results** | 27 implemented, 9 partial, **0 missing** (of 36) | 0 MISSING | **Closed** — enrich/healthcheck handlers present |
| **CI strictness** | `audit.yml` uses `--fail-on NONE` | Optional: `--fail-on MISSING` when ready | Optional gap |
| **Pre-commit** | Contract scanner + verify_contracts run on commit | Doc suggests “make audit” before commit | Optional: no `make audit` in pre-commit |

---

## Gaps (prioritized)

| # | Gap | Priority | Impact | Effort | Fix |
|---|-----|----------|--------|--------|-----|
| 1 | ~~2 MISSING spec features~~ | **CLOSED** | Spec coverage gate can’t be strict; `make audit-strict` fails | Medium | Add `handle_enrich` and `handle_healthcheck` (or register stubs) in `engine/handlers.py`; or adjust spec_extract search tokens so existing wiring counts as IMPLEMENTED. |
| 2 | ~~Full harness doc not in repo~~ | **CLOSED** | Team/Cursor see abbreviated “what it does”; full “two tools together”, “when/how”, and spec_extract description live only in `current work/` | Low | Copy or merge the full explanation from `current work/yes that sounds like...md` into `docs/Audit Harness-Explained.md` (or add `docs/Audit-Harness-and-Spec-Coverage.md`). |
| 3 | **7 PARTIAL features** | Medium | Spec matrix shows partial for v1.1 actions, outcome_weighted, and some action_handler hits (single file) | Low–Medium | Either implement to 2+ evidence files per feature, or relax spec_extract “IMPLEMENTED” rule (e.g. 1 file = IMPLEMENTED for handlers). |
| 4 | **CI uses --fail-on NONE** | Low | Merge not blocked by MISSING spec features | Trivial | When ready: in `.github/workflows/audit.yml`, change spec_extract to `--fail-on MISSING`. |
| 5 | **No pre-commit for make audit** | Low | Developers can commit without running full audit | Low | Add a pre-commit local hook that runs `make audit` (or only `audit_engine.py` + `spec_extract.py`); consider time cost. |

---

## Effort estimate

| Category | Count | Effort |
|----------|--------|--------|
| Close 2 MISSING (handlers or spec logic) | 1 | Medium |
| Full harness doc in repo | 1 | Low |
| Reduce PARTIAL (optional) | 1 | Low–Medium |
| CI strict + pre-commit (optional) | 2 | Low |

**Total gaps:** 5 (2 high/medium impact, 3 optional).  
**Rough effort:** ~0.5–1 day to close MISSING + doc; optional items as needed.

---

## Recommended next steps (GMP / YNP)

| Step | Scope | Gaps addressed |
|------|--------|-----------------|
| **GMP: Close MISSING** | Add or wire `handle_enrich` and `handle_healthcheck` (or equivalent) so spec_extract reports 0 MISSING; then optionally set CI to `--fail-on MISSING`. | #1, optionally #4 |
| **Quick doc update** | Merge full “what it does / doesn’t / when/how” and “two tools together” into `docs/Audit Harness-Explained.md` (or new doc). | #2 |
| **Optional** | Add pre-commit hook for `make audit`; tune spec_extract or implementation for PARTIALs. | #3, #5 |

---

## Summary

- **Harness and spec extractor:** Implemented and wired (audit_engine, Makefile, CI, manifest).  
- **Gaps 1 and 2 closed:** 0 MISSING (enrich/healthcheck handlers present); harness doc complete in `docs/Audit Harness-Explained.md`.  
- **Remaining (optional):** CI `--fail-on MISSING`, pre-commit for `make audit`, reduce PARTIALs if desired.

---

*Gap analysis | 2026-03-02 | Auto-chains to /ynp*
