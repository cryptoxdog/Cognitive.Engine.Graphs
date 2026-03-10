
## What the Audit Harness Does (and Doesn't)

### ✅ What It Does

| Capability | How | Example |
| :-- | :-- | :-- |
| **Banned pattern detection** | Walks every `.py` file via `pathlib.rglob()`, matches string/regex patterns per rule | Finds `from fastapi import APIRouter` in `engine/scoring/assembler.py` line 3 |
| **Forbidden structure checks** | Verifies directories/files that must NOT exist | Fails if `engine/api/` or `engine/middleware.py` reappears |
| **Required structure checks** | Verifies directories/files/tokens that MUST exist | Fails if `engine/handlers.py` is missing or doesn't contain `register_all` |
| **Cypher injection pattern detection** | Regex-scans f-strings for label interpolation without `sanitize_label()` | Flags `f"MERGE (n:{spec.target_node} ...)"` with evidence snippet |
| **Lifecycle anchor verification** | Checks that match/sync/GDS flows reference expected components | Warns if `GateCompiler`, `TraversalAssembler`, `ScoringAssembler` aren't referenced in handler chain |
| **Evidence-based output** | Every finding includes file path + line range + 7-line code snippet | You see the exact code, not a vague description |
| **Severity-gated CI exit codes** | Returns exit code 1 if CRITICAL or HIGH findings exist | CI blocks merge; `make audit` fails locally |
| **Markdown report generation** | Writes `artifacts/audit_report.md` with grouped findings | Attach to PR, review with team, or feed back to Cursor |

### ❌ What It Does NOT Do

| Limitation | Why | What Covers It Instead |
| :-- | :-- | :-- |
| **Does not execute your code** | It's pure static analysis — never imports, never runs, never starts services | `pytest`, `make test` |
| **Does not validate Cypher syntax** | Can't parse Cypher grammar — only detects f-string interpolation patterns | Integration tests with real Neo4j (`testcontainers`) |
| **Does not test runtime behavior** | Can't verify `handle_match` returns correct candidates or scores | Unit tests (gate math), integration tests (full pipeline) |
| **Does not check Neo4j connectivity** | No database interaction whatsoever | `make dev` + `scripts/health.sh` |
| **Does not do type checking** | That's a different analysis pass entirely | `mypy --strict` (runs in CI separately) |
| **Does not validate domain spec semantics** | Can check YAML loads, but can't verify gates reference valid ontology properties | Pydantic validators in `engine/config/schema.py` + integration tests |
| **Does not format code** | Not a formatter | `ruff format .` |
| **Does not replace code review** | Catches mechanical violations, not design mistakes | CodeRabbit + human review |

### When to Run It

| Trigger | How | Why |
| :-- | :-- | :-- |
| **Before every commit** | `make audit` locally | Catch violations before they hit remote |
| **On every PR** (automated) | `.github/workflows/audit.yml` | Gate: blocks merge if CRITICAL/HIGH |
| **After scaffolding a new engine** | `make audit` on fresh clone | Verify template compliance before writing domain code |
| **After any refactor** | `make audit` | Catch regressions (e.g., someone re-adds FastAPI imports) |
| **When debugging agent drift** | Read `artifacts/audit_report.md` | Shows exactly what an agent broke and where |

### When NOT to Run It

- **Not for "does my code work?"** — that's tests
- **Not for "is my Cypher correct?"** — that's integration tests against Neo4j
- **Not for "is my domain spec valid?"** — that's Pydantic schema validation (though the spec extractor below adds partial coverage)

***

## The Spec Coverage Extractor: `tools/spec_extract.py`

This is the second half of the harness. It reads your 68KB [`graph-cognitive-engine-spec-v1.1.0.yaml`](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/blob/main/graph-cognitive-engine-spec-v1.1.0.yaml) and generates a structured checklist, then scans your code to produce a **coverage matrix** showing IMPLEMENTED / PARTIAL / MISSING for every spec feature.

**Create:** `tools/spec_extract.py`

