#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [audit]
tags: [L9_TEMPLATE, audit, contracts]
owner: platform
status: active
--- /L9_META ---

L9 Contract Violation Scanner
Encodes all 20 contracts as grep-able rules.
Exit code 1 = violations found = commit/merge blocked.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Violation:
    file: str
    line: int
    rule_id: str
    contract: str
    severity: str
    message: str
    remediation: str


def _rule(
    rule_id: str,
    contract: str,
    severity: str,
    pattern: str,
    message: str,
    remediation: str,
    *,
    include_dirs: list[str] | None = None,
    exclude_dirs: list[str] | None = None,
) -> dict:
    r = {
        "id": rule_id,
        "contract": contract,
        "severity": severity,
        "pattern": pattern,
        "message": message,
        "remediation": remediation,
    }
    if include_dirs is not None:
        r["include_dirs"] = include_dirs
    if exclude_dirs is not None:
        r["exclude_dirs"] = exclude_dirs
    return r


RULES: list[dict] = [
    # -- CONTRACT 3: CYPHER_SAFETY.md --
    _rule(
        "SEC-001",
        "CYPHER_SAFETY.md",
        "CRITICAL",
        r'f["\'].*MATCH\s*\(.*\{[^$]',
        "Cypher label interpolation without sanitize_label()",
        "Use sanitize_label() for labels, $param for values",
        include_dirs=["engine/"],
        exclude_dirs=["engine/sync/generator.py", "engine/handlers.py"],  # labels sanitized via sanitize_label()
    ),
    _rule(
        "SEC-002",
        "CYPHER_SAFETY.md",
        "CRITICAL",
        r"\beval\s*\(",
        "eval() is banned - code injection risk",
        "Use operator dispatch table or ast.literal_eval()",
        exclude_dirs=["tests/", "tools/contract_scanner.py", "engine/utils/safe_eval.py"],  # AST-based; no eval()
    ),
    _rule(
        "SEC-003",
        "CYPHER_SAFETY.md",
        "CRITICAL",
        r"\bexec\s*\(",
        "exec() is banned - code injection risk",
        "Remove entirely",
        exclude_dirs=["tests/", "tools/contract_scanner.py", "engine/security/"],
    ),
    _rule(
        "SEC-004",
        "CYPHER_SAFETY.md",
        "CRITICAL",
        r'f["\'].*LIMIT\s*\{',
        "LIMIT value interpolation - use $limit parameter",
        "LIMIT $limit with params={'limit': n}",
    ),
    _rule(
        "SEC-005",
        "BANNED_PATTERNS.md",
        "CRITICAL",
        r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)\s.*\{',
        "SQL string interpolation - use parameterized queries",
        "Use $1/$2 placeholders or ORM",
    ),
    _rule(
        "SEC-006",
        "BANNED_PATTERNS.md",
        "CRITICAL",
        r"pickle\.loads?\s*\(",
        "pickle banned - deserialization attack vector",
        "Use json.loads()",
    ),
    _rule(
        "SEC-007",
        "BANNED_PATTERNS.md",
        "CRITICAL",
        r"yaml\.load\s*\([^)]*\)\s*$",
        "yaml.load() without SafeLoader",
        "yaml.safe_load()",
    ),
    # -- CONTRACT 4: ERROR_HANDLING.md --
    _rule(
        "ERR-001",
        "ERROR_HANDLING.md",
        "HIGH",
        r"except\s*:",
        "Bare except: clause",
        "except SpecificError as e:",
        exclude_dirs=["tools/contract_scanner.py"],
    ),
    _rule(
        "ERR-002",
        "ERROR_HANDLING.md",
        "HIGH",
        r"except\s+\w+.*:\s*\n\s*pass",
        "Swallowed exception - except + pass",
        "Log and re-raise",
    ),
    # -- CONTRACT 10: BANNED_PATTERNS.md (Architecture) --
    _rule(
        "ARCH-001",
        "BANNED_PATTERNS.md",
        "CRITICAL",
        r"from\s+fastapi\s+import",
        "FastAPI import in engine/ - chassis owns HTTP",
        "Register handlers in engine/handlers.py",
        include_dirs=["engine/"],
    ),
    _rule(
        "ARCH-002",
        "BANNED_PATTERNS.md",
        "CRITICAL",
        r"from\s+starlette\s+import",
        "Starlette import in engine/ - chassis owns middleware",
        "Remove",
        include_dirs=["engine/"],
    ),
    _rule(
        "ARCH-003",
        "BANNED_PATTERNS.md",
        "CRITICAL",
        r"import\s+uvicorn",
        "uvicorn import in engine/ - chassis owns ASGI",
        "Remove",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 7: DEPENDENCY_INJECTION.md --
    _rule(
        "DI-001",
        "DEPENDENCY_INJECTION.md",
        "HIGH",
        r"from\s+fastapi\s+import\s+Depends",
        "FastAPI Depends in engine/ - chassis concern",
        "Use init_dependencies() pattern",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 12: DELEGATION_PROTOCOL.md --
    _rule(
        "DEL-001",
        "DELEGATION_PROTOCOL.md",
        "CRITICAL",
        r"httpx\.(post|get|put|delete|patch)\s*\(",
        "Raw HTTP to another node - use delegate_to_node()",
        "from l9.core.delegation import delegate_to_node",
        include_dirs=["engine/"],
    ),
    _rule(
        "DEL-002",
        "DELEGATION_PROTOCOL.md",
        "CRITICAL",
        r"requests\.(post|get|put|delete|patch)\s*\(",
        "Raw HTTP via requests - use delegate_to_node()",
        "from l9.core.delegation import delegate_to_node",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 19: MEMORY_SUBSTRATE_ACCESS.md --
    _rule(
        "MEM-001",
        "MEMORY_SUBSTRATE_ACCESS.md",
        "CRITICAL",
        r"INSERT\s+INTO\s+packetstore",
        "Direct write to packetstore - use ingest_packet()",
        "from l9.memory.ingestion import ingest_packet",
        include_dirs=["engine/"],
    ),
    _rule(
        "MEM-002",
        "MEMORY_SUBSTRATE_ACCESS.md",
        "CRITICAL",
        r"INSERT\s+INTO\s+memory_embeddings",
        "Direct write to memory_embeddings - use ingest_packet()",
        "Embeddings generated by LangGraph DAG",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 20: SHARED_MODELS.md --
    _rule(
        "SHARED-001",
        "SHARED_MODELS.md",
        "HIGH",
        r"class\s+PacketEnvelope\s*\(",
        "Redefining PacketEnvelope - import from l9.core",
        "from l9.core.envelope import PacketEnvelope",
        include_dirs=["engine/"],
        exclude_dirs=["engine/packet/packet_envelope.py"],  # canonical envelope in this repo
    ),
    _rule(
        "SHARED-002",
        "SHARED_MODELS.md",
        "HIGH",
        r"class\s+TenantContext\s*\(",
        "Redefining TenantContext - import from l9.core",
        "from l9.core.envelope import TenantContext",
        include_dirs=["engine/"],
        exclude_dirs=["engine/packet/packet_envelope.py"],  # canonical envelope in this repo
    ),
    _rule(
        "SHARED-003",
        "SHARED_MODELS.md",
        "HIGH",
        r"class\s+ExecuteRequest\s*\(",
        "Redefining ExecuteRequest - import from l9.core",
        "from l9.core.contract import ExecuteRequest",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 18: OBSERVABILITY.md --
    _rule(
        "OBS-001",
        "OBSERVABILITY.md",
        "HIGH",
        r"structlog\.configure\s*\(",
        "Configuring structlog in engine - chassis does this",
        "Use logging.getLogger(__name__)",
        include_dirs=["engine/"],
    ),
    _rule(
        "OBS-002",
        "OBSERVABILITY.md",
        "HIGH",
        r"logging\.basicConfig\s*\(",
        "Configuring logging in engine - chassis does this",
        "Use logging.getLogger(__name__) only",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 6: PYDANTIC_YAML_MAPPING.md --
    _rule(
        "NAME-001",
        "PYDANTIC_YAML_MAPPING.md",
        "HIGH",
        r"Field\s*\(\s*alias\s*=",
        "Pydantic Field alias banned - snake_case everywhere",
        "Remove alias, use snake_case matching YAML key",
        include_dirs=["engine/"],
    ),
    # -- CONTRACT 13: PACKET_TYPE_REGISTRY.md --
    _rule(
        "PKT-001",
        "PACKET_TYPE_REGISTRY.md",
        "HIGH",
        r'packet_type\s*[=:]\s*["\'][A-Z]',
        "Uppercase packet_type - must be lowercase snake_case",
        "Check PACKET_TYPE_REGISTRY.md",
    ),
    # -- CONTRACT 17: ENV_VARS.md --
    _rule(
        "ENV-001",
        "ENV_VARS.md",
        "MEDIUM",
        r'os\.environ\[["\']?(?:NEO4J_URI|NEO4J_URL|DATABASE_URL|REDIS_HOST|API_KEY)["\']?\]',
        "Non-standard env var name",
        "Use L9_* or ENGINE_* prefix per ENV_VARS.md",
    ),
]

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}


def _path_matches_rule(file_path: Path, rule: dict) -> bool:
    path_str = str(file_path) + "/"
    if include_dirs := rule.get("include_dirs"):
        if not any(path_str.startswith(d) for d in include_dirs):
            return False
    if exclude_dirs := rule.get("exclude_dirs"):
        if any(path_str.startswith(d) for d in exclude_dirs):
            return False
    return True


def scan_file(file_path: Path, content: str, root: Path) -> list[Violation]:
    violations: list[Violation] = []
    # Handle both absolute and relative paths
    try:
        abs_path = file_path.resolve()
        abs_root = root.resolve()
        rel = abs_path.relative_to(abs_root)
    except ValueError:
        # Path is already relative or not under root
        rel = file_path
    rel_str = str(rel).replace("\\", "/")

    for rule in RULES:
        if not _path_matches_rule(Path(rel_str), rule):
            continue
        try:
            pat = re.compile(rule["pattern"], re.MULTILINE | re.DOTALL)
        except re.error:
            continue
        for i, line in enumerate(content.splitlines(), start=1):
            if pat.search(line):
                violations.append(
                    Violation(
                        file=rel_str,
                        line=i,
                        rule_id=rule["id"],
                        contract=rule["contract"],
                        severity=rule["severity"],
                        message=rule["message"],
                        remediation=rule["remediation"],
                    )
                )
    return violations


def main() -> int:
    root = Path.cwd()
    skip_dirs = {".venv", "venv", "__pycache__", ".git", "site-packages"}
    if len(sys.argv) > 1:
        # Pre-commit passes filenames
        paths = [Path(p) for p in sys.argv[1:] if Path(p).suffix == ".py" and not any(s in str(p) for s in skip_dirs)]
    else:
        paths = [p for p in root.rglob("*.py") if not any(s in str(p) for s in skip_dirs)]

    all_violations: list[Violation] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        all_violations.extend(scan_file(path, text, root))

    all_violations.sort(key=lambda v: (SEVERITY_ORDER.get(v.severity, 99), v.file, v.line))

    if not all_violations:
        print("L9 contract scan: no violations.")
        return 0

    print("L9 Contract Violations (commit/merge blocked):\n", file=sys.stderr)
    for v in all_violations:
        print(
            f"  [{v.rule_id}] {v.file}:{v.line} ({v.severity})\n    {v.message}\n    → {v.remediation}\n",
            file=sys.stderr,
        )
    print(
        f"Total: {len(all_violations)} violation(s). Fix before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
