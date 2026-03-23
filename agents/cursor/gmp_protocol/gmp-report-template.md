<!-- CONTRACT: agents/cursor/gmp_protocol/gmp-report-contract.yaml v3.3.0 -->
<!-- VALIDATE: python3 scripts/validate_gmp_report.py {this_file} -->
<!-- ID: Next sequential after checking reports/ and reports/GMP Reports/ -->

# GMP-Report-{###}-{Description}

**ID:** GMP-{###}
**Task:** {task}
**Tier:** {KERNEL|RUNTIME|INFRA|UX}\_TIER
**Date:** {YYYY-MM-DD}
**Time:** {HH:MM} EST
**Status:** {✅ COMPLETE|⚠️ PARTIAL|❌ FAILED}

<!--
  BEFORE CREATING:
  1. Check highest GMP number: ls reports/GMP-Report-*.md reports/'GMP Reports'/GMP*Report*.md | grep -oE '[0-9]+' | sort -n | tail -1
  2. Use: highest + 1, zero-padded to 3 digits (e.g., 097, 098, 099)
  3. Date: Today's date in ISO format (YYYY-MM-DD)
  4. Time: Current EST time in 24-hour format (HH:MM EST)
-->

---

## PLAN

| ID  | File   | Lines      | Action   | Status |
| --- | ------ | ---------- | -------- | ------ | ------- | ------- | --- | --- |
| T1  | {path} | {L###}     | {CREATE  | INSERT | REPLACE | DELETE} | {✅ | ❌} |
| T2  | {path} | {L###-###} | {action} | {✅    | ❌}     |

**Hash:** `{TODO_COUNT} TODOs | {key files summary}`

---

## CHANGES

| File     | Lines     | Action   | Description          |
| -------- | --------- | -------- | -------------------- |
| `{path}` | {###-###} | {action} | {change description} |

---

## TODO → CHANGE MAP

| TODO | File   | Change         |
| ---- | ------ | -------------- |
| T1   | {file} | {what changed} |

---

## VALIDATION

| Gate        | Result        |
| ----------- | ------------- |
| py_compile  | ✅            |
| import test | ✅            |
| unit tests  | ✅ {X} passed |

---

## DECLARATION

Phases 0-6 complete. No assumptions. No drift.
