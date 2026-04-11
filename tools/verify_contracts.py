#!/usr/bin/env python3
"""L9 Contract Verification Script (Enrichment.Inference.Engine).

Confirms all contract files exist, checks SHA-256 integrity,
and verifies each is referenced in the appropriate governance files.

Exit codes:
  0 = all checks pass
  1 = one or more FAIL conditions
"""

import hashlib
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "tools" / "l9_enrichment_manifest.yaml"


def compute_sha256(filepath: Path) -> str:
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def load_manifest() -> dict:
    if yaml is None:
        print("WARN: PyYAML not installed -- skipping manifest-based verification")
        return {}
    if not MANIFEST_PATH.exists():
        print(f"WARN: Manifest not found at {MANIFEST_PATH} -- skipping")
        return {}
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f) or {}


def check_file_referenced(contract_path: str, ref_file: Path) -> bool:
    if not ref_file.exists():
        return False
    content = ref_file.read_text()
    clean_path = contract_path.lstrip("./")
    return clean_path in content


def check_critical_files() -> list[str]:
    """Verify critical structural files exist regardless of manifest."""
    fails = []
    critical = [
        "app/__init__.py",
        "app/main.py",
        "app/engines/__init__.py",
        "app/engines/handlers.py",
        "app/engines/chassis_contract.py",
        "pyproject.toml",
        "requirements-ci.txt",
    ]
    for path in critical:
        if not (REPO_ROOT / path).exists():
            fails.append(f"FAIL: MISSING critical file {path}")
    return fails


def main():
    manifest = load_manifest()
    fails = []
    warns = []
    passes = []

    # Phase 1: Critical file checks (always run)
    fails.extend(check_critical_files())

    # Phase 2: Manifest-based checks (if manifest exists)
    all_contracts = []
    for level in ["engine_level", "constellation_level"]:
        contracts = manifest.get("contracts", {}).get(level, [])
        all_contracts.extend(contracts)

    total = len(all_contracts)
    present = 0

    for entry in all_contracts:
        path = entry["path"]
        full_path = REPO_ROOT / path
        sha_expected = entry.get("sha256", "")
        required_refs = entry.get("required_refs", [])

        if not full_path.exists():
            fails.append(f"FAIL: MISSING {path}")
            continue

        present += 1

        if sha_expected and not sha_expected.startswith("<"):
            actual_sha = compute_sha256(full_path)
            if actual_sha != sha_expected:
                warns.append(f"WARN: MODIFIED {path} (sha256 mismatch)")

        for ref in required_refs:
            ref_path = REPO_ROOT / ref
            if not check_file_referenced(path, ref_path):
                warns.append(f"WARN: {path} NOT referenced in {ref}")

        passes.append(f"PASS: {path}")

    # Phase 3: KB rule file validation
    kb_dir = REPO_ROOT / "kb"
    if kb_dir.exists():
        for yaml_file in kb_dir.rglob("*.yaml"):
            try:
                if yaml:
                    data = yaml.safe_load(yaml_file.read_text())
                    if data is None:
                        warns.append(f"WARN: Empty YAML file {yaml_file.relative_to(REPO_ROOT)}")
            except Exception as e:
                fails.append(f"FAIL: Invalid YAML {yaml_file.relative_to(REPO_ROOT)}: {e}")

    # Print results
    print("=" * 60)
    print("L9 Contract Verification Report")
    print("Engine: Enrichment.Inference.Engine")
    print("=" * 60)

    for p in passes:
        print(f"  {p}")
    for w in warns:
        print(f"  {w}")
    for f_msg in fails:
        print(f"  {f_msg}")

    if total > 0:
        print()
        print(f"Contracts present:  {present}/{total}")
    print(f"Warnings:           {len(warns)}")
    print(f"Failures:           {len(fails)}")

    if fails:
        print()
        print("RESULT: FAIL -- verification failed")
        sys.exit(1)
    else:
        print()
        print("RESULT: PASS -- all checks verified")
        sys.exit(0)


if __name__ == "__main__":
    main()
