#!/usr/bin/env python3
"""Validate domain specs against strict cutover rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as exc:
    msg = "PyYAML is required for validate_domain.py"
    raise RuntimeError(msg) from exc


FORBIDDEN_VALUES = {
    "PacketEnvelope",
    "inflate_ingress",
    "deflate_egress",
}
REQUIRED_AUTHORITY = {
    "runtime_authority": "Gate_SDK",
    "routing_authority": "Gate",
    "canonical_transport": "TransportPacket",
}


def _walk(node: Any, trail: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{trail}.{key}" if trail else str(key)
            items.append((path, value))
            items.extend(_walk(value, path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            path = f"{trail}[{index}]"
            items.append((path, value))
            items.extend(_walk(value, path))
    return items


def validate_file(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    findings: list[dict[str, Any]] = []

    if isinstance(data, dict):
        for field, expected in REQUIRED_AUTHORITY.items():
            actual = data.get(field)
            if actual is not None and actual != expected:
                findings.append(
                    {
                        "file": str(path),
                        "severity": "CRITICAL",
                        "rule_id": "DOMAIN-CUTOVER-001",
                        "message": f"{field} must be {expected!r}, found {actual!r}",
                    }
                )

    for trail, value in _walk(data):
        if isinstance(value, str) and any(token in value for token in FORBIDDEN_VALUES):
            findings.append(
                {
                    "file": str(path),
                    "severity": "CRITICAL",
                    "rule_id": "DOMAIN-CUTOVER-002",
                    "message": f"Forbidden legacy transport token at {trail}: {value!r}",
                }
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate domain specs")
    parser.add_argument("root", type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    findings: list[dict[str, Any]] = []
    for path in root.rglob("*.yaml"):
        findings.extend(validate_file(path))
    for path in root.rglob("*.yml"):
        findings.extend(validate_file(path))

    payload = {"findings": findings}
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"total": len(findings)}, sort_keys=True))
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
