#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [audit]
tags: [cutover, audit, contracts, transport, routing]
owner: platform
status: active
--- /L9_META ---

Fail-closed cutover contract scanner for Cognitive.Engine.Graphs.

Authority model enforced by this scanner:
- Gate_SDK is the only accepted runtime authority
- Gate is the only accepted routing authority
- TransportPacket is the only accepted canonical transport
- PacketEnvelope is deprecated compatibility only

The scanner blocks:
- legacy PacketEnvelope treated as active truth
- split-brain ingress or routing
- chassis-first assumptions used as current authority
- known security and architecture regressions that remain load-bearing

Usage:
    python tools/contract_scanner.py
    python tools/contract_scanner.py --format json
    python tools/contract_scanner.py path/to/file.py another/file.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "site-packages",
    "artifacts",
}
TEXT_SUFFIXES = {
    ".py",
    ".pyi",
    ".md",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".sh",
}


@dataclass
class Violation:
    file: str
    line: int | None
    rule_id: str
    contract: str
    severity: str
    message: str
    remediation: str
    evidence: str


@dataclass
class Rule:
    rule_id: str
    contract: str
    severity: str
    message: str
    remediation: str
    include_globs: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    regex: str | None = None
    regex_flags: int = re.MULTILINE
    required_regex: str | None = None
    required_message: str | None = None
    pair_forbidden: tuple[str, str] | None = None
    path_exists_forbidden: tuple[str, ...] = ()

    def applies_to(self, rel_path: str) -> bool:
        path = Path(rel_path)
        if self.include_globs and not any(path.match(pattern) for pattern in self.include_globs):
            return False
        return not (self.exclude_globs and any(path.match(pattern) for pattern in self.exclude_globs))


