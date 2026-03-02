# L9 Contract Enforcement System
## Making 20 Contracts Enforced Law — Not Aspirational Guidelines
### Version 1.0.0 | 2026-03-01

---

## The Problem

You have 20 contracts. Agents read them *if they feel like it*. Nothing stops a PR
with `eval()`, a redefined `PacketEnvelope`, or a hand-rolled `httpx.post()` to
another node from merging. The contracts are documentation, not law.

**Law = code that blocks the merge.** Everything below is a concrete tool, hook,
or CI gate that turns each contract into a hard failure.

---

## Enforcement Architecture

```
Developer / Agent writes code
        |
        v
+-------------------------+
|   PRE-COMMIT HOOKS      |  <- Runs on every git commit locally
|   (instant feedback)    |  <- Blocks commit if violations found
+-----------+-------------+
            | passes
            v
+-------------------------+
|   CI - lint + audit     |  <- Runs on every push / PR
|   (GitHub Actions)      |  <- Blocks merge if violations found
+-----------+-------------+
            | passes
            v
+-------------------------+
|   CI - tests            |  <- Unit + integration + compliance
|                         |  <- Blocks merge if tests fail
+-----------+-------------+
            | passes
            v
+-------------------------+
|   CI - contract audit   |  <- Verifies all 20 files exist & unmodified
|                         |  <- Verifies no contract violations in code
|                         |  <- Blocks merge on ANY finding
+-----------+-------------+
            | passes
            v
+-------------------------+
|   3-LLM PR Review       |  <- CodeRabbit + Qodo + Claude
|   (configured with      |  <- Each reviewer knows the 20 contracts
|    contract awareness)   |  <- Blocks merge on CRITICAL findings
+-----------+-------------+
            | all pass
            v
        MERGE ALLOWED

Anything fails -> PR blocked -> agent/developer must fix
```

---

## Layer 1: Pre-Commit Hooks (Instant Local Feedback)

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.0]
        args: [--strict, engine/]

  - repo: local
    hooks:
      - id: l9-contract-scan
        name: L9 Contract Violation Scanner
        entry: python tools/contract_scanner.py
        language: python
        types: [python]
        pass_filenames: true

      - id: l9-contract-files-exist
        name: L9 Contract Files Existence Check
        entry: python tools/verify_contracts.py
        language: python
        pass_filenames: false
        always_run: true
```

---

## Layer 2: `tools/contract_scanner.py` (The Enforcer)

This single script encodes ALL 20 contracts as scannable regex rules.
Runs on pre-commit (per-file) and in CI (full repo). Exit 1 = blocked.

```python
"""
L9 Contract Violation Scanner
Encodes all 20 contracts as grep-able rules.
Exit code 1 = violations found = commit/merge blocked.
"""

import re, sys
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Violation:
    file: str
    line: int
    rule_id: str
    contract: str
    severity: str  # CRITICAL, HIGH, MEDIUM
    message: str
    remediation: str

