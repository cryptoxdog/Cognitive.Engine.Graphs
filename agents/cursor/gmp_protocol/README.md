# GMP Protocol v3.2.0 — L9 Canonical

**Version:** 3.2.0
**Updated:** 2026-01-18
**Status:** Production Ready

---

## Overview

This folder contains the **canonical GMP (Governance Managed Process) protocol** for the L9 Secure AI OS. All files use the **L9 canonical phase system (Phases 0-6)**.

## Phase System

| Phase | Name           | Purpose                            | Time      |
| ----- | -------------- | ---------------------------------- | --------- |
| 0     | PLANNING       | Lock TODO plan, establish scope    | 5-10 min  |
| 1     | BASELINE       | Verify assumptions, ground truth   | 2-5 min   |
| 2     | IMPLEMENTATION | Execute locked TODO plan           | 10-30 min |
| 3     | ENFORCEMENT    | Add guards, fail-fast, validation  | 10-20 min |
| 4     | VALIDATION     | Tests, edge cases, regression      | 10-15 min |
| 5     | RECURSION      | Verify no scope drift, invariants  | 5-10 min  |
| 6     | FINALIZATION   | Evidence report, final declaration | 5-10 min  |

## Files

### Core Templates

| File                                     | Purpose                                                                 |
| ---------------------------------------- | ----------------------------------------------------------------------- |
| `cursor-gmp-template.md`                 | Comprehensive GMP template with all phases, profiles, and report format |
| `cursor-gmp-template-quick-reference.md` | One-page quick reference for GMP execution                              |
| `cursor-gmp-canonical.md`                | Role definition and constraints for deterministic execution             |
| `cursor-gmp-runbook.md`                  | Step-by-step execution guide                                            |

### Phase Specifications

| File                               | Phase                   |
| ---------------------------------- | ----------------------- |
| `cursor-phase-0-planning.md`       | Phase 0: Planning       |
| `cursor-phase-1-baseline.md`       | Phase 1: Baseline       |
| `cursor-phase-2-implementation.md` | Phase 2: Implementation |
| `cursor-phase-3-enforcement.md`    | Phase 3: Enforcement    |
| `cursor-phase-4-validation.md`     | Phase 4: Validation     |
| `cursor-phase-5-recursion.md`      | Phase 5: Recursion      |
| `cursor-phase-6-finalization.md`   | Phase 6: Finalization   |

### Enforcement

| File                       | Purpose                           |
| -------------------------- | --------------------------------- |
| `gmp-contract.yaml`        | Contract for GMP phase execution  |
| `gmp-report-contract.yaml` | Contract for GMP report structure |
| `gmp-report-template.md`   | Canonical report template         |

## Report Naming Convention

```
GMP-Report-{ID}-{Description}.md

Examples:
  GMP-Report-074-Retention-Engine.md
  GMP-Report-095-Fail-Closed-Enforcement.md
```

## Usage

### Starting a GMP Run

1. Load `cursor-gmp-template.md` or the relevant phase file
2. Follow the phase system in order (0 → 6)
3. Use `gmp-contract.yaml` for programmatic enforcement
4. Generate evidence report in Phase 6

### Quick Reference

For rapid execution, use `cursor-gmp-template-quick-reference.md`.

### Contract Enforcement

The `gmp-contract.yaml` file defines:

- Phase definitions with inputs/outputs
- Checklist items for each phase
- Fail rules and modification locks
- Tier classification
- Protected files list

## Definition of Done

A GMP run is complete when ALL are true:

```
✓ Phase 0 plan created and locked
✓ Phase 1 baseline confirmed
✓ Phase 2 implementation complete
✓ Phase 3 enforcement added
✓ Phase 4 validation complete
✓ Phase 5 recursive verification complete
✓ Phase 6 finalization complete
✓ All checklists passed (100%)
✓ No further changes justified
✓ System is deterministic and complete
```

## Version History

| Version | Date       | Changes                                                   |
| ------- | ---------- | --------------------------------------------------------- |
| 3.2.0   | 2026-01-18 | Aligned to L9 canonical phases 0-6, created contract YAML |
| 3.1.0   | 2026-01-12 | Phase files standardized                                  |
| 2.0     | 2025-12-21 | G-CMP comprehensive template (deprecated phase -1 to 5)   |

## Related Files

- `.cursor/rules/80-gmp-execution.mdc` — Workspace rules for GMP execution
- `.cursor/rules/81-gmp-audit.mdc` — Audit and verification rules
- `reports/GMP_Report_*.md` — Generated GMP reports
