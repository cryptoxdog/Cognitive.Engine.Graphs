#!/usr/bin/env python3
"""
L9 Lesson Ingestion Script
===========================

Parses repeated-mistakes.md and ingests each lesson into MCP memory
as a separate packet with structured tags, severity, and content.

Reuses:
- Parsing logic from session_startup.py (load_mistake_patterns)
- Write API from cursor_memory_client.py (mcp_call_tool)

Usage:
    python3 agents/cursor/ingest_lessons.py                    # Dry run (default)
    python3 agents/cursor/ingest_lessons.py --dry-run          # Explicit dry run
    python3 agents/cursor/ingest_lessons.py --live             # Actually write to MCP
    python3 agents/cursor/ingest_lessons.py --live --limit 5   # Write first 5 only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

__dora_meta__ = {
    "component_name": "Ingest Lessons",
    "module_version": "1.0.0",
    "created_by": "L9 Agent",
    "created_at": "2026-02-14T00:00:00Z",
    "updated_at": "2026-02-14T00:00:00Z",
    "layer": "operations",
    "domain": "memory_substrate",
    "module_name": "ingest_lessons",
    "type": "script",
    "status": "active",
    "integrates_with": {
        "api_endpoints": ["/mcp/call"],
        "datasources": ["repeated-mistakes.md"],
        "memory_layers": ["semantic_memory", "packet_store"],
        "imported_by": [],
    },
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_LESSONS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".cursor-commands"
    / "learning"
    / "failures"
    / "repeated-mistakes.md"
)

TIER_MAP = {
    "ULTRA_CRITICAL": "ultra-critical",
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}


# ---------------------------------------------------------------------------
# Parser — adapted from session_startup.py load_mistake_patterns()
# ---------------------------------------------------------------------------


def parse_lessons(path: Path) -> list[dict]:
    """
    Parse repeated-mistakes.md into structured lesson dicts.

    Each lesson dict has:
        lesson_id, number, title, severity, tier_tag,
        rule, wrong, right, prevention, mcp_id, content_json
    """
    content = path.read_text(encoding="utf-8")

    # --- Curated lessons (Tier 1-3): have Rule/Wrong/Right structure ---
    curated_pattern = (
        r"### \*\*(\d+)\.\s*(.*?)\*\*\s*([^\n]*?)\n+"
        r"(?:\*\*Rule:\*\*\s*(.*?)\n+)?"
        r"(?:\*\*Wrong:\*\*\s*(.*?)\n+)?"
        r"(?:\*\*Right:\*\*\s*(.*?)\n+)?"
        r"(?:\*\*(?:On violation|Key|Allowed|Forbidden|Banned|Verify|Verification|Checklist|Response protocol|DoD Checklist|The test|Incident|ADR|Benefit|Tools|Example|Exception|Also|Cherry-pick):\*\*\s*.*?\n+)*"
        r"(?:\*\*MCP-ID:\*\*\s*`(.*?)`\s*\n)?"
    )
    curated_matches = re.findall(curated_pattern, content, re.DOTALL)

    # --- Auto-generated lessons (numbered 19+): have Mistake/Impact/Prevention/Rule ---
    auto_pattern = (
        r"### \*\*(\d+)\.\s*(.*?)\*\*\s*\n+"
        r"\*\*Mistake:\*\*\s*(.*?)\n+"
        r"\*\*Impact:\*\*\s*(.*?)\n+"
        r"\*\*Prevention:\*\*\s*(.*?)\n+"
        r"\*\*Rule:\*\*\s*(.*?)\n+"
        r"(?:\*\*Date Added:\*\*\s*(.*?)\n)?"
    )
    auto_matches = re.findall(auto_pattern, content, re.DOTALL)

    lessons: list[dict] = []
    seen_ids: set[str] = set()

    # Process curated lessons
    for match in curated_matches:
        num_str, title, severity_marker, rule, wrong, right, mcp_id = match
        num = int(num_str)
        title_clean = title.strip()

        # Skip success patterns
        if "successful solution" in title_clean.lower():
            continue

        severity = _classify_severity(severity_marker)
        lesson_id = mcp_id.strip() if mcp_id.strip() else f"lesson-{num:03d}"

        if lesson_id in seen_ids:
            lesson_id = f"{lesson_id}-dup"
        seen_ids.add(lesson_id)

        structured = {
            "lesson_id": lesson_id,
            "number": num,
            "title": title_clean,
            "severity": severity,
            "tier_tag": TIER_MAP.get(severity, "medium"),
            "rule": rule.strip() if rule else "",
            "wrong": wrong.strip() if wrong else "",
            "right": right.strip() if right else "",
            "prevention": "",
            "mcp_id": mcp_id.strip() if mcp_id else "",
            "quality": "curated",
        }
        structured["content_json"] = json.dumps(
            {k: v for k, v in structured.items() if v and k != "content_json"},
            indent=2,
        )
        lessons.append(structured)

    # Process auto-generated lessons
    for match in auto_matches:
        num_str, title, mistake, impact, prevention, rule, date_added = match
        num = int(num_str)
        title_clean = title.strip()

        if "successful solution" in title_clean.lower():
            continue

        lesson_id = f"lesson-auto-{num:03d}"
        if lesson_id in seen_ids:
            lesson_id = f"{lesson_id}-dup"
        seen_ids.add(lesson_id)

        # Auto-generated are typically MEDIUM severity
        severity = "MEDIUM"
        if "CRITICAL" in impact.upper():
            severity = "CRITICAL"
        elif "HIGH" in impact.upper():
            severity = "HIGH"

        structured = {
            "lesson_id": lesson_id,
            "number": num,
            "title": title_clean[:80],
            "severity": severity,
            "tier_tag": TIER_MAP.get(severity, "medium"),
            "rule": rule.strip() if rule else "",
            "wrong": mistake.strip() if mistake else "",
            "right": prevention.strip() if prevention else "",
            "prevention": prevention.strip() if prevention else "",
            "mcp_id": "",
            "quality": "auto-generated",
        }
        structured["content_json"] = json.dumps(
            {k: v for k, v in structured.items() if v and k != "content_json"},
            indent=2,
        )
        lessons.append(structured)

    return lessons


def _classify_severity(marker: str) -> str:
    upper = marker.upper()
    if "🚨" in marker or "ULTRA" in upper:
        return "ULTRA_CRITICAL"
    if "🔴" in marker or "CRITICAL" in upper:
        return "CRITICAL"
    if "🟡" in marker or "HIGH" in upper:
        return "HIGH"
    if "🟢" in marker or "MEDIUM" in upper:
        return "MEDIUM"
    return "MEDIUM"


# ---------------------------------------------------------------------------
# Writer — uses cursor_memory_client.py mcp_call_tool
# ---------------------------------------------------------------------------


def write_lesson_to_mcp(lesson: dict) -> dict:
    """Write a single lesson to MCP memory via save_memory tool."""
    # Import here to avoid circular deps and allow dry-run without env vars
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cursor_memory_client import mcp_call_tool

    tags = [
        "governance",
        "repeated-mistake",
        lesson["tier_tag"],
        lesson["lesson_id"],
    ]
    if lesson["quality"] == "curated":
        tags.append("curated")

    content_text = f"LESSON: {lesson['title']}\n"
    if lesson["rule"]:
        content_text += f"RULE: {lesson['rule']}\n"
    if lesson["wrong"]:
        content_text += f"WRONG: {lesson['wrong']}\n"
    if lesson["right"]:
        content_text += f"RIGHT: {lesson['right']}\n"
    content_text += f"SEVERITY: {lesson['severity']}"

    result = mcp_call_tool(
        "save_memory",
        {
            "content": content_text,
            "kind": "lesson",
            "scope": "cursor",
            "tags": tags,
            "importance": 1.0 if lesson["severity"] in ("ULTRA_CRITICAL", "CRITICAL") else 0.8,
            "metadata": {
                "agent": "cursor",
                "domain": "governance",
                "lesson_id": lesson["lesson_id"],
                "severity": lesson["severity"],
                "quality": lesson["quality"],
                "schema_version": "1.0.0",
            },
        },
    )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest repeated-mistakes.md lessons into MCP memory")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually write to MCP memory (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be written without writing (default)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of lessons to process (0 = all)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(DEFAULT_LESSONS_PATH),
        help="Path to repeated-mistakes.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable",
    )

    args = parser.parse_args()

    # --live overrides --dry-run
    is_live = args.live
    lessons_path = Path(args.path)

    if not lessons_path.exists():
        print(f"ERROR: File not found: {lessons_path}")
        sys.exit(1)

    # Parse
    lessons = parse_lessons(lessons_path)

    if args.limit > 0:
        lessons = lessons[: args.limit]

    # Output
    if args.json:
        output = {
            "mode": "LIVE" if is_live else "DRY-RUN",
            "source": str(lessons_path),
            "total_lessons": len(lessons),
            "lessons": lessons,
        }
        print(json.dumps(output, indent=2))
    else:
        mode_label = "🔴 LIVE" if is_live else "🟢 DRY-RUN"
        print(f"\n{'=' * 60}")
        print(f"  L9 Lesson Ingestion — {mode_label}")
        print(f"  Source: {lessons_path}")
        print(f"  Total lessons parsed: {len(lessons)}")
        print(f"{'=' * 60}\n")

        for i, lesson in enumerate(lessons, 1):
            tags = [
                "governance",
                "repeated-mistake",
                lesson["tier_tag"],
                lesson["lesson_id"],
            ]
            if lesson["quality"] == "curated":
                tags.append("curated")

            print(f"  [{i:02d}] {lesson['lesson_id']}")
            print(f"       Title:    {lesson['title'][:60]}")
            print(f"       Severity: {lesson['severity']}")
            print(f"       Quality:  {lesson['quality']}")
            print("       Kind:     lesson")
            print("       Scope:    cursor")
            print(f"       Tags:     {tags}")

            if is_live:
                result = write_lesson_to_mcp(lesson)
                status = "✅" if not result.get("error") else "❌"
                print(f"       Write:    {status} {result}")
            else:
                print("       Write:    [SKIPPED — dry-run]")

            print()

        # Summary
        curated = len([item for item in lessons if item["quality"] == "curated"])
        auto = len([item for item in lessons if item["quality"] == "auto-generated"])
        ultra = len([item for item in lessons if item["severity"] == "ULTRA_CRITICAL"])
        critical = len([item for item in lessons if item["severity"] == "CRITICAL"])

        print(f"  {'─' * 50}")
        print(f"  Summary: {len(lessons)} lessons")
        print(f"    Curated:        {curated}")
        print(f"    Auto-generated: {auto}")
        print(f"    Ultra-critical: {ultra}")
        print(f"    Critical:       {critical}")

        if not is_live:
            print(f"\n  To write for real: python3 {__file__} --live")
        print()


if __name__ == "__main__":
    main()


__dora_footer__ = {
    "component_id": "AGE-ING-001",
    "governance_level": "standard",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": ["structlog", "cursor_memory_client"],
    "tags": ["ingestion", "lessons", "memory"],
    "keywords": ["ingest", "lesson", "repeated-mistakes", "mcp"],
    "business_value": "Ingests governance lessons into semantic memory for retrieval",
    "last_modified": "2026-02-14T00:00:00Z",
    "modified_by": "L9_Agent",
    "change_summary": "Initial creation — Cursor Agent Enforcement Upgrade plan item 2",
}
