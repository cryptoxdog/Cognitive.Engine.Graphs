#!/usr/bin/env python3
"""Inject L9 cutover metadata headers into text assets.

This injector does not mutate binary files and does not normalize deprecated
PacketEnvelope-first architecture as active truth.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TEXT_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".txt", ".json"}

HEADER_TEMPLATE = """# L9_META:
# runtime_authority: Gate_SDK
# routing_authority: Gate
# canonical_transport: TransportPacket
# packet_envelope_status: deprecated_compatibility_only
# cutover_mode: strict
"""

DEPRECATED_MARKERS = (
    "PacketEnvelope",
    "inflate_ingress(",
    "deflate_egress(",
)

ACTIVE_MARKERS = (
    "TransportPacket",
    "Gate_SDK",
    "Gate",
)


def _should_process(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS


def _has_header(text: str) -> bool:
    return text.startswith("# L9_META:")


def _compatibility_hint(text: str) -> str:
    if any(marker in text for marker in DEPRECATED_MARKERS):
        return "# compatibility_surface: true\n"
    if any(marker in text for marker in ACTIVE_MARKERS):
        return "# compatibility_surface: false\n"
    return "# compatibility_surface: unknown\n"


def inject(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if _has_header(text):
        return False
    header = HEADER_TEMPLATE + _compatibility_hint(text)
    path.write_text(header + text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject strict cutover metadata")
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    updated = 0
    for path in root.rglob("*"):
        if _should_process(path):
            updated += 1 if inject(path) else 0

    print(f"updated_files={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
