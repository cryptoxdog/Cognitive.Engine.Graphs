from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:
    yaml = None


L9_TEMPLATE_TAG = "L9_TEMPLATE"


@dataclass
class Finding:
    severity: str
    rule_id: str
    file: str
    line_start: int | None
    line_end: int | None
    issue: str
    evidence: str
    fix: str


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML not installed. Install pyyaml to run audit.")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def list_files(root: Path, include_globs: list[str], exclude_globs: list[str]) -> list[Path]:
    included: set[Path] = set()
    for pat in include_globs:
        included |= set(root.glob(pat)) if "**" not in pat else set(root.rglob(pat.replace("**/", "")))
    excluded: set[Path] = set()
    for pat in exclude_globs:
        excluded |= set(root.glob(pat)) if "**" not in pat else set(root.rglob(pat.replace("**/", "")))
    files = [p for p in included if p.is_file() and p not in excluded]
    return sorted(files)


def snippet_with_lines(text: str, line_no: int, context: int = 3) -> tuple[int, int, str]:
    lines = text.splitlines()
    start = max(1, line_no - context)
    end = min(len(lines), line_no + context)
    block = []
    for i in range(start, end + 1):
        prefix = ">>" if i == line_no else "  "
        block.append(f"{prefix} {i:4d}: {lines[i-1]}")
    return start, end, "\n".join(block)


def find_all_lines(text: str, needle: str) -> list[int]:
    lines = text.splitlines()
    hits = []
    for i, line in enumerate(lines, start=1):
        if needle in line:
            hits.append(i)
    return hits


def find_regex_lines(text: str, pattern: str) -> list[int]:
    rx = re.compile(pattern, re.MULTILINE | re.DOTALL)
    hits = []
    for m in rx.finditer(text):
        idx = text[: m.start()].count("\n") + 1
        hits.append(idx)
    return hits