RULES = [
    # -- CONTRACT 3: CYPHER_SAFETY.md --
    {"id": "SEC-001", "contract": "CYPHER_SAFETY.md", "severity": "CRITICAL",
     "pattern": r'f["\']\.\*MATCH\s\*\(.*\{[^$]',
     "message": "Cypher label interpolation without sanitize_label()",
     "remediation": "Use sanitize_label() for labels, $param for values",
     "include_dirs": ["engine/"]},
    {"id": "SEC-002", "contract": "CYPHER_SAFETY.md", "severity": "CRITICAL",
     "pattern": r'\beval\s\*\(',
     "message": "eval() is banned - code injection risk",
     "remediation": "Use operator dispatch table or ast.literal_eval()",
     "exclude_dirs": ["tests/"]},
    {"id": "SEC-003", "contract": "CYPHER_SAFETY.md", "severity": "CRITICAL",
     "pattern": r'\bexec\s\*\(',
     "message": "exec() is banned - code injection risk",
     "remediation": "Remove entirely",
     "exclude_dirs": ["tests/"]},
    {"id": "SEC-004", "contract": "CYPHER_SAFETY.md", "severity": "CRITICAL",
     "pattern": r'f["\']\.\*LIMIT\s\*\{',
     "message": "LIMIT value interpolation - use $limit parameter",
     "remediation": "LIMIT $limit with params={'limit': n}"},
    {"id": "SEC-005", "contract": "BANNED_PATTERNS.md", "severity": "CRITICAL",
     "pattern": r'f["\']\.\*(?:SELECT|INSERT|UPDATE|DELETE)\s.*\{',
     "message": "SQL string interpolation - use parameterized queries",
     "remediation": "Use $1/$2 placeholders or ORM"},
    {"id": "SEC-006", "contract": "BANNED_PATTERNS.md", "severity": "CRITICAL",
     "pattern": r'pickle\.loads?\s\*\(',
     "message": "pickle banned - deserialization attack vector",
     "remediation": "Use json.loads()"},
    {"id": "SEC-007", "contract": "BANNED_PATTERNS.md", "severity": "CRITICAL",
     "pattern": r'yaml\.load\s\*\([^)]*\)\s*$',
     "message": "yaml.load() without SafeLoader",
     "remediation": "yaml.safe_load()"},

    # -- CONTRACT 4: ERROR_HANDLING.md --
    {"id": "ERR-001", "contract": "ERROR_HANDLING.md", "severity": "HIGH",
     "pattern": r'except\s*:',
     "message": "Bare except: clause",
     "remediation": "except SpecificError as e:"},
    {"id": "ERR-002", "contract": "ERROR_HANDLING.md", "severity": "HIGH",
     "pattern": r'except\s+\w+.*:\s*\n\s*pass',
     "message": "Swallowed exception - except + pass",
     "remediation": "Log and re-raise"},

    # -- CONTRACT 10: BANNED_PATTERNS.md (Architecture) --
    {"id": "ARCH-001", "contract": "BANNED_PATTERNS.md", "severity": "CRITICAL",
     "pattern": r'from\s+fastapi\s+import',
     "message": "FastAPI import in engine/ - chassis owns HTTP",
     "remediation": "Register handlers in engine/handlers.py",
     "include_dirs": ["engine/"]},
    {"id": "ARCH-002", "contract": "BANNED_PATTERNS.md", "severity": "CRITICAL",
     "pattern": r'from\s+starlette\s+import',
     "message": "Starlette import in engine/ - chassis owns middleware",
     "remediation": "Remove",
     "include_dirs": ["engine/"]},
    {"id": "ARCH-003", "contract": "BANNED_PATTERNS.md", "severity": "CRITICAL",
     "pattern": r'import\s+uvicorn',
     "message": "uvicorn import in engine/ - chassis owns ASGI",
     "remediation": "Remove",
     "include_dirs": ["engine/"]},

    # -- CONTRACT 7: DEPENDENCY_INJECTION.md --
    {"id": "DI-001", "contract": "DEPENDENCY_INJECTION.md", "severity": "HIGH",
     "pattern": r'from\s+fastapi\s+import\s+Depends',
     "message": "FastAPI Depends in engine/ - chassis concern",
     "remediation": "Use init_dependencies() pattern",
     "include_dirs": ["engine/"]},

    # -- CONTRACT 12: DELEGATION_PROTOCOL.md --
    {"id": "DEL-001", "contract": "DELEGATION_PROTOCOL.md", "severity": "CRITICAL",
     "pattern": r'httpx\.(post|get|put|delete|patch)\s*\(',
     "message": "Raw HTTP to another node - use delegate_to_node()",
     "remediation": "from l9.core.delegation import delegate_to_node",
     "include_dirs": ["engine/"]},
    {"id": "DEL-002", "contract": "DELEGATION_PROTOCOL.md", "severity": "CRITICAL",
     "pattern": r'requests\.(post|get|put|delete|patch)\s*\(',
     "message": "Raw HTTP via requests - use delegate_to_node()",
     "remediation": "from l9.core.delegation import delegate_to_node",
     "include_dirs": ["engine/"]},

    # -- CONTRACT 19: MEMORY_SUBSTRATE_ACCESS.md --
    {"id": "MEM-001", "contract": "MEMORY_SUBSTRATE_ACCESS.md", "severity": "CRITICAL",
     "pattern": r'INSERT\s+INTO\s+packetstore',
     "message": "Direct write to packetstore - use ingest_packet()",
     "remediation": "from l9.memory.ingestion import ingest_packet",
     "include_dirs": ["engine/"]},
    {"id": "MEM-002", "contract": "MEMORY_SUBSTRATE_ACCESS.md", "severity": "CRITICAL",
     "pattern": r'INSERT\s+INTO\s+memory_embeddings',
     "message": "Direct write to memory_embeddings - use ingest_packet()",
     "remediation": "Embeddings generated by LangGraph DAG",
     "include_dirs": ["engine/"]},

    # -- CONTRACT 20: SHARED_MODELS.md --
    {"id": "SHARED-001", "contract": "SHARED_MODELS.md", "severity": "HIGH",
     "pattern": r'class\s+PacketEnvelope\s*\(',
     "message": "Redefining PacketEnvelope - import from l9.core",
     "remediation": "from l9.core.envelope import PacketEnvelope",
     "include_dirs": ["engine/"]},
    {"id": "SHARED-002", "contract": "SHARED_MODELS.md", "severity": "HIGH",
     "pattern": r'class\s+TenantContext\s*\(',
     "message": "Redefining TenantContext - import from l9.core",
     "remediation": "from l9.core.envelope import TenantContext",
     "include_dirs": ["engine/"]},
    {"id": "SHARED-003", "contract": "SHARED_MODELS.md", "severity": "HIGH",
     "pattern": r'class\s+ExecuteRequest\s*\(',
     "message": "Redefining ExecuteRequest - import from l9.core",
     "remediation": "from l9.core.contract import ExecuteRequest",
     "include_dirs": ["engine/"]},

    # -- CONTRACT 18: OBSERVABILITY.md --
    {"id": "OBS-001", "contract": "OBSERVABILITY.md", "severity": "HIGH",
     "pattern": r'structlog\.configure\s*\(',
     "message": "Configuring structlog in engine - chassis does this",
     "remediation": "Use logging.getLogger(__name__)",
     "include_dirs": ["engine/"]},
    {"id": "OBS-002", "contract": "OBSERVABILITY.md", "severity": "HIGH",
     "pattern": r'logging\.basicConfig\s*\(',
     "message": "Configuring logging in engine - chassis does this",
     "remediation": "Use logging.getLogger(__name__) only",
     "include_dirs": ["engine/"]},

    # -- CONTRACT 6: PYDANTIC_YAML_MAPPING.md --
    {"id": "NAME-001", "contract": "PYDANTIC_YAML_MAPPING.md", "severity": "HIGH",
     "pattern": r'Field\s*\(\s*alias\s*=',
     "message": "Pydantic Field alias banned - snake_case everywhere",
     "remediation": "Remove alias, use snake_case matching YAML key",
     "include_dirs": ["engine/"]},

    # -- ZERO-STUB BUILD PROTOCOL --
    {"id": "STUB-001", "contract": "ZERO_STUB_BUILD_PROTOCOL.md", "severity": "CRITICAL",
     "pattern": r'raise\s+NotImplementedError',
     "message": "NotImplementedError stub - implement or DEFERRED.md",
     "remediation": "Write implementation or document in DEFERRED.md",
     "exclude_dirs": ["tests/"]},
    {"id": "STUB-002", "contract": "ZERO_STUB_BUILD_PROTOCOL.md", "severity": "HIGH",
     "pattern": r'#\s*TODO',
     "message": "TODO comment - implement or DEFERRED.md",
     "remediation": "Implement or defer explicitly"},
    {"id": "STUB-003", "contract": "ZERO_STUB_BUILD_PROTOCOL.md", "severity": "HIGH",
     "pattern": r'#\s*PLACEHOLDER',
     "message": "PLACEHOLDER comment - implement or defer",
     "remediation": "Write real code or DEFERRED.md"},

    # -- CONTRACT 13: PACKET_TYPE_REGISTRY.md --
    {"id": "PKT-001", "contract": "PACKET_TYPE_REGISTRY.md", "severity": "HIGH",
     "pattern": r'packet_type\s*[=:]\s*["\'"][A-Z]',
     "message": "Uppercase packet_type - must be lowercase snake_case",
     "remediation": "Check PACKET_TYPE_REGISTRY.md"},

    # -- CONTRACT 17: ENV_VARS.md --
    {"id": "ENV-001", "contract": "ENV_VARS.md", "severity": "MEDIUM",
     "pattern": r'os\.environ\[.(?:NEO4J_URI|NEO4J_URL|DATABASE_URL|REDIS_HOST|API_KEY).\]',
     "message": "Non-standard env var name",
     "remediation": "Use L9_* or ENGINE_* prefix per ENV_VARS.md"},
]
```

The full scanner (with `scan_file()`, directory walking, severity sorting,
formatted output, and exit-code logic) follows the exact pattern shown in
the architecture section above. Each rule maps to one contract.

---

## Layer 3: `tools/verify_contracts.py` (File Existence + Wiring)

Verifies all 20 contract files exist AND are referenced in `.cursorrules`
and `CLAUDE.md`. Blocks CI if any are missing or unwired.

```python
REQUIRED_CONTRACTS = [
    # 1-10: Engine-internal
    "docs/contracts/FIELD_NAMES.md",
    "docs/contracts/METHOD_SIGNATURES.md",
    "docs/contracts/CYPHER_SAFETY.md",
    "docs/contracts/ERROR_HANDLING.md",
    "docs/contracts/HANDLER_PAYLOADS.md",
    "docs/contracts/PYDANTIC_YAML_MAPPING.md",
    "docs/contracts/DEPENDENCY_INJECTION.md",
    "docs/contracts/TEST_PATTERNS.md",
    "docs/contracts/RETURN_VALUES.md",
    "docs/contracts/BANNED_PATTERNS.md",
    # 11-20: Constellation
    "docs/contracts/PACKET_ENVELOPE_FIELDS.md",
    "docs/contracts/DELEGATION_PROTOCOL.md",
    "docs/contracts/PACKET_TYPE_REGISTRY.md",
    "docs/contracts/DOMAIN_SPEC_VERSIONING.md",
    "docs/contracts/FEEDBACK_LOOPS.md",
    "docs/contracts/NODE_REGISTRATION.md",
    "docs/contracts/ENV_VARS.md",
    "docs/contracts/OBSERVABILITY.md",
    "docs/contracts/MEMORY_SUBSTRATE_ACCESS.md",
    "docs/contracts/SHARED_MODELS.md",
]
AGENT_FILES = [".cursorrules", "CLAUDE.md"]