def compile_rules() -> list[Rule]:
    compatibility_allowlist = (
        "engine/packet/**",
        "docs/**",
        "contracts/**",
        "tests/**",
        "tools/contract_scanner.py",
        "tools/audit_rules.yaml",
        "tools/audit_engine.py",
        "tools/contract_report.py",
        "tools/spec_extract.py",
    )

    return [
        # Cutover runtime, routing, and transport authority.
        Rule(
            rule_id="CUTOVER-RT-001",
            contract="CUTOVER_RUNTIME_AUTHORITY",
            severity="CRITICAL",
            message="Runtime surfaces must anchor to Gate_SDK, not chassis-first or PacketEnvelope-first authority.",
            remediation="Replace legacy runtime authority references with Gate_SDK runtime authority.",
            include_globs=("tools/**/*.py", "engine/**/*.py", "README*.md", "ARCHITECTURE*.md"),
            exclude_globs=compatibility_allowlist,
            regex=r"\b(PacketEnvelope|inflate_ingress|deflate_egress|chassis_contract)\b",
        ),
        Rule(
            rule_id="CUTOVER-RTE-001",
            contract="CUTOVER_ROUTING_AUTHORITY",
            severity="CRITICAL",
            message="Routing surfaces must anchor to Gate as the routing authority.",
            remediation="Replace legacy routing authority references with Gate routing authority.",
            include_globs=("tools/**/*.py", "engine/**/*.py", "README*.md", "ARCHITECTURE*.md"),
            exclude_globs=compatibility_allowlist,
            regex=r"\b(register_handler\(|handle_[a-z_]+\(|router\.py|Action Router|single ingress envelope)\b",
        ),
        Rule(
            rule_id="CUTOVER-TP-001",
            contract="CUTOVER_TRANSPORT_AUTHORITY",
            severity="CRITICAL",
            message="Canonical transport must be TransportPacket.",
            remediation="Introduce or reference TransportPacket as the canonical transport authority.",
            include_globs=("tools/**/*.py", "engine/**/*.py", "README*.md", "ARCHITECTURE*.md"),
            exclude_globs=compatibility_allowlist,
            required_regex=r"\bTransportPacket\b",
            required_message="TransportPacket authority anchor missing.",
        ),
        Rule(
            rule_id="CUTOVER-PE-001",
            contract="PACKETENVELOPE_DEPRECATED_COMPAT_ONLY",
            severity="CRITICAL",
            message="PacketEnvelope is deprecated and may only appear in explicit compatibility surfaces.",
            remediation="Confine PacketEnvelope to compatibility modules, migration docs, or compatibility tests.",
            include_globs=("**/*",),
            exclude_globs=compatibility_allowlist,
            regex=r"\bPacketEnvelope\b",
        ),
        Rule(
            rule_id="CUTOVER-PE-002",
            contract="PACKETENVELOPE_DEPRECATED_COMPAT_ONLY",
            severity="CRITICAL",
            message="Legacy packet methods imply PacketEnvelope is still active truth.",
            remediation="Remove derive/inflate/deflate flows from active truth and route through TransportPacket-compatible bridges only.",
            include_globs=("**/*.py", "**/*.md", "**/*.yaml", "**/*.yml"),
            exclude_globs=compatibility_allowlist,
            regex=r"\b(derive\(|inflate_ingress\(|deflate_egress\(|DelegationLink|HopEntry|content_hash covers .*address)\b",
        ),
        Rule(
            rule_id="CUTOVER-SB-001",
            contract="SPLIT_BRAIN_INGRESS_BLOCKED",
            severity="CRITICAL",
            message="Split-brain ingress detected: TransportPacket and PacketEnvelope both appear active in the same file.",
            remediation="Keep TransportPacket as sole active truth and move PacketEnvelope references behind explicit compatibility shims.",
            include_globs=("**/*.py", "**/*.md", "**/*.yaml", "**/*.yml"),
            exclude_globs=(
                "tests/**",
                "contracts/**",
                "docs/**",
                "engine/packet/**",
                "tools/contract_scanner.py",
                "tools/spec_extract.py",
            ),
            pair_forbidden=(r"\bTransportPacket\b", r"\bPacketEnvelope\b"),
        ),
        Rule(
            rule_id="CUTOVER-SB-002",
            contract="SPLIT_BRAIN_INGRESS_BLOCKED",
            severity="CRITICAL",
            message="Split-brain ingress detected: Gate_SDK and legacy chassis-first ingress both appear active in the same file.",
            remediation="Make Gate_SDK the sole runtime authority. Legacy ingress may only exist in compatibility fences.",
            include_globs=("**/*.py", "**/*.md", "**/*.yaml", "**/*.yml"),
            exclude_globs=(
                "tests/**",
                "contracts/**",
                "docs/**",
                "engine/packet/**",
                "tools/contract_scanner.py",
                "tools/spec_extract.py",
            ),
            pair_forbidden=(
                r"\bGate_SDK\b",
                r"\b(inflate_ingress|deflate_egress|POST /v1/execute|single ingress envelope)\b",
            ),
        ),
        Rule(
            rule_id="CUTOVER-CH-001",
            contract="CHASSIS_FIRST_ASSUMPTIONS_REMOVED",
            severity="HIGH",
            message="Chassis-first architectural assumptions remain in active tooling.",
            remediation="Replace chassis-first language with Gate_SDK or Gate/TransportPacket cutover language.",
            include_globs=("tools/**/*.py", "tools/**/*.yaml", "README*.md", "ARCHITECTURE*.md"),
            exclude_globs=("contracts/**", "docs/**", "tests/**"),
            regex=r"\b(chassis owns HTTP|universal chassis|single ingress|POST /v1/execute|ExecuteRequest|ExecuteResponse)\b",
        ),
        # Existing security and architecture law still matter.
        Rule(
            rule_id="SEC-001",
            contract="CYPHER_SAFETY",
            severity="CRITICAL",
            message="Potential Cypher interpolation without sanitize_label().",
            remediation="Use sanitize_label() for labels and parameters for values.",
            include_globs=("engine/**/*.py",),
            exclude_globs=("engine/handlers.py",),
            regex=r"f[\"'].*(?:MATCH|MERGE)\s*\([^\n]*\{",
        ),
        Rule(
            rule_id="SEC-002",
            contract="BANNED_PATTERNS",
            severity="CRITICAL",
            message="eval() is banned.",
            remediation="Use a dispatch table or explicit parser.",
            include_globs=("engine/**/*.py", "tools/**/*.py"),
            exclude_globs=("engine/utils/safe_eval.py", "tests/**", "tools/contract_scanner.py"),
            regex=r"\beval\s*\(",
        ),
        Rule(
            rule_id="SEC-003",
            contract="BANNED_PATTERNS",
            severity="CRITICAL",
            message="exec() is banned.",
            remediation="Remove exec() entirely.",
            include_globs=("engine/**/*.py", "tools/**/*.py"),
            exclude_globs=("tests/**", "tools/contract_scanner.py"),
            regex=r"\bexec\s*\(",
        ),
        Rule(
            rule_id="ARCH-001",
            contract="ENGINE_BOUNDARY",
            severity="CRITICAL",
            message="FastAPI import in engine. HTTP belongs outside engine business logic.",
            remediation="Remove FastAPI imports from engine code.",
            include_globs=("engine/**/*.py",),
            regex=r"\b(from\s+fastapi\s+import|import\s+fastapi)\b",
        ),
        Rule(
            rule_id="ARCH-002",
            contract="ENGINE_BOUNDARY",
            severity="CRITICAL",
            message="Starlette import in engine. HTTP/middleware belongs outside engine business logic.",
            remediation="Remove Starlette imports from engine code.",
            include_globs=("engine/**/*.py",),
            regex=r"\b(from\s+starlette\s+import|import\s+starlette)\b",
        ),
        Rule(
            rule_id="ARCH-003",
            contract="ENGINE_BOUNDARY",
            severity="CRITICAL",
            message="uvicorn import in engine. ASGI bootstrap is not engine business logic.",
            remediation="Remove uvicorn imports from engine code.",
            include_globs=("engine/**/*.py",),
            regex=r"\bimport\s+uvicorn\b",
        ),
        Rule(
            rule_id="ERR-001",
            contract="ERROR_HANDLING",
            severity="HIGH",
            message="Bare except is forbidden.",
            remediation="Catch explicit exceptions and log or re-raise intentionally.",
            include_globs=("engine/**/*.py", "tools/**/*.py"),
            regex=r"^\s*except\s*:\s*$",
        ),
        Rule(
            rule_id="OBS-001",
            contract="OBSERVABILITY",
            severity="HIGH",
            message="Engine must not configure structlog.",
            remediation="Use structlog.get_logger(__name__) only.",
            include_globs=("engine/**/*.py",),
            regex=r"\bstructlog\.configure\s*\(",
        ),
        Rule(
            rule_id="OBS-002",
            contract="OBSERVABILITY",
            severity="HIGH",
            message="Engine must not call logging.basicConfig().",
            remediation="Use a module logger and leave configuration to the host runtime.",
            include_globs=("engine/**/*.py",),
            regex=r"\blogging\.basicConfig\s*\(",
        ),
        Rule(
            rule_id="NAME-001",
            contract="PYDANTIC_YAML_MAPPING",
            severity="HIGH",
            message="Pydantic aliases are banned in engine code.",
            remediation="Use snake_case field names that match YAML keys directly.",
            include_globs=("engine/**/*.py",),
            regex=r"\bField\s*\([^\n]*alias\s*=",
        ),
        Rule(
            rule_id="PKT-001",
            contract="PACKET_TYPE_REGISTRY",
            severity="HIGH",
            message="packet_type values must be lowercase snake_case.",
            remediation="Rename the packet_type value to lowercase snake_case.",
            include_globs=("**/*.py", "**/*.yaml", "**/*.yml", "**/*.md"),
            regex=r"packet_type\s*[:=]\s*[\"'][A-Z]",
        ),
        Rule(
            rule_id="ARCH-004",
            contract="ENGINE_BOUNDARY",
            severity="CRITICAL",
            message="engine/api directory must not exist.",
            remediation="Delete custom HTTP directories from engine.",
            path_exists_forbidden=("engine/api",),
        ),
    ]


