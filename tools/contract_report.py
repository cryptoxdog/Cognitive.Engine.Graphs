#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [audit]
tags: [contracts, reporting, cutover]
owner: platform
status: active
--- /L9_META ---

Contract coverage and cutover impact report for Cognitive.Engine.Graphs.

This report does two jobs:
- measure whether each contract has scanner/test coverage
- show which existing contracts are likely impacted by the Gate_SDK/Gate/TransportPacket cutover
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

YAML_IMPORT_ERROR: Exception | None = None
try:
    import yaml  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - import guard
    yaml = None
    YAML_IMPORT_ERROR = exc


@dataclass(slots=True)
class ContractRow:
    contract_id: str
    name: str
    layer: str
    level: str
    scanner_rules_declared: int
    scanner_rules_present: int
    test_path: str
    test_exists: bool
    cutover_impacted: bool
    impact_reason: str


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        msg = f"PyYAML not installed: {YAML_IMPORT_ERROR!s}"
        raise RuntimeError(msg)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_contracts(contracts_dir: Path) -> list[dict[str, Any]]:
    return [load_yaml(path) for path in sorted(contracts_dir.glob("contract_*.yaml"))]


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


def run_scanner(root: Path) -> dict[str, Any]:
    cs = _load_contract_scanner(root)
    violations: list[Any] = cs.scan_repo(root=root, explicit_paths=[])
    return {
        "ok": not violations,
        "violation_count": len(violations),
        "violations": [
            {
                "rule_id": v.rule_id,
                "severity": v.severity,
                "file": v.file,
                "line": v.line,
                "message": v.message,
                "remediation": v.remediation,
                "evidence": getattr(v, "evidence", ""),
            }
            for v in violations
        ],
    }


def is_cutover_impacted(contract: dict[str, Any]) -> tuple[bool, str]:
    text = json.dumps(contract).lower()
    checks = [
        ("packet", "packet contract likely rewritten for TransportPacket cutover"),
        ("ingress", "ingress semantics likely change under Gate_SDK"),
        ("route", "routing semantics likely change under Gate authority"),
        ("execute", "legacy execute-envelope assumptions likely change"),
        ("chassis", "chassis-first framing likely needs cutover alignment"),
    ]
    for needle, reason in checks:
        if needle in text:
            return True, reason
    return False, "no clear cutover coupling detected"


def build_rows(contracts: list[dict[str, Any]], root: Path, scanner_payload: dict[str, Any]) -> list[ContractRow]:
    scanner_rules_found = {str(item["rule_id"]) for item in scanner_payload.get("violations", [])}
    scanner_source = (root / "tools" / "contract_scanner.py").read_text(encoding="utf-8", errors="replace")
    rows: list[ContractRow] = []

    for contract in contracts:
        verification = contract.get("verification", {})
        declared_rules = [str(item) for item in verification.get("scanner_rules", [])]
        present_count = sum(
            1 for rule_id in declared_rules if rule_id in scanner_source or rule_id in scanner_rules_found
        )
        test_path = str(verification.get("test", ""))
        impacted, reason = is_cutover_impacted(contract)
        rows.append(
            ContractRow(
                contract_id=str(contract.get("id", "UNKNOWN")),
                name=str(contract.get("name", "UNKNOWN")),
                layer=str(contract.get("layer", "UNKNOWN")),
                level=str(contract.get("level", "UNKNOWN")),
                scanner_rules_declared=len(declared_rules),
                scanner_rules_present=present_count,
                test_path=test_path,
                test_exists=bool(test_path and (root / test_path).exists()),
                cutover_impacted=impacted,
                impact_reason=reason,
            )
        )

    return rows


def write_outputs(root: Path, rows: list[ContractRow]) -> None:
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    payload = [asdict(row) for row in rows]
    (artifacts / "contract_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# CEG Contract Coverage and Cutover Impact Report")
    lines.append("")
    lines.append("| Contract | Layer | Level | Scanner | Test | Cutover impacted | Reason |")
    lines.append("|---|---|---|---:|---|---|---|")
    for row in rows:
        scanner_cell = f"{row.scanner_rules_present}/{row.scanner_rules_declared}"
        test_cell = "yes" if row.test_exists else "no"
        impacted = "yes" if row.cutover_impacted else "no"
        lines.append(
            f"| {row.contract_id} {row.name} | {row.layer} | {row.level} | {scanner_cell} | {test_cell} | {impacted} | {row.impact_reason} |"
        )
    (artifacts / "contract_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_report(root: Path, contracts_dir: Path | None = None) -> list[ContractRow]:
    """Public API: return contract rows without writing artifacts or printing."""
    effective_dir = contracts_dir if contracts_dir is not None else root / "contracts"
    contracts = load_contracts(effective_dir)
    scanner_payload = run_scanner(root)
    return build_rows(contracts, root, scanner_payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate contract coverage and cutover impact report")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    contracts_dir = root / "contracts"
    if not contracts_dir.exists():
        print(f"contracts/ directory not found at {contracts_dir}", file=sys.stderr)
        return 2

    try:
        contracts = load_contracts(contracts_dir)
        scanner_payload = run_scanner(root)
    except Exception as exc:
        print(f"contract_report failed: {exc}", file=sys.stderr)
        return 2

    rows = build_rows(contracts, root, scanner_payload)
    write_outputs(root, rows)

    if args.format == "json":
        print(json.dumps([asdict(row) for row in rows], indent=2))
    else:
        for row in rows:
            scanner_cell = f"{row.scanner_rules_present}/{row.scanner_rules_declared}"
            test_cell = "yes" if row.test_exists else "no"
            impacted = "yes" if row.cutover_impacted else "no"
            print(
                f"{row.contract_id:<14} {row.layer:<12} {row.level:<6} scanner={scanner_cell:<5} "
                f"test={test_cell:<3} impacted={impacted:<3} reason={row.impact_reason}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