```python
"""
tools/spec_extract.py
L9_TEMPLATE: true

Extracts required features from the graph-cognitive-engine spec YAML,
then scans engine/ code to produce a coverage matrix.

Usage:
    python tools/spec_extract.py                          # default spec path
    python tools/spec_extract.py --spec path/to/spec.yaml # custom spec path
    python tools/spec_extract.py --fail-on MISSING        # exit 1 if any MISSING

Outputs:
    artifacts/spec_checklist.json    — extracted features from spec
    artifacts/coverage_matrix.json   — IMPLEMENTED / PARTIAL / MISSING per feature
    artifacts/coverage_report.md     — human-readable markdown report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


L9_TEMPLATE_TAG = "L9_TEMPLATE"


class Status(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


@dataclass
class SpecFeature:
    category: str
    name: str
    spec_reference: str
    search_tokens: list[str] = field(default_factory=list)
    search_files: list[str] = field(default_factory=list)
    status: str = "MISSING"
    evidence_files: list[str] = field(default_factory=list)
    evidence_lines: list[str] = field(default_factory=list)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def deep_get(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def extract_gate_features(spec: dict) -> list[SpecFeature]:
    features = []
    gates_section = deep_get(spec, "gates", default={})

    if isinstance(gates_section, dict):
        gate_types = gates_section.get("types", gates_section.get("gate_types", {}))
        if isinstance(gate_types, dict):
            for gate_name, gate_def in gate_types.items():
                features.append(SpecFeature(
                    category="gates",
                    name=gate_name,
                    spec_reference=f"gates.types.{gate_name}",
                    search_tokens=[
                        gate_name,
                        gate_name.replace("_", ""),
                        f"class {gate_name.title().replace('_', '')}Gate",
                        f'"{gate_name}"',
                        f"'{gate_name}'",
                        f"GateType.{gate_name.upper()}",
                    ],
                    search_files=["engine/gates/**/*.py"],
                ))
        elif isinstance(gate_types, list):
            for item in gate_types:
                name = item if isinstance(item, str) else item.get("type", item.get("name", str(item)))
                features.append(SpecFeature(
                    category="gates",
                    name=str(name),
                    spec_reference=f"gates.types.{name}",
                    search_tokens=[
                        str(name),
                        str(name).replace("_", ""),
                        f"class {str(name).title().replace('_', '')}Gate",
                        f'"{name}"',
                        f"GateType.{str(name).upper()}",
                    ],
                    search_files=["engine/gates/**/*.py"],
                ))

    if not features:
        all_text = json.dumps(spec)
        known_gates = [
            "range", "threshold", "boolean", "composite", "enum_map",
            "exclusion", "self_range", "freshness", "temporal_range",
            "traversal", "multi_range", "weighted_enum", "geo_radius",
            "set_intersection",
        ]
        for g in known_gates:
            if g in all_text or g.replace("_", "") in all_text:
                features.append(SpecFeature(
                    category="gates",
                    name=g,
                    spec_reference=f"gates (detected in spec text)",
                    search_tokens=[g, g.replace("_", ""), f'"{g}"', f"GateType.{g.upper()}"],
                    search_files=["engine/gates/**/*.py"],
                ))

    return features


def extract_scoring_features(spec: dict) -> list[SpecFeature]:
    features = []
    scoring = deep_get(spec, "scoring", default={})

    if isinstance(scoring, dict):
        dims = scoring.get("dimensions", scoring.get("computation_types", scoring.get("types", {})))
        if isinstance(dims, (dict, list)):
            items = dims.items() if isinstance(dims, dict) else enumerate(dims)
            for key, val in items:
                name = val if isinstance(val, str) else (val.get("type", val.get("name", str(key))) if isinstance(val, dict) else str(val))
                features.append(SpecFeature(
                    category="scoring",
                    name=str(name),
                    spec_reference=f"scoring.{name}",
                    search_tokens=[
                        str(name),
                        str(name).replace("_", ""),
                        f'"{name}"',
                        f"ScoringType.{str(name).upper()}",
                    ],
                    search_files=["engine/scoring/**/*.py"],
                ))

    if not features:
        all_text = json.dumps(spec)
        known_scoring = [
            "geo_decay", "log_normalized", "community_match",
            "inverse_linear", "candidate_property", "custom_cypher",
            "temporal_decay", "outcome_weighted", "set_overlap",
        ]
        for s in known_scoring:
            if s in all_text or s.replace("_", "") in all_text:
                features.append(SpecFeature(
                    category="scoring",
                    name=s,
                    spec_reference=f"scoring (detected in spec text)",
                    search_tokens=[s, s.replace("_", ""), f'"{s}"'],
                    search_files=["engine/scoring/**/*.py"],
                ))

    return features


def extract_ontology_features(spec: dict) -> list[SpecFeature]:
    features = []
    ontology = deep_get(spec, "ontology", default={})

    for section_key, category_label in [("nodes", "ontology_node"), ("edges", "ontology_edge")]:
        items = ontology.get(section_key, [])
        if isinstance(items, list):
            for item in items:
                name = item if isinstance(item, str) else item.get("label", item.get("type", item.get("name", str(item))))
                features.append(SpecFeature(
                    category=category_label,
                    name=str(name),
                    spec_reference=f"ontology.{section_key}.{name}",
                    search_tokens=[f'"{name}"', f"'{name}'", str(name)],
                    search_files=["engine/**/*.py", "domains/**/*.yaml"],
                ))
        elif isinstance(items, dict):
            for name in items:
                features.append(SpecFeature(
                    category=category_label,
                    name=str(name),
                    spec_reference=f"ontology.{section_key}.{name}",
                    search_tokens=[f'"{name}"', f"'{name}'", str(name)],
                    search_files=["engine/**/*.py", "domains/**/*.yaml"],
                ))

    return features


def extract_v11_additions(spec: dict) -> list[SpecFeature]:
    v11_nodes = ["TransactionOutcome", "SignalEvent"]
    v11_edges = ["RESULTED_IN", "RESOLVED_FROM"]
    v11_endpoints = ["outcomes", "resolve"]
    v11_scoring = ["temporal_decay", "outcome_weighted"]

    features = []
    for node in v11_nodes:
        features.append(SpecFeature(
            category="v1.1_node",
            name=node,
            spec_reference=f"v1.1 addition: {node} node",
            search_tokens=[node, f'"{node}"', f"'{node}'"],
            search_files=["engine/**/*.py", "domains/**/*.yaml"],
        ))
    for edge in v11_edges:
        features.append(SpecFeature(
            category="v1.1_edge",
            name=edge,
            spec_reference=f"v1.1 addition: {edge} edge",
            search_tokens=[edge, f'"{edge}"', f"'{edge}'"],
            search_files=["engine/**/*.py", "domains/**/*.yaml"],
        ))
    for ep in v11_endpoints:
        features.append(SpecFeature(
            category="v1.1_action",
            name=ep,
            spec_reference=f"v1.1 addition: {ep} action/endpoint",
            search_tokens=[f"handle_{ep}", f'"{ep}"', f"'{ep}'", ep],
            search_files=["engine/handlers.py", "engine/**/*.py"],
        ))
    for sc in v11_scoring:
        features.append(SpecFeature(
            category="v1.1_scoring",
            name=sc,
            spec_reference=f"v1.1 addition: {sc} scoring type",
            search_tokens=[sc, sc.replace("_", ""), f'"{sc}"'],
            search_files=["engine/scoring/**/*.py"],
        ))

    return features


def extract_action_features(spec: dict) -> list[SpecFeature]:
    actions = ["match", "sync", "admin", "query", "enrich", "healthcheck"]
    features = []
    for action in actions:
        features.append(SpecFeature(
            category="action_handler",
            name=action,
            spec_reference=f"chassis action: {action}",
            search_tokens=[f"handle_{action}", f'"{action}"', f"register_handler(\"{action}\""],
            search_files=["engine/handlers.py"],
        ))
    return features


def extract_gds_features(spec: dict) -> list[SpecFeature]:
    gds = deep_get(spec, "gds_jobs", default=deep_get(spec, "gds", default={}))
    features = []

    known_algos = ["louvain", "cooccurrence", "reinforcement", "temporal_recency",
                   "similarity", "pagerank", "label_propagation"]

    if isinstance(gds, dict):
        jobs = gds.get("jobs", gds.get("algorithms", []))
        if isinstance(jobs, list):
            for job in jobs:
                name = job if isinstance(job, str) else job.get("algorithm", job.get("name", str(job)))
                features.append(SpecFeature(
                    category="gds_algorithm",
                    name=str(name),
                    spec_reference=f"gds_jobs.{name}",
                    search_tokens=[str(name), f"_run_{name}", f'"{name}"'],
                    search_files=["engine/gds/**/*.py"],
                ))

    if not features:
        all_text = json.dumps(spec)
        for algo in known_algos:
            if algo in all_text:
                features.append(SpecFeature(
                    category="gds_algorithm",
                    name=algo,
                    spec_reference=f"gds (detected in spec text)",
                    search_tokens=[algo, f"_run_{algo}", f'"{algo}"'],
                    search_files=["engine/gds/**/*.py"],
                ))

    return features


def scan_codebase(root: Path, features: list[SpecFeature]) -> None:
    py_cache: dict[str, str] = {}
    yaml_cache: dict[str, str] = {}

    for py_file in root.rglob("*.py"):
        if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        try:
            py_cache[str(py_file.relative_to(root))] = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    for yaml_file in root.rglob("*.yaml"):
        if ".venv" in yaml_file.parts:
            continue
        try:
            yaml_cache[str(yaml_file.relative_to(root))] = yaml_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    all_files = {**py_cache, **yaml_cache}

    for feature in features:
        matched_files = []
        matched_lines = []

        search_scope = all_files
        if feature.search_files:
            filtered = {}
            for glob_pat in feature.search_files:
                for fpath, content in all_files.items():
                    norm_glob = glob_pat.replace("**/*", "").replace("**", "").rstrip("/")
                    if fpath.startswith(norm_glob.split("*")[^0].rstrip("/")):
                        filtered[fpath] = content
            if filtered:
                search_scope = filtered

        for fpath, content in search_scope.items():
            for token in feature.search_tokens:
                if token.lower() in content.lower():
                    matched_files.append(fpath)
                    for i, line in enumerate(content.splitlines(), 1):
                        if token.lower() in line.lower():
                            matched_lines.append(f"{fpath}:{i}")
                    break

        feature.evidence_files = sorted(set(matched_files))
        feature.evidence_lines = matched_lines[:10]

        if len(feature.evidence_files) >= 2:
            feature.status = Status.IMPLEMENTED.value
        elif len(feature.evidence_files) == 1:
            feature.status = Status.PARTIAL.value
        else:
            feature.status = Status.MISSING.value


def write_checklist(out_dir: Path, features: list[SpecFeature]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = [asdict(f) for f in features]
    (out_dir / "spec_checklist.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_coverage_matrix(out_dir: Path, features: list[SpecFeature]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    by_category: dict[str, dict[str, int]] = {}
    for f in features:
        cat = f.category
        if cat not in by_category:
            by_category[cat] = {"IMPLEMENTED": 0, "PARTIAL": 0, "MISSING": 0, "total": 0}
        by_category[cat][f.status] += 1
        by_category[cat]["total"] += 1

    totals = {"IMPLEMENTED": 0, "PARTIAL": 0, "MISSING": 0, "total": 0}
    for cat_data in by_category.values():
        for k in totals:
            totals[k] += cat_data[k]

    matrix = {"categories": by_category, "totals": totals, "generated_at": datetime.now(timezone.utc).isoformat()}
    (out_dir / "coverage_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")


def write_coverage_report(out_dir: Path, features: list[SpecFeature], matrix: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# L9 Spec Coverage Report")
    lines.append(f"\n- Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Template tag: `{L9_TEMPLATE_TAG}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | Implemented | Partial | Missing | Total |")
    lines.append("|----------|-------------|---------|---------|-------|")

    cats = json.loads((out_dir / "coverage_matrix.json").read_text())["categories"]
    for cat, data in cats.items():
        lines.append(f"| {cat} | {data['IMPLEMENTED']} | {data['PARTIAL']} | {data['MISSING']} | {data['total']} |")

    totals = json.loads((out_dir / "coverage_matrix.json").read_text())["totals"]
    lines.append(f"| **TOTAL** | **{totals['IMPLEMENTED']}** | **{totals['PARTIAL']}** | **{totals['MISSING']}** | **{totals['total']}** |")
    lines.append("")

    for status_filter in [Status.MISSING.value, Status.PARTIAL.value, Status.IMPLEMENTED.value]:
        filtered = [f for f in features if f.status == status_filter]
        if not filtered:
            continue

        icon = {"MISSING": "❌", "PARTIAL": "⚠️", "IMPLEMENTED": "✅"}[status_filter]
        lines.append(f"## {icon} {status_filter}")
        lines.append("")

        for f in filtered:
            lines.append(f"### {f.category} → `{f.name}`")
            lines.append(f"- Spec ref: `{f.spec_reference}`")
            if f.evidence_files:
                lines.append(f"- Found in: {', '.join(f'`{e}`' for e in f.evidence_files)}")
            if f.evidence_lines:
                lines.append(f"- Lines: {', '.join(f.evidence_lines[:5])}")
            else:
                lines.append("- **No code references found**")
            lines.append("")

    (out_dir / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="L9 Spec Coverage Extractor")
    parser.add_argument("--spec", default=None, help="Path to spec YAML (auto-detected if omitted)")
    parser.add_argument("--root", default=".", help="Repo root directory")
    parser.add_argument("--fail-on", default="MISSING", choices=["MISSING", "PARTIAL", "NONE"],
                        help="Exit 1 if any features have this status (or worse)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = root / "artifacts"

    spec_path = Path(args.spec) if args.spec else None
    if spec_path is None:
        candidates = list(root.glob("*spec*.yaml")) + list(root.glob("*spec*.yml"))
        if candidates:
            spec_path = candidates[^0]
        else:
            print("ERROR: No spec YAML found. Use --spec path/to/spec.yaml", file=sys.stderr)
            return 2

    print(f"Loading spec: {spec_path}")
    spec = load_yaml_file(spec_path)

    features: list[SpecFeature] = []
    features += extract_gate_features(spec)
    features += extract_scoring_features(spec)
    features += extract_ontology_features(spec)
    features += extract_v11_additions(spec)
    features += extract_action_features(spec)
    features += extract_gds_features(spec)

    print(f"Extracted {len(features)} features from spec")
    print(f"Scanning codebase at {root} ...")

    scan_codebase(root, features)

    write_checklist(out_dir, features)
    write_coverage_matrix(out_dir, features)

    matrix_data = json.loads((out_dir / "coverage_matrix.json").read_text())
    write_coverage_report(out_dir, features, matrix_data)

    totals = matrix_data["totals"]
    print(f"\nCoverage: {totals['IMPLEMENTED']} implemented, {totals['PARTIAL']} partial, {totals['MISSING']} missing (of {totals['total']})")
    print(f"Report: {out_dir / 'coverage_report.md'}")
    print(f"Matrix: {out_dir / 'coverage_matrix.json'}")
    print(f"Checklist: {out_dir / 'spec_checklist.json'}")

    if args.fail_on == "MISSING" and totals["MISSING"] > 0:
        print(f"\nFAILED: {totals['MISSING']} features are MISSING", file=sys.stderr)
        return 1
    if args.fail_on == "PARTIAL" and (totals["MISSING"] > 0 or totals["PARTIAL"] > 0):
        print(f"\nFAILED: {totals['MISSING']} MISSING + {totals['PARTIAL']} PARTIAL", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```


***

## Update `tools/audit_engine.py` to call spec_extract

Add this to the bottom of `audit_engine.py`'s `main()`, before the return:

```python
    # --- Spec coverage (if spec exists) ---
    import subprocess
    spec_candidates = list(root.glob("*spec*.yaml")) + list(root.glob("*spec*.yml"))
    if spec_candidates:
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "spec_extract.py"),
             "--spec", str(spec_candidates[^0]),
             "--root", str(root),
             "--fail-on", "NONE"],  # don't double-fail; audit_engine owns exit code
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"spec_extract warning: {result.stderr}", file=sys.stderr)
```


***

## Update Makefile

Add these targets to your existing [Makefile](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/blob/main/Makefile):

```make
# L9_TEMPLATE targets
audit: ## Run full architecture audit + spec coverage
	python tools/audit_engine.py
	python tools/spec_extract.py --fail-on NONE
	@echo "Reports in artifacts/"

