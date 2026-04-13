#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [audit]
tags: [cutover, audit, spec-coverage, extraction]
owner: platform
status: active
--- /L9_META ---

Cutover-aware spec and repo extractor for Cognitive.Engine.Graphs.

This tool answers one question:
Does the repository, as currently written, express the intended cutover model?

Artifacts written:
- artifacts/spec_checklist.json
- artifacts/coverage_matrix.json
- artifacts/coverage_report.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

YAML_IMPORT_ERROR: Exception | None = None
try:
    import yaml  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - import guard
    yaml = None
    YAML_IMPORT_ERROR = exc


SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "artifacts",
}
TEXT_SUFFIXES = {".py", ".pyi", ".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".sh"}


@dataclass(slots=True)
class SpecFeature:
    category: str
    name: str
    reference: str
    expected_state: str
    search_regexes: list[str] = field(default_factory=list)
    include_globs: list[str] = field(default_factory=lambda: ["**/*"])
    exclude_globs: list[str] = field(default_factory=list)
    status: str = "MISSING"
    evidence_files: list[str] = field(default_factory=list)
    evidence_lines: list[str] = field(default_factory=list)
    notes: str = ""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        msg = f"PyYAML not installed: {YAML_IMPORT_ERROR!s}"
        raise RuntimeError(msg)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return bool(path.suffix and path.suffix not in TEXT_SUFFIXES)


def repo_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        files[rel] = path.read_text(encoding="utf-8", errors="replace")
    return files


def matches_globs(rel_path: str, include_globs: list[str], exclude_globs: list[str]) -> bool:
    path = Path(rel_path)
    if include_globs and not any(path.match(pattern) for pattern in include_globs):
        return False
    return not (exclude_globs and any(path.match(pattern) for pattern in exclude_globs))


def base_cutover_features() -> list[SpecFeature]:
    compatibility_allow = ["engine/packet/**", "tests/**", "contracts/**", "docs/**"]
    return [
        SpecFeature(
            category="runtime_authority",
            name="Gate_SDK",
            reference="Cutover objective",
            expected_state="IMPLEMENTED",
            search_regexes=[r"\bGate_SDK\b"],
            include_globs=["**/*.py", "**/*.md", "**/*.yaml", "**/*.yml"],
            exclude_globs=compatibility_allow,
            notes="Gate_SDK should appear as runtime authority in active tooling.",
        ),
        SpecFeature(
            category="routing_authority",
            name="Gate",
            reference="Cutover objective",
            expected_state="IMPLEMENTED",
            search_regexes=[r"\bGate\b"],
            include_globs=["**/*.py", "**/*.md", "**/*.yaml", "**/*.yml"],
            exclude_globs=compatibility_allow,
            notes="Gate should appear as routing authority in active tooling.",
        ),
        SpecFeature(
            category="transport_authority",
            name="TransportPacket",
            reference="Cutover objective",
            expected_state="IMPLEMENTED",
            search_regexes=[r"\bTransportPacket\b"],
            include_globs=["**/*.py", "**/*.md", "**/*.yaml", "**/*.yml"],
            exclude_globs=compatibility_allow,
            notes="TransportPacket should be canonical transport in active tooling.",
        ),
        SpecFeature(
            category="compatibility_only",
            name="PacketEnvelope",
            reference="Cutover objective",
            expected_state="PARTIAL",
            search_regexes=[r"\bPacketEnvelope\b"],
            include_globs=["engine/packet/**", "tests/**", "contracts/**", "docs/**"],
            notes="PacketEnvelope should remain only inside compatibility or historical surfaces.",
        ),
        SpecFeature(
            category="split_brain_guard",
            name="No active dual transport",
            reference="Cutover objective",
            expected_state="IMPLEMENTED",
            search_regexes=[r"\bTransportPacket\b", r"\bPacketEnvelope\b"],
            include_globs=["tools/**/*.py", "engine/**/*.py", "README*.md", "ARCHITECTURE*.md"],
            exclude_globs=compatibility_allow,
            notes="No active file should normalize both PacketEnvelope and TransportPacket as equal truths.",
        ),
        SpecFeature(
            category="legacy_drift",
            name="No chassis-first ingress truth",
            reference="Cutover objective",
            expected_state="IMPLEMENTED",
            search_regexes=[r"POST /v1/execute", r"single ingress", r"inflate_ingress\(", r"deflate_egress\("],
            include_globs=["tools/**/*.py", "engine/**/*.py", "README*.md", "ARCHITECTURE*.md"],
            exclude_globs=compatibility_allow,
            notes="Legacy ingress semantics should not remain active truth in current tooling.",
        ),
    ]


def enrich_from_spec(spec: dict[str, Any], features: list[SpecFeature]) -> list[SpecFeature]:
    spec_text = json.dumps(spec)
    if "Gate_SDK" in spec_text:
        features.append(
            SpecFeature(
                category="spec_declared",
                name="Spec declares Gate_SDK",
                reference="Provided spec document",
                expected_state="IMPLEMENTED",
                search_regexes=[r"\bGate_SDK\b"],
            )
        )
    if "TransportPacket" in spec_text:
        features.append(
            SpecFeature(
                category="spec_declared",
                name="Spec declares TransportPacket",
                reference="Provided spec document",
                expected_state="IMPLEMENTED",
                search_regexes=[r"\bTransportPacket\b"],
            )
        )
    return features


def evaluate_feature(feature: SpecFeature, files: dict[str, str]) -> None:
    matches: list[str] = []
    line_hits: list[str] = []

    for rel_path, content in files.items():
        if not matches_globs(rel_path, feature.include_globs, feature.exclude_globs):
            continue
        regex_hits = [re.search(pattern, content, re.MULTILINE) for pattern in feature.search_regexes]
        if feature.category in {"split_brain_guard", "legacy_drift"}:
            if feature.category == "split_brain_guard":
                if all(regex_hits):
                    matches.append(rel_path)
                    line_hits.append(f"{rel_path}:1")
            elif any(regex_hits):
                matches.append(rel_path)
                line_hits.append(f"{rel_path}:1")
            continue

        if any(regex_hits):
            matches.append(rel_path)
            for pattern in feature.search_regexes:
                match = re.search(pattern, content, re.MULTILINE)
                if match:
                    line_no = content.count("\n", 0, match.start()) + 1
                    line_hits.append(f"{rel_path}:{line_no}")
                    break

    feature.evidence_files = sorted(set(matches))
    feature.evidence_lines = line_hits[:10]

    if feature.category == "split_brain_guard":
        feature.status = "MISSING" if feature.evidence_files else "IMPLEMENTED"
        return
    if feature.category == "legacy_drift":
        feature.status = "MISSING" if feature.evidence_files else "IMPLEMENTED"
        return

    if feature.expected_state == "PARTIAL":
        feature.status = "IMPLEMENTED" if feature.evidence_files else "MISSING"
    else:
        feature.status = "IMPLEMENTED" if feature.evidence_files else "MISSING"


def write_outputs(root: Path, features: list[SpecFeature]) -> None:
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    serialized = [asdict(feature) for feature in features]
    (artifacts / "spec_checklist.json").write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    totals = {"IMPLEMENTED": 0, "MISSING": 0}
    categories: dict[str, dict[str, int]] = {}
    for feature in features:
        totals[feature.status] = totals.get(feature.status, 0) + 1
        categories.setdefault(feature.category, {"IMPLEMENTED": 0, "MISSING": 0, "total": 0})
        categories[feature.category][feature.status] += 1
        categories[feature.category]["total"] += 1

    matrix = {"generated_at": now_iso(), "totals": totals, "categories": categories}
    (artifacts / "coverage_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# CEG Cutover Coverage Report")
    lines.append("")
    lines.append(f"- Generated: {matrix['generated_at']}")
    lines.append(f"- Implemented: {totals['IMPLEMENTED']}")
    lines.append(f"- Missing: {totals['MISSING']}")
    lines.append("")
    for feature in features:
        marker = "✅" if feature.status == "IMPLEMENTED" else "❌"
        lines.append(f"## {marker} {feature.category} :: {feature.name}")
        lines.append(f"- Reference: {feature.reference}")
        lines.append(f"- Expected state: {feature.expected_state}")
        lines.append(f"- Status: {feature.status}")
        if feature.evidence_files:
            lines.append(f"- Files: {', '.join(feature.evidence_files)}")
            lines.append(f"- Lines: {', '.join(feature.evidence_lines)}")
        else:
            lines.append("- Files: none")
        if feature.notes:
            lines.append(f"- Notes: {feature.notes}")
        lines.append("")
    (artifacts / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_extract(root: Path, spec_path: Path | None = None) -> list[SpecFeature]:
    """Public API: return feature list without writing artifacts or printing."""
    features = base_cutover_features()
    if spec_path is not None:
        spec = load_yaml(spec_path)
        features = enrich_from_spec(spec, features)
    files = repo_files(root)
    for feature in features:
        evaluate_feature(feature, files)
    return features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract cutover coverage from repo and optional spec")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--spec", default=None, help="Optional spec YAML path")
    parser.add_argument("--fail-on-missing", action="store_true", help="Exit 1 if any feature is missing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    features = base_cutover_features()

    if args.spec:
        try:
            spec = load_yaml(Path(args.spec).resolve())
            features = enrich_from_spec(spec, features)
        except Exception as exc:
            print(f"spec_extract failed to load spec: {exc}", file=sys.stderr)
            return 2

    files = repo_files(root)
    for feature in features:
        evaluate_feature(feature, files)

    write_outputs(root, features)
    missing = sum(1 for feature in features if feature.status == "MISSING")
    print(json.dumps({"generated_at": now_iso(), "feature_count": len(features), "missing": missing}, indent=2))
    return 1 if args.fail_on_missing and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
