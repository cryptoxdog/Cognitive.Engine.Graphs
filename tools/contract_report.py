#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [tools]
tags: [contracts, verification, report]
owner: engine-team
status: active
--- /L9_META ---

Contract Coverage Matrix Generator.

Reads contract YAML specs from contracts/ and checks which verification
mechanisms exist for each contract: scanner rules, unit tests, integration
tests, and property tests.

Usage:
    python tools/contract_report.py [--format table|csv|json]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def load_contracts(contracts_dir: Path) -> list[dict]:
    """Load all contract YAML specs from the contracts directory."""
    specs = []
    for f in sorted(contracts_dir.glob("contract_*.yaml")):
        with open(f) as fh:
            specs.append(yaml.safe_load(fh))
    return specs


def check_scanner_rules(contract: dict, scanner_path: Path) -> bool:
    """Check if contract_scanner.py has rules for this contract."""
    rules = contract.get("verification", {}).get("scanner_rules", [])
    if not rules:
        return False
    if not scanner_path.exists():
        return False
    scanner_content = scanner_path.read_text()
    return any(rule in scanner_content for rule in rules)


def check_test_exists(contract: dict, repo_root: Path) -> dict[str, bool]:
    """Check which test types exist for this contract."""
    test_path = contract.get("verification", {}).get("test", "")
    result = {"unit": False, "contract": False, "integration": False, "property": False}

    if not test_path:
        return result

    # Check if the specific test file/dir exists
    full_path = repo_root / test_path
    if full_path.exists():
        if "contracts" in test_path:
            result["contract"] = True
        elif "unit" in test_path:
            result["unit"] = True
        elif "integration" in test_path:
            result["integration"] = True
        elif "property" in test_path:
            result["property"] = True
        elif "compliance" in test_path:
            result["unit"] = True  # Count compliance as unit-level

    return result


def generate_report(contracts: list[dict], repo_root: Path) -> list[dict]:
    """Generate the coverage matrix."""
    scanner_path = repo_root / "tools" / "contract_scanner.py"
    rows = []

    for c in contracts:
        cid = c["id"]
        name = c["name"]
        level = c["level"]
        layer = c["layer"]
        has_scanner = check_scanner_rules(c, scanner_path)
        tests = check_test_exists(c, repo_root)

        coverage_count = sum([
            has_scanner,
            tests["unit"],
            tests["contract"],
            tests["integration"],
            tests["property"],
        ])

        rows.append({
            "id": cid,
            "name": name,
            "layer": layer,
            "level": level,
            "scanner": "✓" if has_scanner else "—",
            "unit_test": "✓" if tests["unit"] else "—",
            "contract_test": "✓" if tests["contract"] else "—",
            "integration_test": "✓" if tests["integration"] else "—",
            "property_test": "✓" if tests["property"] else "—",
            "coverage": f"{coverage_count}/5",
        })

    return rows


def print_table(rows: list[dict]) -> None:
    """Print as formatted table."""
    header = f"{'ID':<14} {'Name':<30} {'Layer':<12} {'Level':<6} {'Scan':<5} {'Unit':<5} {'Cntr':<5} {'Intg':<5} {'Prop':<5} {'Cov':<5}"
    print(header)
    print("─" * len(header))
    for r in rows:
        print(
            f"{r['id']:<14} {r['name']:<30} {r['layer']:<12} {r['level']:<6} "
            f"{r['scanner']:<5} {r['unit_test']:<5} {r['contract_test']:<5} "
            f"{r['integration_test']:<5} {r['property_test']:<5} {r['coverage']:<5}"
        )

    # Summary
    total = len(rows)
    with_scanner = sum(1 for r in rows if r["scanner"] == "✓")
    with_contract = sum(1 for r in rows if r["contract_test"] == "✓")
    print(f"\n{'Summary':}")
    print(f"  Total contracts: {total}")
    print(f"  With scanner rules: {with_scanner}/{total}")
    print(f"  With contract tests: {with_contract}/{total}")


def main() -> None:
    repo_root = Path.cwd()
    contracts_dir = repo_root / "contracts"

    if not contracts_dir.exists():
        print(f"No contracts/ directory found at {contracts_dir}", file=sys.stderr)
        sys.exit(1)

    contracts = load_contracts(contracts_dir)
    if not contracts:
        print("No contract YAML files found", file=sys.stderr)
        sys.exit(1)

    fmt = sys.argv[1] if len(sys.argv) > 1 else "table"

    rows = generate_report(contracts, repo_root)

    if fmt == "json":
        print(json.dumps(rows, indent=2))
    elif fmt == "csv":
        keys = rows[0].keys()
        print(",".join(keys))
        for r in rows:
            print(",".join(str(r[k]) for k in keys))
    else:
        print_table(rows)


if __name__ == "__main__":
    main()