audit-strict: ## Audit with strict failure (blocks on MISSING spec features)
	python tools/audit_engine.py
	python tools/spec_extract.py --fail-on MISSING

coverage: ## Spec coverage matrix only (no architecture audit)
	python tools/spec_extract.py --fail-on NONE
```


***

## Update `tools/l9_template_manifest.yaml`

Add the new file to your manifest:

```yaml
  - path: "tools/spec_extract.py"
    required: true
    tags: ["L9_TEMPLATE", "audit", "spec-coverage"]
```


***

## How the Two Tools Work Together

```
make audit
  │
  ├─→ tools/audit_engine.py          (architecture compliance)
  │     ├─ Reads: tools/audit_rules.yaml
  │     ├─ Scans: engine/**/*.py
  │     ├─ Checks: banned imports, forbidden dirs, Cypher injection patterns
  │     └─ Writes: artifacts/audit_report.md
  │
  └─→ tools/spec_extract.py          (spec feature coverage)
        ├─ Reads: graph-cognitive-engine-spec-v1.1.0.yaml
        ├─ Extracts: gates, scoring, ontology, v1.1 additions, actions, GDS
        ├─ Scans: engine/**/*.py + domains/**/*.yaml
        └─ Writes: artifacts/coverage_report.md
                   artifacts/coverage_matrix.json
                   artifacts/spec_checklist.json
