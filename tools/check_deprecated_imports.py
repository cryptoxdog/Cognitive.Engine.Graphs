#!/usr/bin/env python3
# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [tools, governance]
# tags: [deprecated, api, checker, fixer, DomainPackLoader]
# owner: platform
# status: active
# --- /L9_META ---
"""Check and auto-fix deprecated DomainSpecLoader → DomainPackLoader usage.

DomainSpecLoader was renamed to DomainPackLoader in commit 4c0fb5868b.
All callers must migrate to:

    from engine.config.loader import DomainPackLoader
    loader = DomainPackLoader(config_path=str(SPEC_PATH))

Runtime authority: Gate_SDK.
Routing authority: Gate.
Canonical transport: TransportPacket.

Usage:
    # Detect only — exit 1 if any violations found (pre-commit / CI mode):
    python tools/check_deprecated_imports.py --check [PATH ...]

    # Auto-replace in-place — exit 1 if any files were modified (pre-commit
    # fixer mode, exit 0 if nothing to fix):
    python tools/check_deprecated_imports.py --fix [PATH ...]

    # Scan the entire repo:
    python tools/check_deprecated_imports.py --check .
    python tools/check_deprecated_imports.py --fix .
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches: from engine.config.loader import DomainSpecLoader
# Also catches: from engine.config.loader import DomainSpecLoader, OtherThing
# (the replacement handles the simple single-import case; compound imports are
#  flagged and require manual fix with a clear error message)
_IMPORT_PATTERN = re.compile(r"from\s+engine\.config\.loader\s+import\s+([^\n]*\bDomainSpecLoader\b[^\n]*)")

# Matches: DomainSpecLoader(...)  — any call site
_CALL_PATTERN = re.compile(r"\bDomainSpecLoader\(([^)]*)\)")

_SKIP_DIRS = frozenset((".git", "__pycache__", ".venv", "venv", "build", "dist", "node_modules"))
# This file contains the detection pattern as string literals — exclude it from self-scan
_SELF_EXCLUDE = frozenset({"check_deprecated_imports.py"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _replace_import_line(match: re.Match) -> str:  # type: ignore[type-arg]
    """Replace the import symbol, preserving any other symbols on the same line."""
    symbols_raw = match.group(1)
    # Simple case: only DomainSpecLoader imported
    if symbols_raw.strip() == "DomainSpecLoader":
        return "from engine.config.loader import DomainPackLoader"
    # Compound import — replace symbol in-place
    replaced = re.sub(r"\bDomainSpecLoader\b", "DomainPackLoader", symbols_raw)
    return f"from engine.config.loader import {replaced}"


def _replace_call(match: re.Match) -> str:  # type: ignore[type-arg]
    """Rewrite DomainSpecLoader(...) → DomainPackLoader(config_path=str(...))."""
    arg = match.group(1).strip()
    if not arg:
        return "DomainPackLoader()"
    if arg.startswith("config_path="):
        # Already using keyword — just rename the class
        return f"DomainPackLoader({arg})"
    if arg.startswith("str("):
        # DomainSpecLoader(str(SPEC_PATH)) → DomainPackLoader(config_path=str(SPEC_PATH))
        return f"DomainPackLoader(config_path={arg})"
    # Bare positional: DomainSpecLoader(SPEC_PATH) → DomainPackLoader(config_path=str(SPEC_PATH))
    return f"DomainPackLoader(config_path=str({arg}))"


def _collect_py_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            if root.name not in _SELF_EXCLUDE:
                files.append(root)
        elif root.is_dir():
            for p in root.rglob("*.py"):
                if not any(part in _SKIP_DIRS for part in p.parts) and p.name not in _SELF_EXCLUDE:
                    files.append(p)
    return files


def _check_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line_text) for each line containing DomainSpecLoader."""
    violations: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return violations
    for i, line in enumerate(text.splitlines(), 1):
        if "DomainSpecLoader" in line:
            violations.append((i, line.rstrip()))
    return violations


def _fix_file(path: Path) -> bool:
    """Apply all replacements in-place. Returns True if the file was modified."""
    try:
        original = path.read_text(encoding="utf-8")
    except OSError:
        return False
    text = _IMPORT_PATTERN.sub(_replace_import_line, original)
    text = _CALL_PATTERN.sub(_replace_call, text)
    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check / auto-fix deprecated DomainSpecLoader API usage.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python tools/check_deprecated_imports.py --check .\n"
            "  python tools/check_deprecated_imports.py --fix .\n"
            "  python tools/check_deprecated_imports.py --check tests/ engine/\n"
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan (default: current directory)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Detect violations — exit 1 if any found (CI / pre-commit mode)",
    )
    mode.add_argument(
        "--fix",
        action="store_true",
        help="Auto-replace violations in-place — exit 1 if files were modified",
    )
    args = parser.parse_args()

    roots = [Path(p) for p in args.paths]
    files = _collect_py_files(roots)

    # ------------------------------------------------------------------
    # CHECK mode
    # ------------------------------------------------------------------
    if args.check:
        total = 0
        for f in sorted(files):
            violations = _check_file(f)
            for lineno, line in violations:
                print(f"{f}:{lineno}: DomainSpecLoader is deprecated — use DomainPackLoader")
                print(f"  {line}")
                total += 1
        if total:
            print(
                f"\n❌  {total} deprecated DomainSpecLoader reference(s) found.\n"
                "    Auto-fix: python tools/check_deprecated_imports.py --fix .\n"
                "    Migration guide: DomainPackLoader(config_path=str(SPEC_PATH))"
            )
            sys.exit(1)
        print("✅  No deprecated DomainSpecLoader usage found.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # FIX mode
    # ------------------------------------------------------------------
    if args.fix:
        fixed_files: list[Path] = []
        for f in sorted(files):
            if _fix_file(f):
                fixed_files.append(f)
                print(f"  fixed: {f}")
        if fixed_files:
            print(
                f"\n✅  Auto-fixed {len(fixed_files)} file(s).\n"
                "    Review with: git diff\n"
                "    Then: git add <files> and retry your commit."
            )
            sys.exit(1)  # Exit 1 so pre-commit knows to re-stage
        print("✅  No deprecated DomainSpecLoader usage found — nothing to fix.")
        sys.exit(0)


if __name__ == "__main__":
    main()
