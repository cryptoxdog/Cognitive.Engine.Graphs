#!/usr/bin/env python3
# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [meta]
# tags: [L9_TEMPLATE, meta, injector]
# owner: platform
# status: active
# --- /L9_META ---
"""
l9_meta_injector.py — Deterministic L9_META Header Injection
=============================================================

Zero-LLM, zero-token script that injects L9_META headers into every tracked
file in a constellation engine repo.  Run it once, commit the result, done.

Reads the file registry (FILE_REGISTRY below) and injects the correct
header format for each filetype.  Idempotent — re-running replaces any
existing L9_META block rather than duplicating it.

Usage:
    python tools/l9_meta_injector.py                    # dry-run (default)
    python tools/l9_meta_injector.py --apply            # write changes
    python tools/l9_meta_injector.py --apply --engine enrichment  # override engine id

Designed for the Cognitive.Engine.Graphs repo but works on any L9 engine
repo by changing ENGINE_ID and FILE_REGISTRY.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# =============================================================================
# CONFIGURATION
# =============================================================================

ENGINE_ID = "graph"  # Override via --engine flag
L9_SCHEMA_VERSION = 1

# =============================================================================
# FILE REGISTRY — Single source of truth for every file's meta values
# =============================================================================

@dataclass
class FileMeta:
    path: str
    origin: str           # l9-template | engine-specific | domain-specific
    layer: list[str]
    tags: list[str]
    owner: str            # platform | engine-team | domain-team | <handle>
    status: str = "active"


FILE_REGISTRY: list[FileMeta] = [
    # =========================================================================
    # TEMPLATE FILES  (origin: l9-template, owner: platform)
    # =========================================================================

    # --- Agent Rules ---
    FileMeta(".cursorrules",                        "l9-template", ["agent-rules"],           ["L9_TEMPLATE", "agent-rules", "cursor"],       "platform"),
    FileMeta("CLAUDE.md",                           "l9-template", ["agent-rules"],           ["L9_TEMPLATE", "agent-rules", "claude"],       "platform"),
    FileMeta(".github/copilot-instructions.md",     "l9-template", ["agent-rules"],           ["L9_TEMPLATE", "agent-rules", "copilot"],      "platform"),

    # --- Audit Tools ---
    FileMeta("tools/audit_engine.py",               "l9-template", ["audit"],                 ["L9_TEMPLATE", "audit", "compliance"],          "platform"),
    FileMeta("tools/audit_rules.yaml",              "l9-template", ["audit"],                 ["L9_TEMPLATE", "audit-rules"],                  "platform"),
    FileMeta("tools/spec_extract.py",               "l9-template", ["audit"],                 ["L9_TEMPLATE", "audit", "spec-coverage"],       "platform"),
    FileMeta("tools/l9_template_manifest.yaml",     "l9-template", ["meta"],                  ["L9_TEMPLATE", "meta", "manifest"],             "platform"),
    FileMeta("tools/l9_meta_injector.py",            "l9-template", ["meta"],                  ["L9_TEMPLATE", "meta", "injector"],              "platform"),

    # --- CI/CD Workflows ---
    FileMeta(".github/workflows/audit.yml",                    "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "audit"],            "platform"),
    FileMeta(".github/workflows/ci.yml",                       "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "pipeline"],         "platform"),
    FileMeta(".github/workflows/compliance.yml",               "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "compliance"],       "platform"),
    FileMeta(".github/workflows/docker-build.yml",             "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "docker"],           "platform"),
    FileMeta(".github/workflows/k8s-deploy.yml",               "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "deploy"],           "platform"),
    FileMeta(".github/workflows/supply-chain.yml",             "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "security"],         "platform"),
    FileMeta(".github/workflows/codeql.yml",                   "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "security"],         "platform"),
    FileMeta(".github/workflows/pr-review-enforcement.yml",    "l9-template", ["ci", "governance"],      ["L9_TEMPLATE", "ci", "governance"],       "platform"),
    FileMeta(".github/workflows/terminology-guard.yml",        "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "terminology"],      "platform"),
    FileMeta(".github/workflows/release-drafter.yml",          "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "release"],          "platform"),
    FileMeta(".github/workflows/docs-code-sync.yml",           "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "docs-sync"],        "platform"),
    FileMeta(".github/workflows/refactoring-validation.yml",   "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "refactoring"],      "platform"),
    FileMeta(".github/workflows/dev-layer-gmp.yml",            "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "dev-layer"],        "platform"),
    FileMeta(".github/workflows/auto-fix-adr.yml",             "l9-template", ["ci"],                    ["L9_TEMPLATE", "ci", "adr"],              "platform"),

    # --- Governance ---
    FileMeta(".github/CODEOWNERS",                  "l9-template", ["governance"],            ["L9_TEMPLATE", "governance", "ownership"],      "platform"),
    FileMeta(".github/pr_review_config.yaml",       "l9-template", ["governance"],            ["L9_TEMPLATE", "governance", "pr-review"],      "platform"),
    FileMeta(".github/dependabot.yml",              "l9-template", ["governance"],            ["L9_TEMPLATE", "security", "deps"],             "platform"),
    FileMeta(".github/scripts/setup-repo-vars.sh",  "l9-template", ["bootstrap"],             ["L9_TEMPLATE", "bootstrap", "setup"],           "platform"),
    FileMeta(".pre-commit-config.yaml",             "l9-template", ["governance"],            ["L9_TEMPLATE", "precommit"],                    "platform"),
    FileMeta(".coderabbit.yaml",                    "l9-template", ["governance"],            ["L9_TEMPLATE", "pr-review"],                    "platform"),

    # --- Config / Bootstrap ---
    FileMeta(".suite6-config.json",                 "l9-template", ["config"],                ["L9_TEMPLATE", "config", "suite6"],             "platform"),
    FileMeta("setup-new-workspace.yaml",            "l9-template", ["bootstrap"],             ["L9_TEMPLATE", "bootstrap", "workspace"],       "platform"),
    FileMeta("UniversalDevelopmentPack.yaml",       "l9-template", ["bootstrap"],             ["L9_TEMPLATE", "dev-pack", "standards"],        "platform"),
    FileMeta(".env.template",                       "l9-template", ["config"],                ["L9_TEMPLATE", "config", "env"],                "platform"),
    FileMeta(".github/env.template",                "l9-template", ["config"],                ["L9_TEMPLATE", "config", "env"],                "platform"),

    # --- Docker / Build ---
    FileMeta("Dockerfile",                          "l9-template", ["docker"],                ["L9_TEMPLATE", "docker", "dev"],                "platform"),
    FileMeta("Dockerfile.prod",                     "l9-template", ["docker"],                ["L9_TEMPLATE", "docker", "prod"],               "platform"),
    FileMeta("docker-compose.yml",                  "l9-template", ["docker"],                ["L9_TEMPLATE", "docker", "dev"],                "platform"),
    FileMeta("docker-compose.prod.yml",             "l9-template", ["docker"],                ["L9_TEMPLATE", "docker", "prod"],               "platform"),
    FileMeta("entrypoint.sh",                       "l9-template", ["docker"],                ["L9_TEMPLATE", "docker", "entrypoint"],         "platform"),
    FileMeta("Makefile",                            "l9-template", ["build"],                 ["L9_TEMPLATE", "build", "commands"],            "platform"),

    # --- Telemetry ---
    FileMeta("telemetry/dashboards/dashboards-docker-compose.monitoring.yml",       "l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "docker"],     "platform"),
    FileMeta("telemetry/dashboards/dashboards-grafana-overview.json",               "l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "grafana"],    "platform"),
    FileMeta("telemetry/dashboards/dashboards-grafana-api.json",                    "l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "grafana"],    "platform"),
    FileMeta("telemetry/dashboards/dashboards-grafana-neo4j.json",                  "l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "grafana"],    "platform"),
    FileMeta("telemetry/dashboards/dashboards-grafana-provisioning-dashboards.yml", "l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "grafana"],    "platform"),
    FileMeta("telemetry/dashboards/dashboards-grafana-provisioning-datasources.yml","l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "grafana"],    "platform"),
    FileMeta("telemetry/dashboards/dashboards-prometheus.yml",                      "l9-template", ["telemetry"], ["L9_TEMPLATE", "telemetry", "prometheus"], "platform"),

    # --- Scripts ---
    FileMeta("scripts/scripts-build.sh",            "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "build"],             "platform"),
    FileMeta("scripts/scripts-deploy.sh",           "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "deploy"],            "platform"),
    FileMeta("scripts/scripts-dev.sh",              "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "dev"],               "platform"),
    FileMeta("scripts/scripts-health.sh",           "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "health"],            "platform"),
    FileMeta("scripts/scripts-migrate.sh",          "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "migration"],         "platform"),
    FileMeta("scripts/scripts-seed.sh",             "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "seed"],              "platform"),
    FileMeta("scripts/scripts-setup.sh",            "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "setup"],             "platform"),
    FileMeta("scripts/scripts-test.sh",             "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "test"],              "platform"),
    FileMeta("scripts/scripts-gds-trigger.sh",      "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "gds"],               "platform"),
    FileMeta("scripts/entrypoint.sh",               "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "entrypoint"],        "platform"),
    FileMeta("scripts/audit.sh",                    "l9-template", ["scripts", "audit"],      ["L9_TEMPLATE", "scripts", "audit"],             "platform"),
    FileMeta("scripts/README.md",                   "l9-template", ["scripts"],               ["L9_TEMPLATE", "scripts", "docs"],              "platform"),

    # --- Test Harness ---
    FileMeta("tests/conftest.py",                   "l9-template", ["test"],                  ["L9_TEMPLATE", "test", "fixtures"],             "platform"),

    # =========================================================================
    # ENGINE-SPECIFIC FILES  (origin: engine-specific, owner: engine-team)
    # =========================================================================
    FileMeta("engine/__init__.py",                         "engine-specific", ["config"],  ["engine-core"],                         "engine-team"),
    FileMeta("engine/handlers.py",                         "engine-specific", ["config"],  ["chassis-bridge", "handlers"],          "engine-team"),
    FileMeta("engine/config/__init__.py",                  "engine-specific", ["config"],  ["config"],                              "engine-team"),
    FileMeta("engine/config/loader.py",                    "engine-specific", ["config"],  ["config", "domain-loader"],             "engine-team"),
    FileMeta("engine/config/schema.py",                    "engine-specific", ["config"],  ["config", "pydantic", "domain-spec"],   "engine-team"),
    FileMeta("engine/config/settings.py",                  "engine-specific", ["config"],  ["config", "settings"],                  "engine-team"),
    FileMeta("engine/config/units.py",                     "engine-specific", ["config"],  ["config", "units"],                     "engine-team"),
    FileMeta("engine/gates/__init__.py",                   "engine-specific", ["config"],  ["gates"],                               "engine-team"),
    FileMeta("engine/gates/compiler.py",                   "engine-specific", ["config"],  ["gates", "compiler", "cypher"],         "engine-team"),
    FileMeta("engine/gates/null_semantics.py",             "engine-specific", ["config"],  ["gates", "null-semantics"],             "engine-team"),
    FileMeta("engine/gates/registry.py",                   "engine-specific", ["config"],  ["gates", "registry"],                   "engine-team"),
    FileMeta("engine/gates/types/__init__.py",             "engine-specific", ["config"],  ["gates", "types"],                      "engine-team"),
    FileMeta("engine/gates/types/all_gates.py",            "engine-specific", ["config"],  ["gates", "types", "implementation"],    "engine-team"),
    FileMeta("engine/scoring/__init__.py",                 "engine-specific", ["config"],  ["scoring"],                             "engine-team"),
    FileMeta("engine/scoring/assembler.py",                "engine-specific", ["config"],  ["scoring", "assembler", "cypher"],      "engine-team"),
    FileMeta("engine/traversal/__init__.py",               "engine-specific", ["config"],  ["traversal"],                           "engine-team"),
    FileMeta("engine/traversal/assembler.py",              "engine-specific", ["config"],  ["traversal", "assembler", "cypher"],    "engine-team"),
    FileMeta("engine/traversal/resolver.py",               "engine-specific", ["config"],  ["traversal", "resolver"],               "engine-team"),
    FileMeta("engine/sync/__init__.py",                    "engine-specific", ["config"],  ["sync"],                                "engine-team"),
    FileMeta("engine/sync/generator.py",                   "engine-specific", ["config"],  ["sync", "cypher", "merge"],             "engine-team"),
    FileMeta("engine/gds/__init__.py",                     "engine-specific", ["config"],  ["gds"],                                 "engine-team"),
    FileMeta("engine/gds/scheduler.py",                    "engine-specific", ["config"],  ["gds", "scheduler", "louvain"],         "engine-team"),
    FileMeta("engine/graph/__init__.py",                   "engine-specific", ["config"],  ["graph", "driver"],                     "engine-team"),
    FileMeta("engine/graph/driver.py",                     "engine-specific", ["config"],  ["graph", "driver", "neo4j"],            "engine-team"),
    FileMeta("engine/compliance/__init__.py",              "engine-specific", ["config"],  ["compliance"],                          "engine-team"),
    FileMeta("engine/compliance/audit.py",                 "engine-specific", ["config"],  ["compliance", "audit"],                 "engine-team"),
    FileMeta("engine/compliance/pii.py",                   "engine-specific", ["config"],  ["compliance", "pii"],                   "engine-team"),
    FileMeta("engine/compliance/prohibited_factors.py",    "engine-specific", ["config"],  ["compliance", "prohibited-factors"],    "engine-team"),
    FileMeta("engine/packet/__init__.py",                  "engine-specific", ["config"],  ["packet"],                              "engine-team"),
    FileMeta("engine/packet/packet_envelope.py",           "engine-specific", ["config"],  ["packet", "envelope", "pydantic"],      "engine-team"),
    FileMeta("engine/packet/chassis_contract.py",          "engine-specific", ["config"],  ["packet", "chassis-bridge"],            "engine-team"),
    FileMeta("engine/utils/__init__.py",                   "engine-specific", ["config"],  ["utils"],                               "engine-team"),
    FileMeta("engine/utils/safe_eval.py",                  "engine-specific", ["config"],  ["utils", "safe-eval"],                  "engine-team"),
    FileMeta("engine/utils/security.py",                   "engine-specific", ["config"],  ["utils", "security", "sanitize"],       "engine-team"),
    FileMeta("chassis/__init__.py",                        "engine-specific", ["config"],  ["chassis"],                             "engine-team"),
    FileMeta("chassis/actions.py",                         "engine-specific", ["config"],  ["chassis", "actions"],                  "engine-team"),
    FileMeta("pyproject.toml",                             "engine-specific", ["build", "config"], ["build", "dependencies", "poetry"], "engine-team"),
    FileMeta("graph-cognitive-engine-spec-v1.1.0.yaml",    "engine-specific", ["config"],  ["spec", "engine-spec"],                "engine-team"),

    # =========================================================================
    # DOMAIN-SPECIFIC FILES  (origin: domain-specific, owner: domain-team)
    # =========================================================================
    FileMeta("domains/MASTER-SPEC-ALL-DOMAINS.yaml",           "domain-specific", ["config"], ["domains", "master-spec"],     "domain-team"),
    FileMeta("domains/README.md",                              "domain-specific", ["config"], ["domains", "docs"],            "domain-team"),
    FileMeta("domains/TESTING_GUIDE.md",                       "domain-specific", ["test"],   ["domains", "testing", "guide"],"domain-team"),
    FileMeta("domains/domain_extractor.py",                    "domain-specific", ["config"], ["domains", "extractor"],       "domain-team"),
    FileMeta("domains/mortgage_brokerage_domain_spec.yaml",    "domain-specific", ["config"], ["domains", "mortgage"],        "domain-team"),
    FileMeta("domains/healthcare_referral_domain_spec.yaml",   "domain-specific", ["config"], ["domains", "healthcare"],      "domain-team"),
    FileMeta("domains/freight_matching_domain_spec.yaml",      "domain-specific", ["config"], ["domains", "freight"],         "domain-team"),
    FileMeta("domains/legal_discovery_domain_spec.yaml",       "domain-specific", ["config"], ["domains", "legal"],           "domain-team"),
    FileMeta("domains/roofing_company_domain_spec.yaml",       "domain-specific", ["config"], ["domains", "roofing"],         "domain-team"),
    FileMeta("domains/executive_assistant_domain_spec.yaml",   "domain-specific", ["config"], ["domains", "executive-assistant"], "domain-team"),
    FileMeta("domains/aios_god_agent_domain_spec.yaml",        "domain-specific", ["config"], ["domains", "aios"],            "domain-team"),
    FileMeta("domains/repo_as_agent_domain_spec.yaml",         "domain-specific", ["config"], ["domains", "repo-agent"],      "domain-team"),
    FileMeta("domains/research_agent_domain_spec.yaml",        "domain-specific", ["config"], ["domains", "research-agent"],  "domain-team"),
]


# =============================================================================
# FORMATTERS — One per filetype family
# =============================================================================

def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def format_comment_block(meta: FileMeta, engine: str, prefix: str = "# ") -> str:
    lines = [
        f"{prefix}",
    ]
    return "\n".join(lines)


def format_html_comment(meta: FileMeta, engine: str) -> str:
    lines = [
        "<!-- L9_META",
        f"l9_schema: {L9_SCHEMA_VERSION}",
        f"origin: {meta.origin}",
        f"engine: {engine}",
        f"layer: {_yaml_list(meta.layer)}",
        f"tags: {_yaml_list(meta.tags)}",
        f"owner: {meta.owner}",
        f"status: {meta.status}",
        "/L9_META -->",
    ]
    return "\n".join(lines)


def format_python_docstring_block(meta: FileMeta, engine: str) -> str:
    lines = [
        "",
    ]
    return "\n".join(lines)


def format_json_meta(meta: FileMeta, engine: str) -> dict[str, Any]:
    return {
        "l9_schema": L9_SCHEMA_VERSION,
        "origin": meta.origin,
        "engine": engine,
        "layer": meta.layer,
        "tags": meta.tags,
        "owner": meta.owner,
        "status": meta.status,
    }


def format_toml_block(meta: FileMeta, engine: str) -> str:
    layer_str = ", ".join(f'"{l}"' for l in meta.layer)
    tags_str = ", ".join(f'"{t}"' for t in meta.tags)
    lines = [
        "",
        "[tool.l9_meta]",
        f"l9_schema = {L9_SCHEMA_VERSION}",
        f'origin = "{meta.origin}"',
        f'engine = "{engine}"',
        f'layer = [{layer_str}]',
        f'tags = [{tags_str}]',
        f'owner = "{meta.owner}"',
        f'status = "{meta.status}"',
    ]
    return "\n".join(lines)


# =============================================================================
# STRIP EXISTING — Regex patterns for idempotent re-injection
# =============================================================================

RE_COMMENT_META = re.compile(
    r"[ \t]*#[ \t]*[ \t]*\n?",
    re.DOTALL,
)
RE_HTML_META = re.compile(
    r"<!-- L9_META.*?/L9_META -->[ \t]*\n?",
    re.DOTALL,
)
RE_PY_DOCSTRING_META = re.compile(
    r"\n?",
    re.DOTALL,
)


# =============================================================================
# FILETYPE DETECTION
# =============================================================================

def _detect_filetype(path: str) -> str:
    p = Path(path)
    name = p.name.lower()
    suffix = p.suffix.lower()

    if name == "codeowners":
        return "plain-comment"
    if name in ("makefile",):
        return "comment"
    if name.startswith("dockerfile"):
        return "comment"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    if suffix == ".py":
        return "python"
    if suffix == ".md":
        return "markdown"
    if suffix == ".sh":
        return "shell"
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    if ".template" in name:
        return "comment"
    return "comment"


# =============================================================================
# INJECTION — Filetype-aware header injection
# =============================================================================

def inject_meta(content: str, meta: FileMeta, engine: str) -> str:
    ftype = _detect_filetype(meta.path)

    # --- JSON ---
    if ftype == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return content
        data["_l9_meta"] = format_json_meta(meta, engine)
        ordered = {"_l9_meta": data.pop("_l9_meta")}
        ordered.update(data)
        return json.dumps(ordered, indent=2) + "\n"

    # --- TOML ---
    if ftype == "toml":
        block = format_toml_block(meta, engine)
        cleaned = re.sub(
            r"\n?\[tool\.l9_meta\].*?(?=\n\[|\Z)", "", content, flags=re.DOTALL
        ).rstrip() + "\n"
        return cleaned + block + "\n"

    # --- Markdown ---
    if ftype == "markdown":
        content = RE_HTML_META.sub("", content)
        block = format_html_comment(meta, engine)
        return block + "\n\n" + content.lstrip("\n")

    # --- Python ---
    if ftype == "python":
        content = RE_PY_DOCSTRING_META.sub("", content)
        ds_match = re.match(r'^(""")(.*?)(""")', content, re.DOTALL)
        if ds_match:
            opening = ds_match.group(1)
            body = ds_match.group(2)
            closing = ds_match.group(3)
            meta_block = format_python_docstring_block(meta, engine)
            body_stripped = body.lstrip("\n")
            new_ds = f'{opening}\n{meta_block}\n\n{body_stripped}{closing}'
            return new_ds + content[ds_match.end():]
        else:
            content = RE_COMMENT_META.sub("", content)
            block = format_comment_block(meta, engine)
            if content.startswith("#!"):
                nl = content.index("\n")
                return content[:nl + 1] + block + "\n" + content[nl + 1:]
            return block + "\n" + content

    # --- Shell ---
    if ftype == "shell":
        content = RE_COMMENT_META.sub("", content)
        block = format_comment_block(meta, engine)
        if content.startswith("#!"):
            nl = content.index("\n")
            return content[:nl + 1] + block + "\n" + content[nl + 1:]
        return block + "\n" + content

    # --- YAML ---
    if ftype == "yaml":
        content = RE_COMMENT_META.sub("", content)
        block = format_comment_block(meta, engine)
        if content.lstrip().startswith("---"):
            idx = content.index("---")
            return block + "\n" + content[idx:]
        return block + "\n" + content

    # --- Fallback: comment-style ---
    content = RE_COMMENT_META.sub("", content)
    block = format_comment_block(meta, engine)
    if content.startswith("#!"):
        nl = content.index("\n")
        return content[:nl + 1] + block + "\n" + content[nl + 1:]
    return block + "\n" + content


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject L9_META headers into all tracked files"
    )
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--engine", default=ENGINE_ID, help=f"Engine ID (default: {ENGINE_ID})")
    parser.add_argument("--root", default=".", help="Repo root directory")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    engine = args.engine
    updated = skipped = missing = errors = 0

    for fm in FILE_REGISTRY:
        fpath = root / fm.path
        if not fpath.exists():
            print(f"  MISSING  {fm.path}")
            missing += 1
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
            new_content = inject_meta(content, fm, engine)
            if new_content == content:
                print(f"  SKIP     {fm.path}  (already has correct meta)")
                skipped += 1
                continue
            if args.apply:
                fpath.write_text(new_content, encoding="utf-8")
                print(f"  UPDATED  {fm.path}")
            else:
                print(f"  PENDING  {fm.path}  (dry-run)")
            updated += 1
        except Exception as e:
            print(f"  ERROR    {fm.path}  ({e})")
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"  Engine:   {engine}")
    print(f"  Updated:  {updated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Missing:  {missing}")
    print(f"  Errors:   {errors}")
    print(f"  Total:    {len(FILE_REGISTRY)}")
    if not args.apply and updated > 0:
        print(f"\n  >>> Dry-run mode. Run with --apply to write changes.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
