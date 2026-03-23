#!/usr/bin/env python3
"""
Cursor Mistake Checker — Leverages L9's MistakePrevention Engine
================================================================

This script allows Cursor to check content against L9's mistake prevention
rules before execution.

Usage:
    python scripts/cursor_check_mistakes.py "content to check"
    python scripts/cursor_check_mistakes.py --file path/to/file.py
    echo "content" | python scripts/cursor_check_mistakes.py --stdin

Examples:
    python scripts/cursor_check_mistakes.py "/Users/ib-mac/Library/Application"
    python scripts/cursor_check_mistakes.py --file generated/api/client.py

Exit codes:
    0 — No violations found
    1 — Violations found but not blocking
    2 — CRITICAL violations found (would be blocked)
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Check Mistakes",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-06T19:43:29Z",
    "updated_at": "2026-01-07T13:35:58Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "cursor_check_mistakes",
    "type": "cli",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": [],
        "memory_layers": [],
        "imported_by": [],
    },
}
# ============================================================================

import argparse
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Add L9 root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.governance.mistake_prevention import Violation, create_mistake_prevention


def format_violation(v: Violation) -> str:
    """Format a violation for display."""
    icon = "🚫" if v.blocked else "⚠️"
    return f"""
{icon} [{v.severity.upper()}] {v.name} (Rule: {v.rule_id})
   Match: "{v.match}"
   Prevention: {v.prevention}
   Blocked: {"YES" if v.blocked else "no"}
"""


def main():
    """
    Checks content against L9's mistake prevention rules to ensure code correctness and adherence to best practices.

    Args:
        content: Optional inline content to be checked.
        file: Optional path to a file containing content to be validated.

    Returns:
        None

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    parser = argparse.ArgumentParser(description="Check content against L9 mistake prevention rules")
    parser.add_argument(
        "content",
        nargs="?",
        help="Content to check (inline)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="File to check",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read content from stdin",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show rule statistics",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="List all rules",
    )

    args = parser.parse_args()

    engine = create_mistake_prevention()

    # List rules mode
    if args.list_rules:
        logger.info("L9 Mistake Prevention Rules:")
        logger.info("-" * 60)
        for rule in engine.rules:
            logger.info(f"  {rule.id}: {rule.name} [{rule.severity.value.upper()}]")
            logger.info(f"       Pattern: {rule.pattern[:50]}...")
            logger.info(f"       Prevention: {rule.prevention}")
            logger.info()
        return 0

    # Stats mode
    if args.stats:
        stats = engine.get_stats()
        logger.info("L9 Mistake Prevention Statistics:")
        logger.info(f"  Total rules: {stats['total_rules']}")
        logger.info(f"  Rules triggered: {stats['rules_triggered']}")
        logger.info(f"  Total occurrences: {stats['total_occurrences']}")
        if stats["top_violations"]:
            logger.info("  Top violations:")
            for rule_id, name, count in stats["top_violations"]:
                logger.info(f"    - {rule_id}: {name} ({count}x)")
        return 0

    # Get content to check
    content = ""
    if args.stdin:
        content = sys.stdin.read()
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.info(f"❌ File not found: {args.file}", file=sys.stderr)
            return 1
        content = file_path.read_text()
    elif args.content:
        content = args.content
    else:
        parser.print_help()
        return 1

    # Check content
    allowed, violations = engine.enforce(content)

    if not violations:
        logger.info("✅ No mistake patterns detected")
        return 0

    # Report violations
    logger.info(f"\n{'=' * 60}")
    logger.info(f"L9 MISTAKE CHECK — {len(violations)} violation(s) found")
    logger.info(f"{'=' * 60}")

    for v in violations:
        logger.info(format_violation(v))

    logger.info(f"{'=' * 60}")
    if not allowed:
        logger.info("🚫 BLOCKED: Critical violations would prevent execution")
        return 2
    logger.info("⚠️  WARNINGS: Non-blocking violations detected")
    return 1


if __name__ == "__main__":
    sys.exit(main())

# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-001",
    "governance_level": "critical",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": ["core.governance.mistake_prevention"],
    "tags": [
        "agent-execution",
        "api",
        "cli",
        "event-driven",
        "filesystem",
        "intelligence",
        "logging",
    ],
    "keywords": ["check", "cursor", "format", "mistakes", "violation"],
    "business_value": "This script allows Cursor to check content against L9's mistake prevention rules before execution. p",
    "last_modified": "2026-01-07T13:35:58Z",
    "modified_by": "L9_Codegen_Engine",
    "change_summary": "Initial generation with DORA compliance",
}
# ============================================================================
# L9 DORA BLOCK - AUTO-UPDATED - DO NOT EDIT
# Runtime execution trace - updated automatically on every execution
# ============================================================================
__l9_trace__ = {
    "trace_id": "",
    "task": "",
    "timestamp": "",
    "patterns_used": [],
    "graph": {"nodes": [], "edges": []},
    "inputs": {},
    "outputs": {},
    "metrics": {"confidence": "", "errors_detected": [], "stability_score": ""},
}
# ============================================================================
# END L9 DORA BLOCK
# ============================================================================