def iter_candidate_files(root: Path, explicit_paths: list[Path]) -> Iterable[Path]:
    if explicit_paths:
        for candidate in explicit_paths:
            if candidate.is_file():
                yield candidate.resolve()
            elif candidate.is_dir():
                for path in sorted(candidate.rglob("*")):
                    if path.is_file() and not should_skip(path):
                        yield path.resolve()
        return

    for path in sorted(root.rglob("*")):
        if path.is_file() and not should_skip(path):
            yield path.resolve()


def should_skip(path: Path) -> bool:
    if any(part in DEFAULT_SKIP_DIRS for part in path.parts):
        return True
    return bool(path.suffix and path.suffix not in TEXT_SUFFIXES)


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def first_line_for_regex(content: str, pattern: str, flags: int = re.MULTILINE) -> tuple[int | None, str]:
    match = re.search(pattern, content, flags)
    if not match:
        return None, ""
    line_no = content.count("\n", 0, match.start()) + 1
    line = content.splitlines()[line_no - 1] if content.splitlines() else ""
    return line_no, line.strip()


def scan_file(path: Path, root: Path, rules: list[Rule]) -> list[Violation]:
    rel = rel_path(path, root)
    text = path.read_text(encoding="utf-8", errors="replace")
    violations: list[Violation] = []

    for rule in rules:
        if not rule.applies_to(rel):
            continue

        if rule.regex:
            line_no, evidence = first_line_for_regex(text, rule.regex, rule.regex_flags)
            if line_no is not None:
                violations.append(
                    Violation(
                        file=rel,
                        line=line_no,
                        rule_id=rule.rule_id,
                        contract=rule.contract,
                        severity=rule.severity,
                        message=rule.message,
                        remediation=rule.remediation,
                        evidence=evidence,
                    )
                )

        if rule.required_regex and not re.search(rule.required_regex, text, re.MULTILINE):
            violations.append(
                Violation(
                    file=rel,
                    line=None,
                    rule_id=rule.rule_id,
                    contract=rule.contract,
                    severity=rule.severity,
                    message=rule.required_message or rule.message,
                    remediation=rule.remediation,
                    evidence="required authority anchor not found",
                )
            )

        if rule.pair_forbidden:
            left, right = rule.pair_forbidden
            if re.search(left, text, re.MULTILINE) and re.search(right, text, re.MULTILINE):
                line_no, evidence = first_line_for_regex(text, left, re.MULTILINE)
                violations.append(
                    Violation(
                        file=rel,
                        line=line_no,
                        rule_id=rule.rule_id,
                        contract=rule.contract,
                        severity=rule.severity,
                        message=rule.message,
                        remediation=rule.remediation,
                        evidence=evidence or "forbidden co-occurrence detected",
                    )
                )

    return violations


