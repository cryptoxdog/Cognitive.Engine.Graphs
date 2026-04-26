#!/usr/bin/env python3
"""Extract cutover-relevant domain and authority signals from a repo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TEXT_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".txt", ".json"}

SIGNALS = {
    "runtime_authority": ("Gate_SDK",),
    "routing_authority": ("Gate",),
    "canonical_transport": ("TransportPacket",),
    "deprecated_compatibility": ("PacketEnvelope", "inflate_ingress(", "deflate_egress("),
}


def _is_text(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract cutover domain signals")
    parser.add_argument("root", type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    results: dict[str, list[dict[str, str]]] = {key: [] for key in SIGNALS}

    for path in root.rglob("*"):
        if not _is_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(path.relative_to(root))
        for category, tokens in SIGNALS.items():
            for token in tokens:
                if token in text:
                    results[category].append({"file": rel, "token": token})

    payload = {"signals": results}
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: len(value) for key, value in results.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