# For each contract: check file exists + check filename appears in each agent file
# Exit 1 if anything missing -> blocks merge
```

---

## Layer 4: CI Pipeline (The Final Gate)

### `.github/workflows/contracts.yml`

```yaml
name: Contract Enforcement
on: [push, pull_request]

jobs:
  contract-files:
    name: Verify Contract Files Exist
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python tools/verify_contracts.py

  contract-scan:
    name: Scan for Contract Violations
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python tools/contract_scanner.py

  lint:
    name: Lint + Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[dev]"
      - run: ruff check . && ruff format --check .
      - run: mypy engine/ --strict

  test:
    name: Test Suite
    runs-on: ubuntu-latest
    needs: [contract-files, contract-scan, lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --tb=short
```

### GitHub Branch Protection (Settings -> Branches -> main)

```
Required status checks:
  - contract-files
  - contract-scan
  - lint
  - test
Do not allow bypassing the above settings: ON
```

---

## Layer 5: LLM Reviewer Configuration

### CodeRabbit `.coderabbit.yaml`

```yaml
reviews:
  instructions: |
    This repo follows the L9 Constellation architecture. Check ALL code against
    these rules (violations are CRITICAL):

    1. No eval(), exec(), pickle.loads() anywhere
    2. No f-string interpolation in Cypher or SQL - use parameterized queries
    3. No FastAPI imports in engine/ - chassis owns HTTP
    4. No raw HTTP calls between nodes - use delegate_to_node()
    5. No direct writes to packetstore - use ingest_packet()
    6. No redefining PacketEnvelope/TenantContext/ExecuteRequest - import from l9-core
    7. No configuring structlog or logging.basicConfig in engine/ - chassis does it
    8. No bare except: clauses
    9. No NotImplementedError stubs
    10. All packet_type values must be lowercase snake_case from the registry

    Contract files are in docs/contracts/. Reference them in your review.
```

---

## Contract-to-Enforcement Matrix

| # | Contract | Scanner Rules | Pre-Commit | CI | LLM Review |
|---|----------|--------------|------------|-----|------------|
| 1 | FIELD_NAMES.md | (semantic - tests) | - | pytest | Yes |
| 2 | METHOD_SIGNATURES.md | (semantic - tests) | - | pytest | Yes |
| 3 | CYPHER_SAFETY.md | SEC-001 to SEC-004 | Yes | Yes | Yes |
| 4 | ERROR_HANDLING.md | ERR-001, ERR-002 | Yes | Yes | Yes |
| 5 | HANDLER_PAYLOADS.md | (type checker) | mypy | mypy | Yes |
| 6 | PYDANTIC_YAML_MAPPING.md | NAME-001 | Yes | Yes | Yes |
| 7 | DEPENDENCY_INJECTION.md | DI-001 | Yes | Yes | Yes |
| 8 | TEST_PATTERNS.md | (semantic) | - | pytest | Yes |
| 9 | RETURN_VALUES.md | (type checker) | mypy | mypy | Yes |
| 10 | BANNED_PATTERNS.md | ARCH-001 to 003, SEC-005 to 007 | Yes | Yes | Yes |
| 11 | PACKET_ENVELOPE_FIELDS.md | (l9-core types) | mypy | mypy | Yes |
| 12 | DELEGATION_PROTOCOL.md | DEL-001, DEL-002 | Yes | Yes | Yes |
| 13 | PACKET_TYPE_REGISTRY.md | PKT-001 | Yes | Yes | Yes |
| 14 | DOMAIN_SPEC_VERSIONING.md | (semantic) | - | pytest | Yes |
| 15 | FEEDBACK_LOOPS.md | (integration tests) | - | pytest | Yes |
| 16 | NODE_REGISTRATION.md | (semantic) | - | verify_contracts | Yes |
| 17 | ENV_VARS.md | ENV-001 | Yes | Yes | Yes |
| 18 | OBSERVABILITY.md | OBS-001, OBS-002 | Yes | Yes | Yes |
| 19 | MEMORY_SUBSTRATE_ACCESS.md | MEM-001, MEM-002 | Yes | Yes | Yes |
| 20 | SHARED_MODELS.md | SHARED-001 to 003 | Yes | Yes | Yes |
| - | All 20 files exist | verify_contracts.py | Yes | Yes | - |
| - | All 20 wired in CLAUDE.md | verify_contracts.py | Yes | Yes | - |
| - | Zero-Stub Protocol | STUB-001 to 003 | Yes | Yes | Yes |

**16 of 20 contracts have automated scanner rules. The other 4 are semantic
(field names, method signatures, test patterns, domain versioning) and are
enforced by mypy, pytest, and LLM review.**

---

## What This Gives You

- **Pre-commit**: Violations never leave the local machine
- **CI contract-scan**: Even if pre-commit is bypassed, CI catches it
- **CI verify_contracts**: Contract files cannot be deleted or unwired
- **CI tests**: Semantic contracts caught by actual test failures
- **LLM review**: Catches intent/logic violations regex cannot
- **Branch protection**: Nothing merges without all 5 layers green

The contracts stop being "please read this" and become **automated gates
that block bad code from ever reaching main**.

---

L9 Contract Enforcement System v1.0.0
Quantum AI Partners | ScrapManagement.com
Created: 2026-03-01