def scan_repo(root: Path, explicit_paths: list[Path]) -> list[Violation]:
    rules = compile_rules()
    violations: list[Violation] = []

    for rule in rules:
        for forbidden_path in rule.path_exists_forbidden:
            absolute = root / forbidden_path
            if absolute.exists():
                violations.append(
                    Violation(
                        file=forbidden_path,
                        line=None,
                        rule_id=rule.rule_id,
                        contract=rule.contract,
                        severity=rule.severity,
                        message=rule.message,
                        remediation=rule.remediation,
                        evidence="forbidden path exists",
                    )
                )

    seen: set[str] = set()
    for path in iter_candidate_files(root, explicit_paths):
        rel = rel_path(path, root)
        if rel in seen:
            continue
        seen.add(rel)
        violations.extend(scan_file(path, root, rules))

    violations.sort(key=lambda item: (SEVERITY_ORDER.get(item.severity, 99), item.file, item.line or 0, item.rule_id))
    return violations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed CEG cutover contract scanner")
    parser.add_argument("paths", nargs="*", help="Optional file or directory paths to scan")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root. Defaults to current working directory.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args()


def emit_text(violations: list[Violation]) -> int:
    if not violations:
        print("CEG cutover contract scan: no violations.")
        return 0

    print("CEG cutover contract violations detected:\n", file=sys.stderr)
    for violation in violations:
        location = f":{violation.line}" if violation.line is not None else ""
        print(
            f"[{violation.rule_id}] {violation.file}{location} ({violation.severity})\n"
            f"  Contract: {violation.contract}\n"
            f"  Issue: {violation.message}\n"
            f"  Evidence: {violation.evidence}\n"
            f"  Fix: {violation.remediation}\n",
            file=sys.stderr,
        )
    print(f"Total: {len(violations)} violation(s).", file=sys.stderr)
    return 1


def emit_json(violations: list[Violation]) -> int:
    payload = {
        "ok": not violations,
        "violation_count": len(violations),
        "violations": [asdict(item) for item in violations],
    }
    print(json.dumps(payload, indent=2))
    return 0 if not violations else 1


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    explicit_paths = [Path(path).resolve() for path in args.paths]
    violations = scan_repo(root=root, explicit_paths=explicit_paths)
    if args.format == "json":
        return emit_json(violations)
    return emit_text(violations)


if __name__ == "__main__":
    raise SystemExit(main())
