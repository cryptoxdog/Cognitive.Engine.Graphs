#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [audit]
tags: [L9_TEMPLATE, audit, deprecation, packet]
owner: platform
status: active
--- /L9_META ---

PacketEnvelope Prohibition Scanner

PacketEnvelope is DEPRECATED and has been superseded by transportPacket.
This script enforces the migration by blocking any usage of PacketEnvelope.

Exit code 1 = violations found = commit/merge blocked.

Usage:
    python tools/check_packet_envelope_prohibited.py [files...]
    python tools/check_packet_envelope_prohibited.py --check .
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
    code: str
    message: str


# Files where PacketEnvelope definition is allowed (canonical locations)
ALLOWED_DEFINITION_FILES = {
    "engine/packet/packet_envelope.py",  # Canonical definition (deprecated, to be removed)
    "l9_core/models.py",  # Legacy models
}

# Directories/files to skip entirely
SKIP_PATTERNS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    "site-packages",
    "docs/",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    "tools/check_packet_envelope_prohibited.py",  # This script
    "tools/contract_scanner.py",  # Contract scanner references it
    ".cursorrules",
    "agents/cursor/",  # Agent rules reference it in documentation
    "current work/",  # Working notes
    "tests/unit/test_packet_bridge.py",  # Tests need to test packet functionality
}


def should_skip(path: Path) -> bool:
    """Check if a path should be skipped."""
    path_str = str(path)
    return any(pattern in path_str for pattern in SKIP_PATTERNS)


def is_allowed_definition_file(path: Path, root: Path) -> bool:
    """Check if this is an allowed file where PacketEnvelope can be defined."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path
    rel_str = str(rel).replace("\\", "/")
    return rel_str in ALLOWED_DEFINITION_FILES


# Patterns to detect PacketEnvelope usage
PATTERNS = [
    # Import patterns
    (re.compile(r"from\s+[\w.]+\s+import\s+.*\bPacketEnvelope\b"), "PE-001", "Import of PacketEnvelope"),
    (re.compile(r"import\s+.*\bPacketEnvelope\b"), "PE-002", "Import of PacketEnvelope"),
    # Type annotation patterns
    (re.compile(r":\s*PacketEnvelope\b"), "PE-003", "Type annotation using PacketEnvelope"),
    (re.compile(r"->\s*PacketEnvelope\b"), "PE-004", "Return type using PacketEnvelope"),
    # Usage patterns
    (re.compile(r"\bPacketEnvelope\s*\("), "PE-005", "Instantiation of PacketEnvelope"),
    (re.compile(r"\bPacketEnvelope\s*\."), "PE-006", "Method/attribute access on PacketEnvelope"),
    # Generic reference (catch-all for non-definition contexts)
    (re.compile(r"(?<!class\s)\bPacketEnvelope\b(?!\s*[:\(])"), "PE-007", "Reference to PacketEnvelope"),
]

# Pattern to detect class definition (allowed only in canonical files)
CLASS_DEFINITION_PATTERN = re.compile(r"^\s*class\s+PacketEnvelope\s*[\(:]")


def scan_file(file_path: Path, content: str, root: Path) -> list[Violation]:
    """Scan a single file for PacketEnvelope violations."""
    violations: list[Violation] = []

    try:
        abs_path = file_path.resolve()
        abs_root = root.resolve()
        rel = abs_path.relative_to(abs_root)
    except ValueError:
        rel = file_path
    rel_str = str(rel).replace("\\", "/")

    is_definition_file = is_allowed_definition_file(file_path, root)
    lines = content.splitlines()

    for i, line in enumerate(lines, start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Skip docstrings (simple heuristic)
        if stripped.startswith(('"""', "'''")):
            continue
        # Skip string literals containing PacketEnvelope (e.g., in error messages)
        if "PacketEnvelope" in line and ('"PacketEnvelope' in line or "'PacketEnvelope" in line):
            continue

        # Check for class definition
        if CLASS_DEFINITION_PATTERN.match(line):
            if not is_definition_file:
                violations.append(
                    Violation(
                        file=rel_str,
                        line=i,
                        code="PE-DEF",
                        message="Class definition of PacketEnvelope (only allowed in canonical files)",
                    )
                )
            continue  # Don't flag definition in allowed files

        # Check other patterns (skip if this is the definition file)
        if is_definition_file:
            continue

        for pattern, code, msg in PATTERNS:
            if pattern.search(line):
                violations.append(
                    Violation(
                        file=rel_str,
                        line=i,
                        code=code,
                        message=msg,
                    )
                )
                break  # Only one violation per line

    return violations


def main() -> int:
    root = Path.cwd()

    # Determine files to scan
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check" and len(sys.argv) > 2:
            # Recursive check from directory
            base = Path(sys.argv[2])
            paths = [p for p in base.rglob("*.py") if not should_skip(p)]
        else:
            # Pre-commit passes filenames
            paths = [Path(p) for p in sys.argv[1:] if p.endswith(".py") and not should_skip(Path(p))]
    else:
        # Default: scan all Python files
        paths = [p for p in root.rglob("*.py") if not should_skip(p)]

    all_violations: list[Violation] = []

    for path in paths:
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        all_violations.extend(scan_file(path, text, root))

    if not all_violations:
        print("✅ PacketEnvelope prohibition check: no violations.")
        return 0

    print("❌ PacketEnvelope PROHIBITED — Use transportPacket instead!\n", file=sys.stderr)
    print("PacketEnvelope has been superseded by transportPacket.", file=sys.stderr)
    print("See: docs/contracts/TRANSPORT_PACKET.md\n", file=sys.stderr)

    for v in all_violations:
        print(f"  [{v.code}] {v.file}:{v.line}", file=sys.stderr)
        print(f"    {v.message}", file=sys.stderr)
        print("    → Replace with: transportPacket\n", file=sys.stderr)

    print(
        f"Total: {len(all_violations)} violation(s). Fix before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
