#!/usr/bin/env python3
"""
L9 Contract Files Existence + Wiring Check
Verifies all 20 contract files exist AND are referenced in .cursorrules and CLAUDE.md.
Exit code 1 = missing file or unwired -> blocks CI/merge.
"""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_CONTRACTS = [
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


def main() -> int:
    root = Path.cwd()
    errors: list[str] = []

    for rel in REQUIRED_CONTRACTS:
        path = root / rel
        if not path.is_file():
            errors.append(f"Missing contract file: {rel}")

    # Each contract must be referenced in at least one agent file
    agent_contents: list[tuple[str, str]] = []
    for agent_file in AGENT_FILES:
        path = root / agent_file
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            agent_contents.append((agent_file, content))
        except OSError as e:
            errors.append(f"Cannot read {agent_file}: {e}")

    for rel in REQUIRED_CONTRACTS:
        name = Path(rel).name
        if not any(name in c or rel in c for _f, c in agent_contents):
            errors.append(f"No agent file references contract: {name}")

    if not errors:
        print("L9 contract files: all 20 present and wired.")
        return 0

    print("L9 contract verification failed:\n", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
