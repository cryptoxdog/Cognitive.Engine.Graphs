#!/usr/bin/env python3
"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [meta]
tags: [L9_TEMPLATE, meta, injector]
owner: platform
status: active
--- /L9_META ---
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
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
    origin: str  # l9-template | engine-specific | domain-specific
    layer: list[str]
    tags: list[str]
    owner: str  # platform | engine-team | domain-team | <handle>
    status: str = "active"


FILE_REGISTRY: list[FileMeta] = [
    # =========================================================================
    # TEMPLATE FILES  (origin: l9-template, owner: platform)
    # =========================================================================
    # --- Agent Rules ---
    FileMeta(".cursorrules", "l9-template", ["agent-rules"], ["L9_TEMPLATE", "agent-rules", "cursor"], "platform"),
    FileMeta("CLAUDE.md", "l9-template", ["agent-rules"], ["L9_TEMPLATE", "agent-rules", "claude"], "platform"),
    FileMeta(
        ".github/copilot-instructions.md",
        "l9-template",
        ["agent-rules"],
        ["L9_TEMPLATE", "agent-rules", "copilot"],
        "platform",
    ),
    # --- Audit Tools ---
    FileMeta("tools/audit_engine.py", "l9-template", ["audit"], ["L9_TEMPLATE", "audit", "compliance"], "platform"),
    FileMeta("tools/audit_rules.yaml", "l9-template", ["audit"], ["L9_TEMPLATE", "audit-rules"], "platform"),
    FileMeta("tools/spec_extract.py", "l9-template", ["audit"], ["L9_TEMPLATE", "audit", "spec-coverage"], "platform"),
    FileMeta(
        "tools/l9_template_manifest.yaml", "l9-template", ["meta"], ["L9_TEMPLATE", "meta", "manifest"], "platform"
    ),
    FileMeta("tools/l9_meta_injector.py", "l9-template", ["meta"], ["L9_TEMPLATE", "meta", "injector"], "platform"),
    # --- CI/CD Workflows ---
    FileMeta(".github/workflows/audit.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "audit"], "platform"),
    FileMeta(".github/workflows/ci.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "pipeline"], "platform"),
    FileMeta(
        ".github/workflows/compliance.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "compliance"], "platform"
    ),
    FileMeta(".github/workflows/docker-build.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "docker"], "platform"),
    FileMeta(".github/workflows/k8s-deploy.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "deploy"], "platform"),
    FileMeta(
        ".github/workflows/supply-chain.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "security"], "platform"
    ),
    FileMeta(".github/workflows/codeql.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "security"], "platform"),
    FileMeta(
        ".github/workflows/pr-review-enforcement.yml",
        "l9-template",
        ["ci", "governance"],
        ["L9_TEMPLATE", "ci", "governance"],
        "platform",
    ),
    FileMeta(
        ".github/workflows/terminology-guard.yml",
        "l9-template",
        ["ci"],
        ["L9_TEMPLATE", "ci", "terminology"],
        "platform",
    ),
    FileMeta(
        ".github/workflows/release-drafter.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "release"], "platform"
    ),
    FileMeta(
        ".github/workflows/docs-code-sync.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "docs-sync"], "platform"
    ),
    FileMeta(
        ".github/workflows/refactoring-validation.yml",
        "l9-template",
        ["ci"],
        ["L9_TEMPLATE", "ci", "refactoring"],
        "platform",
    ),
    FileMeta(
        ".github/workflows/dev-layer-gmp.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "dev-layer"], "platform"
    ),
    FileMeta(".github/workflows/auto-fix-adr.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "adr"], "platform"),
    # --- Governance ---
    FileMeta(
        ".github/CODEOWNERS", "l9-template", ["governance"], ["L9_TEMPLATE", "governance", "ownership"], "platform"
    ),
    FileMeta(
        ".github/pr_review_config.yaml",
        "l9-template",
        ["governance"],
        ["L9_TEMPLATE", "governance", "pr-review"],
        "platform",
    ),
    FileMeta(".github/dependabot.yml", "l9-template", ["governance"], ["L9_TEMPLATE", "security", "deps"], "platform"),
    FileMeta(
        ".github/scripts/setup-repo-vars.sh",
        "l9-template",
        ["bootstrap"],
        ["L9_TEMPLATE", "bootstrap", "setup"],
        "platform",
    ),
    FileMeta(".pre-commit-config.yaml", "l9-template", ["governance"], ["L9_TEMPLATE", "precommit"], "platform"),
    FileMeta(".coderabbit.yaml", "l9-template", ["governance"], ["L9_TEMPLATE", "pr-review"], "platform"),
    # --- Config / Bootstrap ---
    FileMeta(".suite6-config.json", "l9-template", ["config"], ["L9_TEMPLATE", "config", "suite6"], "platform"),
    FileMeta(
        "setup-new-workspace.yaml", "l9-template", ["bootstrap"], ["L9_TEMPLATE", "bootstrap", "workspace"], "platform"
    ),
    FileMeta(
        "UniversalDevelopmentPack.yaml",
        "l9-template",
        ["bootstrap"],
        ["L9_TEMPLATE", "dev-pack", "standards"],
        "platform",
    ),
    FileMeta(".env.template", "l9-template", ["config"], ["L9_TEMPLATE", "config", "env"], "platform"),
    FileMeta(".github/env.template", "l9-template", ["config"], ["L9_TEMPLATE", "config", "env"], "platform"),
    # --- Docker / Build ---
    FileMeta("Dockerfile", "l9-template", ["docker"], ["L9_TEMPLATE", "docker", "dev"], "platform"),
    FileMeta("Dockerfile.prod", "l9-template", ["docker"], ["L9_TEMPLATE", "docker", "prod"], "platform"),
    FileMeta("docker-compose.yml", "l9-template", ["docker"], ["L9_TEMPLATE", "docker", "dev"], "platform"),
    FileMeta("docker-compose.prod.yml", "l9-template", ["docker"], ["L9_TEMPLATE", "docker", "prod"], "platform"),
    # entrypoint.sh at root doesn't exist - use scripts/entrypoint.sh or chassis/entrypoint.sh
    FileMeta("Makefile", "l9-template", ["build"], ["L9_TEMPLATE", "build", "commands"], "platform"),
    # --- Telemetry ---
    FileMeta(
        "telemetry/dashboards/dashboards-docker-compose.monitoring.yml",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "docker"],
        "platform",
    ),
    FileMeta(
        "telemetry/dashboards/dashboards-grafana-overview.json",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "grafana"],
        "platform",
    ),
    FileMeta(
        "telemetry/dashboards/dashboards-grafana-api.json",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "grafana"],
        "platform",
    ),
    FileMeta(
        "telemetry/dashboards/dashboards-grafana-neo4j.json",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "grafana"],
        "platform",
    ),
    FileMeta(
        "telemetry/dashboards/dashboards-grafana-provisioning-dashboards.yml",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "grafana"],
        "platform",
    ),
    FileMeta(
        "telemetry/dashboards/dashboards-grafana-provisioning-datasources.yml",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "grafana"],
        "platform",
    ),
    FileMeta(
        "telemetry/dashboards/dashboards-prometheus.yml",
        "l9-template",
        ["telemetry"],
        ["L9_TEMPLATE", "telemetry", "prometheus"],
        "platform",
    ),
    # --- Scripts ---
    FileMeta("scripts/scripts-build.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "build"], "platform"),
    FileMeta("scripts/scripts-deploy.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "deploy"], "platform"),
    FileMeta("scripts/scripts-dev.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "dev"], "platform"),
    FileMeta("scripts/scripts-health.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "health"], "platform"),
    FileMeta(
        "scripts/scripts-migrate.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "migration"], "platform"
    ),
    FileMeta("scripts/scripts-seed.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "seed"], "platform"),
    FileMeta("scripts/scripts-setup.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "setup"], "platform"),
    FileMeta("scripts/scripts-test.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "test"], "platform"),
    FileMeta(
        "scripts/scripts-gds-trigger.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "gds"], "platform"
    ),
    FileMeta("scripts/entrypoint.sh", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "entrypoint"], "platform"),
    FileMeta("scripts/audit.sh", "l9-template", ["scripts", "audit"], ["L9_TEMPLATE", "scripts", "audit"], "platform"),
    FileMeta("scripts/README.md", "l9-template", ["scripts"], ["L9_TEMPLATE", "scripts", "docs"], "platform"),
    FileMeta(
        "scripts/domain_extractor.py",
        "l9-template",
        ["scripts"],
        ["L9_TEMPLATE", "scripts", "domain-extractor"],
        "platform",
    ),
    # --- Test Harness ---
    FileMeta("tests/conftest.py", "l9-template", ["test"], ["L9_TEMPLATE", "test", "fixtures"], "platform"),
    FileMeta("tests/README.md", "l9-template", ["test"], ["L9_TEMPLATE", "test", "docs"], "platform"),
    # --- Tests: Compliance ---
    FileMeta(
        "tests/compliance/test_audit.py", "engine-specific", ["test"], ["test", "compliance", "audit"], "engine-team"
    ),
    FileMeta(
        "tests/compliance/test_hipaa.py", "engine-specific", ["test"], ["test", "compliance", "hipaa"], "engine-team"
    ),
    FileMeta(
        "tests/compliance/test_prohibited_factors.py",
        "engine-specific",
        ["test"],
        ["test", "compliance", "prohibited-factors"],
        "engine-team",
    ),
    # --- Tests: Integration ---
    FileMeta(
        "tests/integration/test_multi_tenant.py",
        "engine-specific",
        ["test"],
        ["test", "integration", "multi-tenant"],
        "engine-team",
    ),
    FileMeta(
        "tests/integration/test_null_semantics.py",
        "engine-specific",
        ["test"],
        ["test", "integration", "null-semantics"],
        "engine-team",
    ),
    # --- Tests: Performance ---
    FileMeta(
        "tests/performance/test_query_latency.py",
        "engine-specific",
        ["test"],
        ["test", "performance", "latency"],
        "engine-team",
    ),
    FileMeta(
        "tests/performance/test_sync_throughput.py",
        "engine-specific",
        ["test"],
        ["test", "performance", "throughput"],
        "engine-team",
    ),
    # --- Tests: Root Level ---
    FileMeta("tests/test_compliance_engine.py", "engine-specific", ["test"], ["test", "compliance"], "engine-team"),
    FileMeta("tests/test_config_loader.py", "engine-specific", ["test"], ["test", "config"], "engine-team"),
    FileMeta("tests/test_enrich.py", "engine-specific", ["test"], ["test", "enrich"], "engine-team"),
    FileMeta("tests/test_handlers.py", "engine-specific", ["test"], ["test", "handlers"], "engine-team"),
    FileMeta("tests/test_scoring_extended.py", "engine-specific", ["test"], ["test", "scoring"], "engine-team"),
    # --- Tests: Unit ---
    FileMeta(
        "tests/unit/test_api_error_handling.py", "engine-specific", ["test"], ["test", "unit", "api"], "engine-team"
    ),
    FileMeta("tests/unit/test_chassis_app.py", "engine-specific", ["test"], ["test", "unit", "chassis"], "engine-team"),
    FileMeta(
        "tests/unit/test_chassis_contract.py", "engine-specific", ["test"], ["test", "unit", "chassis"], "engine-team"
    ),
    FileMeta("tests/unit/test_config.py", "engine-specific", ["test"], ["test", "unit", "config"], "engine-team"),
    FileMeta(
        "tests/unit/test_config_schema.py", "engine-specific", ["test"], ["test", "unit", "config"], "engine-team"
    ),
    FileMeta(
        "tests/unit/test_domain_pack_loader.py", "engine-specific", ["test"], ["test", "unit", "config"], "engine-team"
    ),
    FileMeta(
        "tests/unit/test_gates_all_types.py", "engine-specific", ["test"], ["test", "unit", "gates"], "engine-team"
    ),
    FileMeta("tests/unit/test_gds_scheduler.py", "engine-specific", ["test"], ["test", "unit", "gds"], "engine-team"),
    FileMeta(
        "tests/unit/test_handlers_enrich_health.py",
        "engine-specific",
        ["test"],
        ["test", "unit", "handlers"],
        "engine-team",
    ),
    FileMeta(
        "tests/unit/test_handlers_extended.py", "engine-specific", ["test"], ["test", "unit", "handlers"], "engine-team"
    ),
    FileMeta("tests/unit/test_kge_beam_search.py", "engine-specific", ["test"], ["test", "unit", "kge"], "engine-team"),
    FileMeta(
        "tests/unit/test_kge_compound_e3d.py", "engine-specific", ["test"], ["test", "unit", "kge"], "engine-team"
    ),
    FileMeta("tests/unit/test_kge_ensemble.py", "engine-specific", ["test"], ["test", "unit", "kge"], "engine-team"),
    FileMeta(
        "tests/unit/test_kge_transformations.py", "engine-specific", ["test"], ["test", "unit", "kge"], "engine-team"
    ),
    FileMeta(
        "tests/unit/test_packet_envelope.py", "engine-specific", ["test"], ["test", "unit", "packet"], "engine-team"
    ),
    FileMeta("tests/unit/test_safe_eval.py", "engine-specific", ["test"], ["test", "unit", "utils"], "engine-team"),
    FileMeta("tests/unit/test_scoring.py", "engine-specific", ["test"], ["test", "unit", "scoring"], "engine-team"),
    FileMeta(
        "tests/unit/test_scoring_security.py", "engine-specific", ["test"], ["test", "unit", "scoring"], "engine-team"
    ),
    FileMeta("tests/unit/test_settings.py", "engine-specific", ["test"], ["test", "unit", "config"], "engine-team"),
    FileMeta("tests/unit/test_sync.py", "engine-specific", ["test"], ["test", "unit", "sync"], "engine-team"),
    FileMeta("tests/unit/test_traversal.py", "engine-specific", ["test"], ["test", "unit", "traversal"], "engine-team"),
    FileMeta("tests/unit/test_units.py", "engine-specific", ["test"], ["test", "unit", "units"], "engine-team"),
    # =========================================================================
    # ENGINE-SPECIFIC FILES  (origin: engine-specific, owner: engine-team)
    # =========================================================================
    FileMeta("engine/__init__.py", "engine-specific", ["config"], ["engine-core"], "engine-team"),
    FileMeta("engine/handlers.py", "engine-specific", ["config"], ["chassis-bridge", "handlers"], "engine-team"),
    FileMeta("engine/config/__init__.py", "engine-specific", ["config"], ["config"], "engine-team"),
    FileMeta("engine/config/loader.py", "engine-specific", ["config"], ["config", "domain-loader"], "engine-team"),
    FileMeta(
        "engine/config/schema.py", "engine-specific", ["config"], ["config", "pydantic", "domain-spec"], "engine-team"
    ),
    FileMeta("engine/config/settings.py", "engine-specific", ["config"], ["config", "settings"], "engine-team"),
    FileMeta("engine/config/units.py", "engine-specific", ["config"], ["config", "units"], "engine-team"),
    FileMeta("engine/gates/__init__.py", "engine-specific", ["config"], ["gates"], "engine-team"),
    FileMeta("engine/gates/compiler.py", "engine-specific", ["config"], ["gates", "compiler", "cypher"], "engine-team"),
    FileMeta(
        "engine/gates/null_semantics.py", "engine-specific", ["config"], ["gates", "null-semantics"], "engine-team"
    ),
    FileMeta("engine/gates/registry.py", "engine-specific", ["config"], ["gates", "registry"], "engine-team"),
    FileMeta("engine/gates/types/__init__.py", "engine-specific", ["config"], ["gates", "types"], "engine-team"),
    FileMeta(
        "engine/gates/types/all_gates.py",
        "engine-specific",
        ["config"],
        ["gates", "types", "implementation"],
        "engine-team",
    ),
    FileMeta("engine/scoring/__init__.py", "engine-specific", ["config"], ["scoring"], "engine-team"),
    FileMeta(
        "engine/scoring/assembler.py", "engine-specific", ["config"], ["scoring", "assembler", "cypher"], "engine-team"
    ),
    FileMeta("engine/traversal/__init__.py", "engine-specific", ["config"], ["traversal"], "engine-team"),
    FileMeta(
        "engine/traversal/assembler.py",
        "engine-specific",
        ["config"],
        ["traversal", "assembler", "cypher"],
        "engine-team",
    ),
    FileMeta("engine/traversal/resolver.py", "engine-specific", ["config"], ["traversal", "resolver"], "engine-team"),
    FileMeta("engine/sync/__init__.py", "engine-specific", ["config"], ["sync"], "engine-team"),
    FileMeta("engine/sync/generator.py", "engine-specific", ["config"], ["sync", "cypher", "merge"], "engine-team"),
    FileMeta("engine/gds/__init__.py", "engine-specific", ["config"], ["gds"], "engine-team"),
    FileMeta("engine/gds/scheduler.py", "engine-specific", ["config"], ["gds", "scheduler", "louvain"], "engine-team"),
    FileMeta("engine/graph/__init__.py", "engine-specific", ["config"], ["graph", "driver"], "engine-team"),
    FileMeta("engine/graph/driver.py", "engine-specific", ["config"], ["graph", "driver", "neo4j"], "engine-team"),
    FileMeta("engine/compliance/__init__.py", "engine-specific", ["config"], ["compliance"], "engine-team"),
    FileMeta("engine/compliance/audit.py", "engine-specific", ["config"], ["compliance", "audit"], "engine-team"),
    FileMeta("engine/compliance/pii.py", "engine-specific", ["config"], ["compliance", "pii"], "engine-team"),
    FileMeta(
        "engine/compliance/prohibited_factors.py",
        "engine-specific",
        ["config"],
        ["compliance", "prohibited-factors"],
        "engine-team",
    ),
    FileMeta("engine/packet/__init__.py", "engine-specific", ["config"], ["packet"], "engine-team"),
    FileMeta(
        "engine/packet/packet_envelope.py",
        "engine-specific",
        ["config"],
        ["packet", "envelope", "pydantic"],
        "engine-team",
    ),
    FileMeta(
        "engine/packet/chassis_contract.py", "engine-specific", ["config"], ["packet", "chassis-bridge"], "engine-team"
    ),
    FileMeta("engine/utils/__init__.py", "engine-specific", ["config"], ["utils"], "engine-team"),
    FileMeta("engine/utils/safe_eval.py", "engine-specific", ["config"], ["utils", "safe-eval"], "engine-team"),
    FileMeta(
        "engine/utils/security.py", "engine-specific", ["config"], ["utils", "security", "sanitize"], "engine-team"
    ),
    FileMeta("engine/boot.py", "engine-specific", ["config"], ["engine", "boot", "lifecycle"], "engine-team"),
    # --- Engine KGE (Knowledge Graph Embeddings) ---
    FileMeta("engine/kge/__init__.py", "engine-specific", ["kge"], ["kge", "embeddings"], "engine-team"),
    FileMeta(
        "engine/kge/beam_search.py",
        "engine-specific",
        ["kge"],
        ["kge", "beam-search", "link-prediction"],
        "engine-team",
    ),
    FileMeta("engine/kge/compound_e3d.py", "engine-specific", ["kge"], ["kge", "compound-e3d", "model"], "engine-team"),
    FileMeta("engine/kge/ensemble.py", "engine-specific", ["kge"], ["kge", "ensemble", "aggregation"], "engine-team"),
    FileMeta("engine/kge/transformations.py", "engine-specific", ["kge"], ["kge", "transformations"], "engine-team"),
    # --- Engine Compliance (additional) ---
    FileMeta("engine/compliance/engine.py", "engine-specific", ["compliance"], ["compliance", "engine"], "engine-team"),
    # --- Engine Security ---
    FileMeta("engine/security/5_llm_security.py", "engine-specific", ["security"], ["security", "llm"], "engine-team"),
    FileMeta(
        "engine/security/P2_9_llm_schemas.py",
        "engine-specific",
        ["security"],
        ["security", "llm", "schemas"],
        "engine-team",
    ),
    FileMeta(
        "engine/security/5_prompt_injection_semgrep.yaml",
        "engine-specific",
        ["security"],
        ["security", "semgrep", "prompt-injection"],
        "engine-team",
    ),
    # --- Tools (additional) ---
    FileMeta("tools/audit_dispatch.py", "l9-template", ["audit"], ["L9_TEMPLATE", "audit", "dispatch"], "platform"),
    FileMeta("tools/contract_scanner.py", "l9-template", ["audit"], ["L9_TEMPLATE", "audit", "contracts"], "platform"),
    FileMeta("tools/verify_contracts.py", "l9-template", ["audit"], ["L9_TEMPLATE", "audit", "verify"], "platform"),
    FileMeta("tools/auditors/__init__.py", "l9-template", ["audit"], ["L9_TEMPLATE", "auditors"], "platform"),
    FileMeta("tools/auditors/base.py", "l9-template", ["audit"], ["L9_TEMPLATE", "auditors", "base"], "platform"),
    FileMeta(
        "tools/auditors/api_regression.py", "l9-template", ["audit"], ["L9_TEMPLATE", "auditors", "api"], "platform"
    ),
    FileMeta(
        "tools/auditors/log_safety.py", "l9-template", ["audit"], ["L9_TEMPLATE", "auditors", "logging"], "platform"
    ),
    FileMeta(
        "tools/auditors/query_performance.py",
        "l9-template",
        ["audit"],
        ["L9_TEMPLATE", "auditors", "performance"],
        "platform",
    ),
    FileMeta(
        "tools/auditors/test_quality.py",
        "l9-template",
        ["audit"],
        ["L9_TEMPLATE", "auditors", "test-quality"],
        "platform",
    ),
    # --- Chassis Entrypoint ---
    FileMeta("chassis/entrypoint.sh", "chassis", ["docker"], ["chassis", "entrypoint"], "platform-team"),
    # --- Tools Shell Scripts ---
    FileMeta("tools/deploy/deploy.sh", "l9-template", ["scripts", "deploy"], ["L9_TEMPLATE", "deploy"], "platform"),
    FileMeta("tools/dev/dev_up.sh", "l9-template", ["scripts", "dev"], ["L9_TEMPLATE", "dev"], "platform"),
    FileMeta(
        "tools/hooks/install_hooks.sh", "l9-template", ["scripts", "hooks"], ["L9_TEMPLATE", "git-hooks"], "platform"
    ),
    FileMeta(
        "tools/infra/check_env.sh",
        "l9-template",
        ["scripts", "infra"],
        ["L9_TEMPLATE", "infra", "env-check"],
        "platform",
    ),
    FileMeta(
        "tools/infra/deep_mri.sh",
        "l9-template",
        ["scripts", "infra"],
        ["L9_TEMPLATE", "infra", "diagnostics"],
        "platform",
    ),
    FileMeta(
        "tools/infra/docker_validate.sh",
        "l9-template",
        ["scripts", "infra"],
        ["L9_TEMPLATE", "infra", "docker"],
        "platform",
    ),
    FileMeta(
        "tools/infra/precommit_smoke.sh",
        "l9-template",
        ["scripts", "infra"],
        ["L9_TEMPLATE", "infra", "precommit"],
        "platform",
    ),
    FileMeta(
        "tools/infra/test_everything.sh",
        "l9-template",
        ["scripts", "infra"],
        ["L9_TEMPLATE", "infra", "test"],
        "platform",
    ),
    # --- Core Markdown Docs (root) ---
    FileMeta("README.md", "engine-specific", ["docs"], ["readme", "overview"], "engine-team"),
    FileMeta("CHANGELOG.md", "engine-specific", ["docs"], ["changelog"], "engine-team"),
    FileMeta("ROADMAP.md", "engine-specific", ["docs"], ["roadmap", "planning"], "engine-team"),
    FileMeta("TODO.md", "engine-specific", ["docs"], ["todo", "planning"], "engine-team"),
    FileMeta("Readme-Requirements.md", "engine-specific", ["docs"], ["requirements"], "engine-team"),
    FileMeta("workflow_state.md", "engine-specific", ["docs"], ["workflow", "state"], "engine-team"),
    FileMeta(".gitleaks.toml", "l9-template", ["security"], ["L9_TEMPLATE", "gitleaks", "secrets"], "platform"),
    # --- docs/ folder ---
    FileMeta("docs/ARCHITECTURE.md", "engine-specific", ["docs"], ["architecture", "design"], "engine-team"),
    FileMeta("docs/ACTION ITEMS.MD", "engine-specific", ["docs"], ["action-items"], "engine-team"),
    FileMeta("docs/Audit Harness-Explained.md", "engine-specific", ["docs"], ["audit", "harness"], "engine-team"),
    FileMeta("docs/What the Audit Harness Does.md", "engine-specific", ["docs"], ["audit", "harness"], "engine-team"),
    FileMeta("docs/GRAPH-architecture.md", "engine-specific", ["docs"], ["architecture", "graph"], "engine-team"),
    FileMeta(
        "docs/L9_Contract_Enforcement_System.md",
        "engine-specific",
        ["docs"],
        ["contracts", "enforcement"],
        "engine-team",
    ),
    FileMeta(
        "docs/PlasticOS Graph Cognitive Engine.yaml", "engine-specific", ["docs"], ["plasticos", "spec"], "engine-team"
    ),
    FileMeta(
        "docs/plasticos_domain_spec_v0.3.0.yaml",
        "domain-specific",
        ["docs"],
        ["plasticos", "spec", "v0.3"],
        "domain-team",
    ),
    FileMeta(
        "docs/plasticos_domain_spec_v0.4.yaml",
        "domain-specific",
        ["docs"],
        ["plasticos", "spec", "v0.4"],
        "domain-team",
    ),
    # L9_Platform_Architecture.md and L9_AI_Constellation_Infrastructure_Reference.md
    # are referenced in CLAUDE.md but live in the L9 platform repo, not here
    # --- docs/Dev-Docs ---
    FileMeta(
        "docs/Dev-Docs/cognitive-engine-revenue-patterns.md",
        "engine-specific",
        ["docs"],
        ["dev-docs", "revenue"],
        "engine-team",
    ),
    FileMeta(
        "docs/Dev-Docs/top3_graph_pattern_analysis.json",
        "engine-specific",
        ["docs"],
        ["dev-docs", "analysis"],
        "engine-team",
    ),
    FileMeta(
        "docs/Dev-Docs/top5_leverage_patterns_detailed.json",
        "engine-specific",
        ["docs"],
        ["dev-docs", "analysis"],
        "engine-team",
    ),
    FileMeta(
        "docs/Dev-Docs/universal_graph_schema.json", "engine-specific", ["docs"], ["dev-docs", "schema"], "engine-team"
    ),
    # --- docs/agent-tasks ---
    FileMeta(
        "docs/agent-tasks/add-domain-spec.md",
        "engine-specific",
        ["docs"],
        ["agent-tasks", "domain-spec"],
        "engine-team",
    ),
    FileMeta("docs/agent-tasks/add-gate-type.md", "engine-specific", ["docs"], ["agent-tasks", "gates"], "engine-team"),
    FileMeta(
        "docs/agent-tasks/add-action-handler.md",
        "engine-specific",
        ["docs"],
        ["agent-tasks", "handlers"],
        "engine-team",
    ),
    FileMeta(
        "docs/agent-tasks/extend-contract.md", "engine-specific", ["docs"], ["agent-tasks", "contracts"], "engine-team"
    ),
    FileMeta(
        "docs/agent-tasks/fix-api-regression.md", "engine-specific", ["docs"], ["agent-tasks", "api"], "engine-team"
    ),
    FileMeta(
        "docs/agent-tasks/fix-audit-finding.md", "engine-specific", ["docs"], ["agent-tasks", "audit"], "engine-team"
    ),
    FileMeta(
        "docs/agent-tasks/fix-log-safety.md", "engine-specific", ["docs"], ["agent-tasks", "logging"], "engine-team"
    ),
    FileMeta(
        "docs/agent-tasks/fix-test-quality.md", "engine-specific", ["docs"], ["agent-tasks", "testing"], "engine-team"
    ),
    # --- docs/misc ---
    FileMeta(
        "docs/plasticos_domain_spec_changes.md", "domain-specific", ["docs"], ["plasticos", "changelog"], "domain-team"
    ),
    # --- docs/contracts ---
    FileMeta(
        "docs/contracts/FIELD_NAMES.md", "l9-template", ["docs", "contracts"], ["L9_TEMPLATE", "contracts"], "platform"
    ),
    FileMeta(
        "docs/contracts/METHOD_SIGNATURES.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/CYPHER_SAFETY.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts", "cypher"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/BANNED_PATTERNS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/ERROR_HANDLING.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/HANDLER_PAYLOADS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/PYDANTIC_YAML_MAPPING.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/DEPENDENCY_INJECTION.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/TEST_PATTERNS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/RETURN_VALUES.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/PACKET_ENVELOPE_FIELDS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts", "packet"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/DELEGATION_PROTOCOL.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/PACKET_TYPE_REGISTRY.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts", "packet"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/DOMAIN_SPEC_VERSIONING.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/FEEDBACK_LOOPS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/NODE_REGISTRATION.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/ENV_VARS.md", "l9-template", ["docs", "contracts"], ["L9_TEMPLATE", "contracts"], "platform"
    ),
    FileMeta(
        "docs/contracts/OBSERVABILITY.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/MEMORY_SUBSTRATE_ACCESS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    FileMeta(
        "docs/contracts/SHARED_MODELS.md",
        "l9-template",
        ["docs", "contracts"],
        ["L9_TEMPLATE", "contracts"],
        "platform",
    ),
    # --- engine/packet ---
    FileMeta(
        "engine/packet/README-Packet Envelope.md", "engine-specific", ["docs"], ["packet", "envelope"], "engine-team"
    ),
    # --- artifacts ---
    FileMeta("artifacts/audit_report.md", "engine-specific", ["artifacts"], ["audit", "report"], "engine-team"),
    FileMeta("artifacts/coverage_report.md", "engine-specific", ["artifacts"], ["coverage", "report"], "engine-team"),
    FileMeta("artifacts/coverage_matrix.json", "engine-specific", ["artifacts"], ["coverage", "matrix"], "engine-team"),
    FileMeta("artifacts/spec_checklist.json", "engine-specific", ["artifacts"], ["spec", "checklist"], "engine-team"),
    # --- reports ---
    FileMeta(
        "reports/GAP-ANALYSIS-Audit-Harness-and-Spec-Coverage.md",
        "engine-specific",
        ["reports"],
        ["gap-analysis"],
        "engine-team",
    ),
    FileMeta(
        "reports/GMP-Report-130-Contract-Enforcement-System.md",
        "engine-specific",
        ["reports"],
        ["gmp-report"],
        "engine-team",
    ),
    # --- templates ---
    FileMeta(
        "templates/styleguide.template.md", "l9-template", ["templates"], ["L9_TEMPLATE", "styleguide"], "platform"
    ),
    # --- Additional YAML configs ---
    FileMeta(".github/workflows/ci-quality.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "quality"], "platform"),
    FileMeta(".github/workflows/contracts.yml", "l9-template", ["ci"], ["L9_TEMPLATE", "ci", "contracts"], "platform"),
    FileMeta(
        ".semgrep/semgrep-rules.yaml", "l9-template", ["security"], ["L9_TEMPLATE", "semgrep", "rules"], "platform"
    ),
    FileMeta("domains/_template.yaml", "domain-specific", ["config"], ["domains", "template"], "domain-team"),
    FileMeta(
        "domains/plasticos_domain_spec.yaml", "domain-specific", ["config"], ["domains", "plasticos"], "domain-team"
    ),
    FileMeta("domains/plasticos/spec.yaml", "domain-specific", ["config"], ["domains", "plasticos"], "domain-team"),
    FileMeta("chassis/__init__.py", "chassis", ["api"], ["chassis"], "platform-team"),
    FileMeta("chassis/actions.py", "chassis", ["api"], ["chassis", "actions"], "platform-team"),
    FileMeta("chassis/action_registry.py", "chassis", ["api"], ["chassis", "registry"], "platform-team"),
    FileMeta("chassis/app.py", "chassis", ["api"], ["chassis", "fastapi", "legacy"], "platform-team"),
    FileMeta("chassis/audit.py", "chassis", ["api"], ["chassis", "audit"], "platform-team"),
    FileMeta("chassis/chassis_app.py", "chassis", ["api"], ["chassis", "fastapi", "single-ingress"], "platform-team"),
    FileMeta("chassis/config.py", "chassis", ["api", "config"], ["chassis", "settings"], "platform-team"),
    FileMeta("chassis/engine_boot.py", "chassis", ["api"], ["chassis", "lifecycle", "boot"], "platform-team"),
    FileMeta("chassis/errors.py", "chassis", ["api"], ["chassis", "errors", "exceptions"], "platform-team"),
    FileMeta("chassis/health.py", "chassis", ["api"], ["chassis", "health", "readiness"], "platform-team"),
    FileMeta("chassis/middleware.py", "chassis", ["api"], ["chassis", "middleware", "tenant"], "platform-team"),
    FileMeta("chassis/orchestrator.py", "chassis", ["api"], ["chassis", "orchestrator"], "platform-team"),
    FileMeta("chassis/pii.py", "chassis", ["api", "compliance"], ["chassis", "pii", "redaction"], "platform-team"),
    FileMeta("chassis/router.py", "chassis", ["api"], ["chassis", "router", "action-dispatch"], "platform-team"),
    FileMeta("chassis/types.py", "chassis", ["api"], ["chassis", "types", "pydantic"], "platform-team"),
    # --- Chassis Auth Submodule ---
    FileMeta("chassis/auth/app.py", "chassis", ["api", "auth"], ["chassis", "auth", "fastapi"], "platform-team"),
    FileMeta("chassis/auth/auth.py", "chassis", ["api", "auth"], ["chassis", "auth", "middleware"], "platform-team"),
    FileMeta(
        "chassis/auth/generate_l9_api_key.py",
        "chassis",
        ["api", "auth"],
        ["chassis", "auth", "keygen"],
        "platform-team",
    ),
    FileMeta(
        "chassis/auth/settings.py",
        "chassis",
        ["api", "auth", "config"],
        ["chassis", "auth", "settings"],
        "platform-team",
    ),
    FileMeta(
        "chassis/auth/test_auth_middleware.py",
        "chassis",
        ["api", "auth", "test"],
        ["chassis", "auth", "test"],
        "platform-team",
    ),
    FileMeta(
        "pyproject.toml", "engine-specific", ["build", "config"], ["build", "dependencies", "poetry"], "engine-team"
    ),
    FileMeta(
        "graph-cognitive-engine-spec-v1.1.0.yaml", "engine-specific", ["config"], ["spec", "engine-spec"], "engine-team"
    ),
    # =========================================================================
    # DOMAIN-SPECIFIC FILES  (origin: domain-specific, owner: domain-team)
    # =========================================================================
    FileMeta(
        "domains/MASTER-SPEC-ALL-DOMAINS.yaml", "domain-specific", ["config"], ["domains", "master-spec"], "domain-team"
    ),
    FileMeta("domains/README.md", "domain-specific", ["config"], ["domains", "docs"], "domain-team"),
    FileMeta("domains/TESTING_GUIDE.md", "domain-specific", ["test"], ["domains", "testing", "guide"], "domain-team"),
    # domains/domain_extractor.py doesn't exist (removed or renamed)
    FileMeta(
        "domains/mortgage_brokerage_domain_spec.yaml",
        "domain-specific",
        ["config"],
        ["domains", "mortgage"],
        "domain-team",
    ),
    FileMeta(
        "domains/healthcare_referral_domain_spec.yaml",
        "domain-specific",
        ["config"],
        ["domains", "healthcare"],
        "domain-team",
    ),
    FileMeta(
        "domains/freight_matching_domain_spec.yaml",
        "domain-specific",
        ["config"],
        ["domains", "freight"],
        "domain-team",
    ),
    FileMeta(
        "domains/legal_discovery_domain_spec.yaml", "domain-specific", ["config"], ["domains", "legal"], "domain-team"
    ),
    FileMeta(
        "domains/roofing_company_domain_spec.yaml", "domain-specific", ["config"], ["domains", "roofing"], "domain-team"
    ),
    FileMeta(
        "domains/executive_assistant_domain_spec.yaml",
        "domain-specific",
        ["config"],
        ["domains", "executive-assistant"],
        "domain-team",
    ),
    FileMeta(
        "domains/aios_god_agent_domain_spec.yaml", "domain-specific", ["config"], ["domains", "aios"], "domain-team"
    ),
    FileMeta(
        "domains/repo_as_agent_domain_spec.yaml",
        "domain-specific",
        ["config"],
        ["domains", "repo-agent"],
        "domain-team",
    ),
    FileMeta(
        "domains/research_agent_domain_spec.yaml",
        "domain-specific",
        ["config"],
        ["domains", "research-agent"],
        "domain-team",
    ),
]


# =============================================================================
# FORMATTERS — One per filetype family
# =============================================================================


def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def format_comment_block(meta: FileMeta, engine: str, prefix: str = "# ") -> str:
    """Format L9_META as comment block for YAML, shell, Makefile, Dockerfile, etc."""
    lines = [
        f"{prefix}",
    ]
    return "\n".join(lines)


def format_html_comment(meta: FileMeta, engine: str) -> str:
    """Format L9_META as HTML comment for Markdown files."""
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
    """Format L9_META for Python docstring insertion."""
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
        f"layer = [{layer_str}]",
        f"tags = [{tags_str}]",
        f'owner = "{meta.owner}"',
        f'status = "{meta.status}"',
    ]
    return "\n".join(lines)


# =============================================================================
# STRIP EXISTING — Regex patterns for idempotent re-injection
# =============================================================================

# Matches comment-style L9_META blocks (YAML, shell, Makefile, Dockerfile, Python without docstring)
# Example:
RE_COMMENT_META = re.compile(
    r"^[ \t]*#[ \t]*---[ \t]*L9_META[ \t]*---.*?#[ \t]*---[ \t]*/L9_META[ \t]*---[ \t]*\n?",
    re.MULTILINE | re.DOTALL,
)

# Matches HTML comment L9_META blocks (Markdown)
# Example:
#   <!-- L9_META
#   l9_schema: 1
#   ...
#   /L9_META -->
RE_HTML_META = re.compile(
    r"<!-- L9_META.*?/L9_META -->[ \t]*\n?",
    re.DOTALL,
)

# Matches L9_META inside Python docstrings
# Example:
#   """
RE_PY_DOCSTRING_META = re.compile(
    r"---[ \t]*L9_META[ \t]*---.*?---[ \t]*/L9_META[ \t]*---[ \t]*\n?",
    re.DOTALL,
)

# Matches broken/uncommented L9_META blocks in YAML files (missing # prefix)
# These need to be stripped before injecting the correct comment-style block
RE_BROKEN_YAML_META = re.compile(
    r"^---[ \t]*L9_META[ \t]*---.*?---[ \t]*/L9_META[ \t]*---[ \t]*\n?",
    re.MULTILINE | re.DOTALL,
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


def _inject_python_meta(content: str, meta: FileMeta, engine: str) -> str:
    """Inject L9_META into Python files using docstring style."""
    # Strip existing meta from docstring if present
    content = RE_PY_DOCSTRING_META.sub("", content)
    # Also strip comment-style meta if someone added it wrong
    content = RE_COMMENT_META.sub("", content)

    meta_block = format_python_docstring_block(meta, engine)

    # Check for existing docstring at start of file (after optional shebang)
    shebang = ""
    working_content = content.lstrip("\n")
    if working_content.startswith("#!"):
        nl = working_content.index("\n")
        shebang = working_content[: nl + 1]
        working_content = working_content[nl + 1 :]

    # Strip leading whitespace/newlines and any orphaned comments before docstring
    working_content = working_content.lstrip("\n")

    # Match existing docstring (may be preceded by comments we should skip)
    ds_match = re.search(r'^(""")(.*?)(""")', working_content, re.MULTILINE | re.DOTALL)
    if ds_match:
        # Skip any content before the docstring (orphaned comments, stale paths)
        opening = ds_match.group(1)
        body = ds_match.group(2)
        closing = ds_match.group(3)
        post_docstring = working_content[ds_match.end() :]

        # Strip any existing L9_META from body
        body = RE_PY_DOCSTRING_META.sub("", body)
        body_stripped = body.lstrip("\n")

        # Build new docstring with meta at top
        if body_stripped:
            new_ds = f"{opening}\n{meta_block}\n\n{body_stripped}{closing}"
        else:
            new_ds = f"{opening}\n{meta_block}\n{closing}"

        # Don't preserve orphaned comments before docstring (they're usually stale paths)
        return shebang + new_ds + post_docstring

    # No existing docstring — create one with just the meta block
    return shebang + f'"""\n{meta_block}\n"""\n' + working_content


def _inject_comment_meta(content: str, meta: FileMeta, engine: str) -> str:
    """Inject L9_META using comment-style for shell, YAML, etc."""
    content = RE_COMMENT_META.sub("", content)
    block = format_comment_block(meta, engine)
    if content.startswith("#!"):
        nl = content.index("\n")
        return content[: nl + 1] + block + "\n" + content[nl + 1 :]
    return block + "\n" + content


def inject_meta(content: str, meta: FileMeta, engine: str) -> str:
    """Inject L9_META header into file content based on filetype."""
    ftype = _detect_filetype(meta.path)

    # --- JSON ---
    if ftype == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return content
        # Only inject _l9_meta into objects, not arrays (arrays would break structure)
        if not isinstance(data, dict):
            return content  # Skip arrays - can't inject meta without breaking structure
        data["_l9_meta"] = format_json_meta(meta, engine)
        ordered = {"_l9_meta": data.pop("_l9_meta")}
        ordered.update(data)
        return json.dumps(ordered, indent=2) + "\n"

    # --- TOML ---
    if ftype == "toml":
        block = format_toml_block(meta, engine)
        cleaned = re.sub(r"\n?\[tool\.l9_meta\].*?(?=\n\[|\Z)", "", content, flags=re.DOTALL).rstrip() + "\n"
        return cleaned + block + "\n"

    # --- Markdown ---
    if ftype == "markdown":
        content = RE_HTML_META.sub("", content)
        block = format_html_comment(meta, engine)
        return block + "\n\n" + content.lstrip("\n")

    # --- Python ---
    if ftype == "python":
        return _inject_python_meta(content, meta, engine)

    # --- Shell ---
    if ftype == "shell":
        content = RE_COMMENT_META.sub("", content)
        block = format_comment_block(meta, engine)
        if content.startswith("#!"):
            nl = content.index("\n")
            return content[: nl + 1] + block + "\n" + content[nl + 1 :]
        return block + "\n" + content

    # --- YAML ---
    if ftype == "yaml":
        # Strip both comment-style and broken (uncommented) meta blocks
        content = RE_COMMENT_META.sub("", content)
        content = RE_BROKEN_YAML_META.sub("", content)
        block = format_comment_block(meta, engine)
        # Handle YAML document separator
        content_stripped = content.lstrip()
        if content_stripped.startswith("---"):
            # Find the first --- that's a YAML doc separator (not part of meta)
            idx = content.index("---")
            return block + "\n" + content[idx:]
        return block + "\n" + content.lstrip()

    # --- Fallback: comment-style ---
    content = RE_COMMENT_META.sub("", content)
    block = format_comment_block(meta, engine)
    if content.startswith("#!"):
        nl = content.index("\n")
        return content[: nl + 1] + block + "\n" + content[nl + 1 :]
    return block + "\n" + content


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject L9_META headers into all tracked files")
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
        print("\n  >>> Dry-run mode. Run with --apply to write changes.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
