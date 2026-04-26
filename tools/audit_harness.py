#!/usr/bin/env python3
"""Cutover audit harness for CEG.

Strict mode only. Runs the cutover toolchain in deterministic order and fails
closed on critical or high findings.

Each tool is loaded as a Python module via importlib — no subprocess calls.
This avoids spawning child processes and eliminates the S603 security class
of issues entirely.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _load_tool_module(name: str, tools_dir: Path) -> types.ModuleType:
    """Load a Python tool module from tools_dir without modifying sys.path."""
    file_path = tools_dir / f"{name}.py"
    if not file_path.exists():
        msg = f"Tool module not found: {file_path}"
        raise FileNotFoundError(msg)
    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec is None or spec.loader is None:
        msg = f"Cannot create module spec for {file_path}"
        raise ImportError(msg)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _count_severity(items: list[Any]) -> dict[str, int]:
    """Count findings by severity from a list of dataclass instances."""
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": len(items)}
    for item in items:
        sev = str(getattr(item, "severity", "")).upper()
        key = sev.lower()
        if key in counts:
            counts[key] += 1
    return counts


def _step_contract_scanner(tools_dir: Path, repo_root: Path, out_dir: Path) -> tuple[dict[str, Any], int, int]:
    cs = _load_tool_module("contract_scanner", tools_dir)
    violations: list[Any] = cs.scan_repo(root=repo_root, explicit_paths=[])
    (out_dir / "contract_scanner.json").write_text(
        json.dumps(
            {"ok": not violations, "violation_count": len(violations), "violations": [asdict(v) for v in violations]},
            indent=2,
        ),
        encoding="utf-8",
    )
    counts = _count_severity(violations)
    record: dict[str, Any] = {
        "name": "contract_scanner",
        "returncode": 0 if not violations else 1,
        "counts": counts,
    }
    return record, counts["critical"], counts["high"]


def _step_audit_engine(tools_dir: Path, repo_root: Path, out_dir: Path) -> tuple[dict[str, Any], int, int]:
    ae = _load_tool_module("audit_engine", tools_dir)
    rules_path = repo_root / "tools" / "audit_rules.yaml"
    findings: list[Any]
    audit_summary: dict[str, Any]
    findings, audit_summary = ae.run_audit(repo_root, rules_path if rules_path.exists() else None)
    ae.write_artifacts(repo_root, findings, audit_summary)
    (out_dir / "audit_engine.json").write_text(
        json.dumps(
            {"generated_at": ae.now_iso(), "summary": audit_summary, "findings": [asdict(f) for f in findings]},
            indent=2,
        ),
        encoding="utf-8",
    )
    counts = _count_severity(findings)
    record: dict[str, Any] = {
        "name": "audit_engine",
        "returncode": int(audit_summary.get("exit_code", 0)),
        "counts": counts,
    }
    return record, counts["critical"], counts["high"]


def _step_spec_extract(tools_dir: Path, repo_root: Path, out_dir: Path) -> dict[str, Any]:
    se = _load_tool_module("spec_extract", tools_dir)
    features: list[Any] = se.run_extract(repo_root)
    se.write_outputs(repo_root, features)
    (out_dir / "spec_extract.json").write_text(json.dumps([asdict(f) for f in features], indent=2), encoding="utf-8")
    missing = sum(1 for f in features if getattr(f, "status", "") == "MISSING")
    return {"name": "spec_extract", "returncode": 0, "counts": {"missing": missing, "total": len(features)}}


def _step_contract_report(tools_dir: Path, repo_root: Path, out_dir: Path) -> dict[str, Any]:
    cr = _load_tool_module("contract_report", tools_dir)
    rows: list[Any] = cr.run_report(repo_root)
    cr.write_outputs(repo_root, rows)
    (out_dir / "contract_report.json").write_text(json.dumps([asdict(r) for r in rows], indent=2), encoding="utf-8")
    impacted = sum(1 for r in rows if getattr(r, "cutover_impacted", False))
    return {"name": "contract_report", "returncode": 0, "counts": {"impacted": impacted, "total": len(rows)}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict cutover audit harness")
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("--tools-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    tools_dir = (args.tools_dir or Path(__file__).resolve().parent).resolve()
    out_dir = (args.out_dir or repo_root / ".cutover_audit").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"repo_root": str(repo_root), "steps": [], "status": "PASS"}
    max_critical = 0
    max_high = 0

    rec1, c1, h1 = _step_contract_scanner(tools_dir, repo_root, out_dir)
    summary["steps"].append(rec1)
    max_critical = max(max_critical, c1)
    max_high = max(max_high, h1)

    rec2, c2, h2 = _step_audit_engine(tools_dir, repo_root, out_dir)
    summary["steps"].append(rec2)
    max_critical = max(max_critical, c2)
    max_high = max(max_high, h2)

    summary["steps"].append(_step_spec_extract(tools_dir, repo_root, out_dir))
    summary["steps"].append(_step_contract_report(tools_dir, repo_root, out_dir))

    if max_critical > 0 or max_high > 0 or any(s["returncode"] != 0 for s in summary["steps"]):
        summary["status"] = "FAIL"

    summary["critical"] = max_critical
    summary["high"] = max_high

    summary_path = out_dir / "audit_harness_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    markdown_lines = [
        "# CEG Strict Cutover Audit",
        "",
        f"- repo_root: `{repo_root}`",
        f"- status: **{summary['status']}**",
        f"- critical: **{summary['critical']}**",
        f"- high: **{summary['high']}**",
        "",
        "## Steps",
    ]
    for item in summary["steps"]:
        counts = item.get("counts", {})
        markdown_lines.extend(
            [
                f"### {item['name']}",
                f"- returncode: `{item['returncode']}`",
                f"- critical: `{counts.get('critical', 0)}`",
                f"- high: `{counts.get('high', 0)}`",
                f"- medium: `{counts.get('medium', 0)}`",
                f"- low: `{counts.get('low', 0)}`",
                "",
            ]
        )

    (out_dir / "audit_harness_summary.md").write_text("\n".join(markdown_lines), encoding="utf-8")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
