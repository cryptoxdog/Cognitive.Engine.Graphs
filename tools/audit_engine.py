#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [audit]
tags: [cutover, audit, compliance, reporting]
owner: platform
status: active
--- /L9_META ---

Cutover audit engine for Cognitive.Engine.Graphs.

This audit engine does three things:
1. Runs the fail-closed declarative audit rules in tools/audit_rules.yaml
2. Runs tools/contract_scanner.py in JSON mode
3. Produces human and machine-readable artifacts grouped by cutover risk
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import types
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

YAML_IMPORT_ERROR: Exception | None = None
try:
    import yaml  # type: ignore[import-untyped]
except Exception as exc:  # pragma: no cover - import guard
    yaml = None
    YAML_IMPORT_ERROR = exc


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
CATEGORY_ORDER = {
    "runtime_authority": 0,
    "routing_authority": 1,
    "transport_authority": 2,
    "compatibility_misuse": 3,
    "split_brain": 4,
    "chassis_drift": 5,
    "security": 6,
    "engine_boundary": 7,
    "general": 8,
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "artifacts",
}
TEXT_SUFFIXES = {".py", ".pyi", ".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".sh"}


@dataclass(slots=True)
class Finding:
    severity: str
    category: str
    rule_id: str
    file: str
    line_start: int | None
    line_end: int | None
    issue: str
    evidence: str
    fix: str
    source: str


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        msg = f"PyYAML not installed: {YAML_IMPORT_ERROR!s}"
        raise RuntimeError(msg)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return bool(path.suffix and path.suffix not in TEXT_SUFFIXES)


def list_matching_files(root: Path, include_globs: list[str], exclude_globs: list[str]) -> list[Path]:
    files: set[Path] = set()
    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        relative = path.relative_to(root)
        if include_globs and not any(relative.match(pattern) for pattern in include_globs):
            continue
        if exclude_globs and any(relative.match(pattern) for pattern in exclude_globs):
            continue
        files.add(path)
    return sorted(files)


def relative_string(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def first_match_line(text: str, pattern: str) -> tuple[int | None, str]:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None, ""
    line_no = text.count("\n", 0, match.start()) + 1
    line = text.splitlines()[line_no - 1] if text.splitlines() else ""
    return line_no, line.strip()


def categorize(rule_id: str) -> str:
    if rule_id.startswith("CUTOVER_RUNTIME"):
        return "runtime_authority"
    if rule_id.startswith("CUTOVER_ROUTING"):
        return "routing_authority"
    if rule_id.startswith("CUTOVER_TRANSPORT"):
        return "transport_authority"
    if "PACKETENVELOPE" in rule_id:
        return "compatibility_misuse"
    if "SPLIT_BRAIN" in rule_id:
        return "split_brain"
    if "CHASSIS" in rule_id:
        return "chassis_drift"
    if rule_id.startswith(("SECURITY", "SEC-")):
        return "security"
    if rule_id.startswith(("ENGINE_BOUNDARY", "ARCH-")):
        return "engine_boundary"
    return "general"


def findings_from_rulebook(root: Path, rulebook: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for rule in rulebook.get("rules", []):
        rule_id = str(rule["id"])
        severity = str(rule["severity"])
        description = str(rule["description"])
        remediation = str(rule["remediation"])
        include_globs = [str(item) for item in rule.get("include_globs", [])]
        exclude_globs = [str(item) for item in rule.get("exclude_globs", [])]

        for forbidden_path in rule.get("forbid_paths", []):
            absolute = root / forbidden_path
            if absolute.exists():
                findings.append(
                    Finding(
                        severity=severity,
                        category=categorize(rule_id),
                        rule_id=rule_id,
                        file=str(forbidden_path),
                        line_start=None,
                        line_end=None,
                        issue=description,
                        evidence="forbidden path exists",
                        fix=remediation,
                        source="audit_rules",
                    )
                )

        files = list_matching_files(root, include_globs, exclude_globs)
        for path in files:
            rel = relative_string(path, root)
            text = path.read_text(encoding="utf-8", errors="replace")

            required_patterns = [str(item) for item in rule.get("require_any_regex", [])]
            if required_patterns and not any(re.search(pattern, text, re.MULTILINE) for pattern in required_patterns):
                findings.append(
                    Finding(
                        severity=severity,
                        category=categorize(rule_id),
                        rule_id=rule_id,
                        file=rel,
                        line_start=None,
                        line_end=None,
                        issue=str(rule.get("fail_message", description)),
                        evidence="required anchor not found",
                        fix=remediation,
                        source="audit_rules",
                    )
                )

            for pattern in rule.get("forbid_regex", []):
                line_no, evidence = first_match_line(text, str(pattern))
                if line_no is not None:
                    findings.append(
                        Finding(
                            severity=severity,
                            category=categorize(rule_id),
                            rule_id=rule_id,
                            file=rel,
                            line_start=line_no,
                            line_end=line_no,
                            issue=description,
                            evidence=evidence,
                            fix=remediation,
                            source="audit_rules",
                        )
                    )

            pair = rule.get("forbid_pair_regex", [])
            if (
                len(pair) == 2
                and re.search(str(pair[0]), text, re.MULTILINE)
                and re.search(str(pair[1]), text, re.MULTILINE)
            ):
                line_no, evidence = first_match_line(text, str(pair[0]))
                findings.append(
                    Finding(
                        severity=severity,
                        category=categorize(rule_id),
                        rule_id=rule_id,
                        file=rel,
                        line_start=line_no,
                        line_end=line_no,
                        issue=description,
                        evidence=evidence or "forbidden co-occurrence detected",
                        fix=remediation,
                        source="audit_rules",
                    )
                )

    return findings


def _load_contract_scanner(root: Path) -> types.ModuleType:
    """Load contract_scanner.py as a Python module without modifying sys.path or spawning a process."""
    candidates = [
        Path(__file__).resolve().parent / "contract_scanner.py",
        root / "tools" / "contract_scanner.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("contract_scanner", candidate)
            if spec is not None and spec.loader is not None:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
    msg = "contract_scanner.py not found (searched sibling dir and root/tools/)"
    raise FileNotFoundError(msg)


def findings_from_contract_scanner(root: Path) -> list[Finding]:
    cs = _load_contract_scanner(root)
    violations: list[Any] = cs.scan_repo(root=root, explicit_paths=[])
    return [
        Finding(
            severity=str(v.severity),
            category=categorize(str(v.rule_id)),
            rule_id=str(v.rule_id),
            file=str(v.file),
            line_start=v.line,
            line_end=v.line,
            issue=str(v.message),
            evidence=str(getattr(v, "evidence", "")),
            fix=str(v.remediation),
            source="contract_scanner",
        )
        for v in violations
    ]


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    unique: dict[tuple[Any, ...], Finding] = {}
    for finding in findings:
        key = (
            finding.rule_id,
            finding.file,
            finding.line_start,
            finding.issue,
            finding.source,
        )
        unique[key] = finding
    return sorted(
        unique.values(),
        key=lambda item: (
            SEVERITY_ORDER.get(item.severity, 99),
            CATEGORY_ORDER.get(item.category, 99),
            item.file,
            item.line_start or 0,
            item.rule_id,
        ),
    )


def summarize(findings: list[Finding]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "totals": dict.fromkeys(SEVERITY_ORDER, 0),
        "categories": defaultdict(lambda: dict.fromkeys(SEVERITY_ORDER, 0)),
    }
    for finding in findings:
        summary["totals"][finding.severity] += 1
        summary["categories"][finding.category][finding.severity] += 1
    summary["categories"] = dict(summary["categories"])
    summary["exit_code"] = 1 if summary["totals"]["CRITICAL"] or summary["totals"]["HIGH"] else 0
    return summary


def write_artifacts(root: Path, findings: list[Finding], summary: dict[str, Any]) -> None:
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    json_payload = {
        "generated_at": now_iso(),
        "summary": summary,
        "findings": [asdict(finding) for finding in findings],
    }
    (artifacts / "audit_findings.json").write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# CEG Cutover Audit Report")
    lines.append("")
    lines.append(f"- Generated: {json_payload['generated_at']}")
    lines.append(f"- CRITICAL: {summary['totals']['CRITICAL']}")
    lines.append(f"- HIGH: {summary['totals']['HIGH']}")
    lines.append(f"- MEDIUM: {summary['totals']['MEDIUM']}")
    lines.append(f"- LOW: {summary['totals']['LOW']}")
    lines.append("")

    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.category].append(finding)

    for category in sorted(grouped, key=lambda item: CATEGORY_ORDER.get(item, 99)):
        lines.append(f"## {category.replace('_', ' ').title()}")
        lines.append("")
        for finding in grouped[category]:
            location = f"{finding.file}:{finding.line_start}" if finding.line_start else finding.file
            lines.append(f"### [{finding.rule_id}] {location}")
            lines.append(f"- Severity: {finding.severity}")
            lines.append(f"- Source: {finding.source}")
            lines.append(f"- Issue: {finding.issue}")
            lines.append(f"- Evidence: `{finding.evidence}`")
            lines.append(f"- Fix: {finding.fix}")
            lines.append("")
    (artifacts / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_audit(root: Path, rules_path: Path | None = None) -> tuple[list[Finding], dict[str, Any]]:
    """Public API: run the full audit and return (findings, summary) without writing artifacts."""
    effective_rules = rules_path if rules_path is not None else root / "tools" / "audit_rules.yaml"
    rulebook = load_yaml(effective_rules)
    all_findings = findings_from_rulebook(root, rulebook)
    all_findings.extend(findings_from_contract_scanner(root))
    normalized = dedupe_findings(all_findings)
    summary = summarize(normalized)
    return normalized, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CEG cutover audit engine")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--rules", default="tools/audit_rules.yaml", help="Audit rules path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    rules_path = root / args.rules
    if not rules_path.exists():
        print(f"Missing audit rules file: {rules_path}", file=sys.stderr)
        return 2

    try:
        rulebook = load_yaml(rules_path)
        findings = findings_from_rulebook(root, rulebook)
        findings.extend(findings_from_contract_scanner(root))
    except Exception as exc:
        print(f"Audit engine failed: {exc}", file=sys.stderr)
        return 2

    normalized = dedupe_findings(findings)
    summary = summarize(normalized)
    write_artifacts(root, normalized, summary)

    print(json.dumps({"summary": summary, "finding_count": len(normalized)}, indent=2))
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
