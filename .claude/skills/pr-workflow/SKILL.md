---
name: pr-workflow
description: Create a branch, commit, and open a PR following CEG conventions
disable-model-invocation: true
---

# PR Workflow

## Branch Naming
- `feat/short-description` — new features
- `fix/short-description` — bug fixes
- `docs/short-description` — documentation
- `refactor/short-description` — code restructuring
- `test/short-description` — test additions

## Pre-Commit Checklist
1. Run `make lint` — must pass (ruff check + mypy)
2. Run `make test-unit` — all unit tests pass
3. Run `python tools/contract_scanner.py` — no violations
4. Verify L9_META headers on new files: `python tools/l9_meta_injector.py`

## Commit Message Format
Conventional commits:
```
feat: add proximity gate type
fix: clamp negative scores in geodecay
docs: update domain spec authoring guide
refactor: extract circuit breaker into separate module
test: add property tests for composite gates
```

## PR Description Template
```
## What
Brief description of the change.

## Why
Motivation and context.

## Changes
- File-by-file summary of changes

## Testing
- What tests were added or run
- `make test-unit` result
- `make lint` result

## Contracts
- Which contracts this change relates to
- Contract scanner result: clean / violations addressed
```