```

**`audit_engine.py`** answers: *"Does this repo comply with L9 architecture rules?"*[^1][^2]
**`spec_extract.py`** answers: *"Does this repo implement everything the spec requires?"*

Together they produce a complete picture. The architecture audit catches structural violations (wrong imports, missing handlers, injection risks). The spec coverage catches functional gaps (missing gate types, unimplemented scoring dimensions, absent v1.1 nodes).[^2][^1]

***

## CI Integration: `.github/workflows/audit.yml` (updated)

```yaml
name: L9 Audit + Spec Coverage

on:
  pull_request:
  push:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install pyyaml

      - name: Architecture audit
        run: python tools/audit_engine.py

      - name: Spec coverage
        run: python tools/spec_extract.py --fail-on NONE

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: l9-audit-reports
          path: artifacts/
```

Use `--fail-on MISSING` when you're ready to enforce full spec coverage. Use `--fail-on NONE` during active development so you can see the matrix without blocking.

***

## What Cursor Needs to Do

1. Create `tools/spec_extract.py` (paste the code above)
2. Update `tools/l9_template_manifest.yaml` with the new entry
3. Add the three Makefile targets (`audit`, `audit-strict`, `coverage`)
4. Run `make audit` to verify everything works
5. Commit with: `feat: add spec coverage extractor (L9_TEMPLATE)`

After that, run `make coverage` any time you want to see the matrix without the full architecture scan. The coverage report will auto-detect your `graph-cognitive-engine-spec-v1.1.0.yaml` and produce the IMPLEMENTED/PARTIAL/MISSING breakdown for every gate type, scoring dimension, v1.1 addition, GDS algorithm, and action handler.
