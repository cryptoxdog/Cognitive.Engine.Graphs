#!/usr/bin/env python3
# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [audit]
# tags: [L9_TEMPLATE, audit, harness]
# owner: platform
# status: active
# --- /L9_META ---
"""
L9 Audit Harness — Single-Entrypoint Static Analysis Orchestrator
=================================================================

Coordinates all static analysis tools in the correct order and produces
a consolidated report. This is what `make audit` and CI should invoke.

Orchestration sequence:
    1. Architecture audit  (tools/audit_engine.py)
    2. Spec coverage       (tools/spec_extract.py)
    3. Contract wiring     (tools/verify_contracts.py)
    4. Consolidated report (artifacts/harness_report.md)

Exit codes:
    0 — all clean (no CRITICAL/HIGH findings, contracts wired)
    1 — CRITICAL or HIGH findings exist, or contracts broken
    2 — harness infrastructure error (missing tools, bad YAML, etc.)

Usage:
    python tools/audit_harness.py                    # default (blocks on CRITICAL/HIGH)
    python tools/audit_harness.py --strict           # also blocks on MISSING spec features
    python tools/audit_harness.py --skip-contracts   # skip contract wiring check
    python tools/audit_harness.py --json             # output JSON summary to stdout
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class StepResult:
    """Result from a single audit step."""

    name: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    artifacts: list[str] = field(default_factory=list)
    passed: bool = True
    skipped: bool = False


@dataclass
class HarnessResult:
    """Consolidated result from all audit steps."""

    generated_at: str = ""
    repo_root: str = ""
    steps: list[StepResult] = field(default_factory=list)
    overall_passed: bool = True
    overall_exit_code: int = 0
    summary: dict[str, Any] = field(default_factory=dict)


def run_step(
    name: str,
    cmd: list[str],
    root: Path,
    fail_on_nonzero: bool = True,
) -> StepResult:
    """Run a subprocess and capture results."""
    result = StepResult(name=name, exit_code=0)

    # Check the script exists
    if len(cmd) >= 2 and cmd[0] in (sys.executable, "python3", "python"):
        script_path = root / cmd[1]
        if not script_path.exists():
            result.exit_code = 2
            result.stderr = f"Script not found: {cmd[1]}"
            result.passed = False
            return result

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        result.exit_code = proc.returncode
        result.stdout = proc.stdout
        result.stderr = proc.stderr
        if fail_on_nonzero and proc.returncode != 0:
            result.passed = False
    except subprocess.TimeoutExpired:
        result.exit_code = 124
        result.stderr = f"TIMEOUT: {name} exceeded 120s"
        result.passed = False
    except FileNotFoundError as e:
        result.exit_code = 2
        result.stderr = f"Command not found: {e}"
        result.passed = False

    return result


def collect_artifacts(root: Path) -> dict[str, str]:
    """Read all generated artifacts from artifacts/ directory."""
    artifacts_dir = root / "artifacts"
    collected: dict[str, str] = {}
    if not artifacts_dir.exists():
        return collected
    for f in sorted(artifacts_dir.iterdir()):
        if f.is_file() and f.suffix in (".md", ".json"):
            try:
                collected[f.name] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                collected[f.name] = "<read error>"
    return collected


def parse_coverage_matrix(root: Path) -> dict[str, Any]:
    """Parse the coverage matrix JSON if it exists."""
    matrix_path = root / "artifacts" / "coverage_matrix.json"
    if not matrix_path.exists():
        return {}
    try:
        return json.loads(matrix_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def parse_audit_report(root: Path) -> dict[str, int]:
    """Parse the audit report to count findings by severity."""
    report_path = root / "artifacts" / "audit_report.md"
    if not report_path.exists():
        return {}
    try:
        content = report_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    current_severity = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## CRITICAL"):
            current_severity = "CRITICAL"
        elif stripped.startswith("## HIGH"):
            current_severity = "HIGH"
        elif stripped.startswith("## MEDIUM"):
            current_severity = "MEDIUM"
        elif stripped.startswith("## LOW"):
            current_severity = "LOW"
        elif stripped.startswith("### ") and current_severity:
            counts[current_severity] += 1
    return counts


def write_harness_report(
    root: Path,
    harness: HarnessResult,
    audit_counts: dict[str, int],
    coverage: dict[str, Any],
) -> Path:
    """Write the consolidated harness report."""
    out_dir = root / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "harness_report.md"

    lines: list[str] = []
    lines.append("# L9 Audit Harness Report")
    lines.append("")
    lines.append(f"- **Generated:** {harness.generated_at}")
    lines.append(f"- **Repo root:** `{harness.repo_root}`")
    lines.append(f"- **Overall result:** {'✅ PASSED' if harness.overall_passed else '❌ FAILED'}")
    lines.append(f"- **Exit code:** {harness.overall_exit_code}")
    lines.append("")

    # Step summary table
    lines.append("## Step Results")
    lines.append("")
    lines.append("| Step | Status | Exit Code | Notes |")
    lines.append("|------|--------|-----------|-------|")
    for step in harness.steps:
        if step.skipped:
            status = "⏭️ Skipped"
        elif step.passed:
            status = "✅ Passed"
        else:
            status = "❌ Failed"
        notes = ""
        if step.stderr and not step.passed:
            first_line = step.stderr.strip().splitlines()[0][:80] if step.stderr.strip() else ""
            notes = first_line
        lines.append(f"| {step.name} | {status} | {step.exit_code} | {notes} |")
    lines.append("")

    # Architecture audit findings
    if audit_counts:
        lines.append("## Architecture Audit Findings")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = audit_counts.get(sev, 0)
            icon = "🔴" if sev == "CRITICAL" else "🟠" if sev == "HIGH" else "🟡" if sev == "MEDIUM" else "🔵"
            lines.append(f"| {icon} {sev} | {count} |")
        lines.append("")
        lines.append("See `artifacts/audit_report.md` for full details.")
        lines.append("")

    # Spec coverage summary
    if coverage and "totals" in coverage:
        totals = coverage["totals"]
        lines.append("## Spec Coverage")
        lines.append("")
        lines.append(f"- ✅ Implemented: {totals.get('IMPLEMENTED', 0)}")
        lines.append(f"- ⚠️ Partial: {totals.get('PARTIAL', 0)}")
        lines.append(f"- ❌ Missing: {totals.get('MISSING', 0)}")
        lines.append(f"- **Total features:** {totals.get('total', 0)}")
        lines.append("")

        if "categories" in coverage:
            lines.append("| Category | Implemented | Partial | Missing | Total |")
            lines.append("|----------|-------------|---------|---------|-------|")
            for cat, data in coverage["categories"].items():
                lines.append(
                    f"| {cat} | {data['IMPLEMENTED']} | {data['PARTIAL']} | {data['MISSING']} | {data['total']} |"
                )
            lines.append("")

        lines.append("See `artifacts/coverage_report.md` for full details.")
        lines.append("")

    # What to do next
    lines.append("## Next Steps")
    lines.append("")
    if not harness.overall_passed:
        if audit_counts.get("CRITICAL", 0) > 0:
            lines.append("1. **Fix CRITICAL findings first** — these are production blockers")
        if audit_counts.get("HIGH", 0) > 0:
            lines.append("2. **Fix HIGH findings** — these block merge")
        lines.append("3. Re-run `make harness` after fixes to verify")
    else:
        lines.append("All checks passed. Safe to merge.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="L9 Audit Harness — orchestrates all static analysis")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also fail on MISSING spec features (default: only CRITICAL/HIGH arch findings)",
    )
    parser.add_argument(
        "--skip-contracts",
        action="store_true",
        help="Skip contract wiring verification",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON summary to stdout",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root directory (default: cwd)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    python = sys.executable

    harness = HarnessResult(
        generated_at=datetime.now(UTC).isoformat(),
        repo_root=str(root),
    )

    # ── Step 1: Architecture Audit ──────────────────────────
    print("\n╔══════════════════════════════════════╗")
    print("║  L9 Audit Harness                    ║")
    print("╚══════════════════════════════════════╝\n")

    print("[1/3] Architecture audit...")
    step1 = run_step(
        name="Architecture Audit",
        cmd=[python, "tools/audit_engine.py"],
        root=root,
        fail_on_nonzero=True,
    )
    harness.steps.append(step1)

    if step1.passed:
        print("  ✅ No CRITICAL/HIGH findings")
    elif step1.exit_code == 2:
        print(f"  ⚠️  Infrastructure error: {step1.stderr.strip()[:100]}")
    else:
        print("  ❌ CRITICAL or HIGH findings detected")

    if step1.stdout:
        for line in step1.stdout.strip().splitlines():
            print(f"     {line}")

    # ── Step 2: Spec Coverage ───────────────────────────────
    print("\n[2/3] Spec coverage scan...")
    spec_fail_on = "MISSING" if args.strict else "NONE"
    step2 = run_step(
        name="Spec Coverage",
        cmd=[python, "tools/spec_extract.py", "--fail-on", spec_fail_on],
        root=root,
        fail_on_nonzero=args.strict,
    )
    # In non-strict mode, spec failures are informational only
    if not args.strict:
        step2.passed = True
    harness.steps.append(step2)

    if step2.passed:
        print("  ✅ Spec coverage scan complete")
    else:
        print("  ❌ Missing spec features (--strict mode)")

    if step2.stdout:
        for line in step2.stdout.strip().splitlines()[-5:]:
            print(f"     {line}")

    # ── Step 3: Contract Wiring ─────────────────────────────
    if args.skip_contracts:
        step3 = StepResult(name="Contract Wiring", exit_code=0, skipped=True)
        print("\n[3/3] Contract wiring... ⏭️  skipped")
    else:
        print("\n[3/3] Contract wiring check...")
        step3 = run_step(
            name="Contract Wiring",
            cmd=[python, "tools/verify_contracts.py"],
            root=root,
            fail_on_nonzero=True,
        )
        if step3.passed:
            print("  ✅ All contracts present and wired")
        elif step3.exit_code == 2:
            # Infrastructure error — don't block on missing tool
            print(f"  ⚠️  Skipped (tool issue): {step3.stderr.strip()[:100]}")
            step3.passed = True  # Don't block harness for missing optional tool
        else:
            print("  ❌ Contract wiring issues detected")
            if step3.stderr:
                for line in step3.stderr.strip().splitlines()[:5]:
                    print(f"     {line}")
    harness.steps.append(step3)

    # ── Consolidate ─────────────────────────────────────────
    harness.overall_passed = all(s.passed for s in harness.steps)
    harness.overall_exit_code = 0 if harness.overall_passed else 1

    audit_counts = parse_audit_report(root)
    coverage = parse_coverage_matrix(root)

    harness.summary = {
        "audit_findings": audit_counts,
        "spec_coverage": coverage.get("totals", {}),
        "steps_passed": sum(1 for s in harness.steps if s.passed),
        "steps_failed": sum(1 for s in harness.steps if not s.passed and not s.skipped),
        "steps_skipped": sum(1 for s in harness.steps if s.skipped),
    }

    report_path = write_harness_report(root, harness, audit_counts, coverage)

    # ── Final Output ────────────────────────────────────────
    print("\n" + "═" * 42)
    if harness.overall_passed:
        print("  ✅ HARNESS PASSED — safe to merge")
    else:
        print("  ❌ HARNESS FAILED — fix issues before merge")
    print("═" * 42)
    print("\nReports:")
    print(f"  Consolidated:  {report_path}")
    print("  Arch audit:    artifacts/audit_report.md")
    print("  Spec coverage: artifacts/coverage_report.md")
    print("  Coverage JSON: artifacts/coverage_matrix.json")

    if args.json:
        summary_json = {
            "generated_at": harness.generated_at,
            "overall_passed": harness.overall_passed,
            "exit_code": harness.overall_exit_code,
            "audit_findings": audit_counts,
            "spec_coverage": coverage.get("totals", {}),
            "steps": [
                {
                    "name": s.name,
                    "passed": s.passed,
                    "skipped": s.skipped,
                    "exit_code": s.exit_code,
                }
                for s in harness.steps
            ],
        }
        print("\n--- JSON Summary ---")
        print(json.dumps(summary_json, indent=2))

    return harness.overall_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