def ensure_template_manifest(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    manifest = root / "tools" / "l9_template_manifest.yaml"
    if not manifest.exists():
        findings.append(Finding(
            severity="HIGH",
            rule_id="TEMPLATE_MANIFEST_MISSING",
            file=str(manifest),
            line_start=None,
            line_end=None,
            issue="Template manifest missing.",
            evidence="tools/l9_template_manifest.yaml does not exist.",
            fix="Add tools/l9_template_manifest.yaml with L9_TEMPLATE tagging for template files."
        ))
    return findings


def audit_rules(root: Path, rules: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    for rule in rules.get("rules", []):
        rule_id = rule["id"]
        severity = rule["severity"]
        desc = rule["description"]

        forbidden = rule.get("file_exists_forbidden", [])
        for rel in forbidden:
            p = root / rel
            if p.exists():
                findings.append(Finding(
                    severity=severity,
                    rule_id=rule_id,
                    file=str(p),
                    line_start=None,
                    line_end=None,
                    issue=desc,
                    evidence=f"{rel} exists.",
                    fix="Delete this directory/file; engines must not implement custom HTTP surface."
                ))

        include_globs = rule.get("include_globs", [])
        if include_globs:
            exclude_globs = rule.get("exclude_globs", [])
            files = list_files(root, include_globs, exclude_globs)

            patterns = rule.get("patterns", [])
            patterns_regex = rule.get("patterns_regex", [])
            allow_if_contains = rule.get("allow_if_contains", [])

            required_all = rule.get("required_all", [])
            required_any = rule.get("required_any", [])

            for f in files:
                text = read_text(f)

                if required_all:
                    missing = [x for x in required_all if x not in text]
                    if missing:
                        findings.append(Finding(
                            severity=severity,
                            rule_id=rule_id,
                            file=str(f),
                            line_start=None,
                            line_end=None,
                            issue=desc,
                            evidence=f"Missing required tokens: {missing}",
                            fix="Implement required flow anchors or algorithms as per engine contract."
                        ))

                if required_any:
                    if not any(x in text for x in required_any):
                        findings.append(Finding(
                            severity=severity,
                            rule_id=rule_id,
                            file=str(f),
                            line_start=None,
                            line_end=None,
                            issue=desc,
                            evidence=f"None of required-any tokens found: {required_any}",
                            fix="Ensure lifecycle entrypoints reference expected components."
                        ))

                for needle in patterns:
                    for ln in find_all_lines(text, needle):
                        s, e, snip = snippet_with_lines(text, ln)
                        findings.append(Finding(
                            severity=severity,
                            rule_id=rule_id,
                            file=str(f),
                            line_start=s,
                            line_end=e,
                            issue=desc,
                            evidence=snip,
                            fix="Remove banned import/logic; rely on chassis for HTTP/tenancy/auth."
                        ))

                for rx_pat in patterns_regex:
                    hit_lines = find_regex_lines(text, rx_pat)
                    for ln in hit_lines:
                        if allow_if_contains and any(a in text for a in allow_if_contains):
                            continue
                        s, e, snip = snippet_with_lines(text, ln)
                        findings.append(Finding(
                            severity=severity,
                            rule_id=rule_id,
                            file=str(f),
                            line_start=s,
                            line_end=e,
                            issue=desc,
                            evidence=snip,
                            fix="Wrap labels/types with sanitize_label() before Cypher interpolation."
                        ))

    return findings


def group_findings(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for f in findings:
        grouped.setdefault(f.severity, []).append(f)
    for sev in grouped:
        grouped[sev] = sorted(grouped[sev], key=lambda x: (x.file, x.line_start or 0))
    return grouped


def write_report(root: Path, meta: dict[str, Any], grouped: dict[str, list[Finding]]) -> None:
    out_dir = root / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "audit_report.md"

    lines: list[str] = []
    lines.append(f"# L9 Engine Audit Report\n")
    lines.append(f"- Generated: {meta['generated_at']}")
    lines.append(f"- Repo root: `{meta['repo_root']}`")
    lines.append(f"- Template tag: `{L9_TEMPLATE_TAG}`")
    lines.append("")

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        lines.append(f"## {sev}")
        if not grouped.get(sev):
            lines.append("No findings.")
            lines.append("")
            continue

        for f in grouped[sev]:
            loc = ""
            if f.line_start is not None and f.line_end is not None:
                loc = f" (lines {f.line_start}-{f.line_end})"
            lines.append(f"### {f.rule_id}")
            lines.append(f"- File: `{f.file}`{loc}")
            lines.append(f"- Issue: {f.issue}")
            lines.append(f"- Fix: {f.fix}")
            lines.append("")
            lines.append("```")
            lines.append(f.evidence)
            lines.append("```")
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def write_coverage(root: Path, grouped: dict[str, list[Finding]]) -> None:
    out_dir = root / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = out_dir / "coverage_matrix.json"

    summary = {
        "CRITICAL": len(grouped.get("CRITICAL", [])),
        "HIGH": len(grouped.get("HIGH", [])),
        "MEDIUM": len(grouped.get("MEDIUM", [])),
        "LOW": len(grouped.get("LOW", [])),
    }
    coverage_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> int:
    root = Path(".").resolve()
    meta = {"generated_at": now_iso(), "repo_root": str(root)}

    findings = []
    findings += ensure_template_manifest(root)

    rules_path = root / "tools" / "audit_rules.yaml"
    if not rules_path.exists():
        print("ERROR: tools/audit_rules.yaml missing", file=sys.stderr)
        return 2

    rules = load_yaml(rules_path)
    findings += audit_rules(root, rules)

    grouped = group_findings(findings)
    write_report(root, meta, grouped)
    write_coverage(root, grouped)

    critical = len(grouped.get("CRITICAL", []))
    high = len(grouped.get("HIGH", []))

    if critical > 0:
        return 1
    if high > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
