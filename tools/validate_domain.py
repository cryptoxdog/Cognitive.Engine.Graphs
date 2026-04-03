#!/usr/bin/env python3
"""
Domain-spec validation CLI tool (W5-04).

Validates a domain spec YAML against Wave 1 invariants:
  - W1-01: Cross-reference validation (ontology → gates → scoring)
  - W1-03: Gate compilation checks
  - W1-04: Traversal pattern safety
  - W3-02: Capability validation (prohibited factors)

Usage:
    python tools/validate_domain.py path/to/spec.yaml
    python tools/validate_domain.py path/to/spec.yaml --strict
    python tools/validate_domain.py path/to/spec.yaml --json

Exit codes:
    0 — all checks passed
    1 — critical failures
    2 — warnings only (no failures)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from engine.config.schema import DomainSpec


def _check_cross_references(spec: DomainSpec) -> list[dict]:
    """W1-01: Validate cross-references between spec sections."""
    results = []
    node_labels = {n.label for n in spec.ontology.nodes}
    edge_types = {e.type for e in spec.ontology.edges}

    # Check edge from/to references
    for edge in spec.ontology.edges:
        if edge.from_ not in node_labels:
            results.append(
                {
                    "check": "W1-01-edge-source",
                    "status": "FAIL",
                    "message": f"Edge '{edge.type}' source '{edge.from_}' not in ontology nodes",
                    "path": f"ontology.edges[type={edge.type}].from",
                }
            )
        if edge.to not in node_labels:
            results.append(
                {
                    "check": "W1-01-edge-target",
                    "status": "FAIL",
                    "message": f"Edge '{edge.type}' target '{edge.to}' not in ontology nodes",
                    "path": f"ontology.edges[type={edge.type}].to",
                }
            )

    # Check match entity references
    for candidate in spec.matchentities.candidate:
        if candidate.label not in node_labels:
            results.append(
                {
                    "check": "W1-01-candidate-label",
                    "status": "FAIL",
                    "message": f"Candidate label '{candidate.label}' not in ontology",
                    "path": f"matchentities.candidate[label={candidate.label}]",
                }
            )

    # Check gate edge references
    for gate in spec.gates:
        if gate.edgetype and gate.edgetype not in edge_types:
            results.append(
                {
                    "check": "W1-01-gate-edge",
                    "status": "FAIL",
                    "message": f"Gate '{gate.name}' references unknown edge type '{gate.edgetype}'",
                    "path": f"gates[name={gate.name}].edgetype",
                }
            )

    # Check scoring weight sum
    if spec.scoring and spec.scoring.dimensions:
        weight_sum = sum(d.defaultweight for d in spec.scoring.dimensions)
        if weight_sum > 1.0 + 1e-9:
            results.append(
                {
                    "check": "W1-01-weight-sum",
                    "status": "FAIL",
                    "message": f"Scoring default weights sum to {weight_sum:.4f}, exceeding 1.0",
                    "path": "scoring.dimensions[*].defaultweight",
                }
            )

    if not results:
        results.append({"check": "W1-01-cross-ref", "status": "PASS", "message": "All cross-references valid"})

    return results


def _check_gate_compilation(spec: DomainSpec) -> list[dict]:
    """W1-03: Validate gate compilation."""
    results = []

    try:
        from engine.gates.compiler import GateCompiler

        compiler = GateCompiler(spec)
        directions = spec.queryschema.matchdirections
        for direction in directions:
            clause = compiler.compile_all_gates(direction)
            if clause:
                results.append(
                    {
                        "check": "W1-03-gate-compile",
                        "status": "PASS",
                        "message": f"Gates compile for direction '{direction}' ({len(clause)} chars)",
                    }
                )
    except Exception as exc:
        results.append(
            {
                "check": "W1-03-gate-compile",
                "status": "FAIL",
                "message": f"Gate compilation failed: {exc}",
            }
        )

    if not results:
        results.append({"check": "W1-03-gate-compile", "status": "PASS", "message": "No gates to compile"})

    return results


def _check_traversal(spec: DomainSpec) -> list[dict]:
    """W1-04: Validate traversal patterns."""
    results = []

    if spec.traversal is None:
        results.append({"check": "W1-04-traversal", "status": "PASS", "message": "No traversal defined"})
        return results

    try:
        from engine.traversal.assembler import TraversalAssembler

        assembler = TraversalAssembler(spec)
        for direction in spec.queryschema.matchdirections:
            warnings = assembler.validate_traversal(direction)
            if warnings:
                for w in warnings:
                    results.append({"check": "W1-04-traversal", "status": "WARN", "message": w})
            else:
                results.append(
                    {
                        "check": "W1-04-traversal",
                        "status": "PASS",
                        "message": f"Traversal valid for direction '{direction}'",
                    }
                )
    except Exception as exc:
        results.append(
            {
                "check": "W1-04-traversal",
                "status": "FAIL",
                "message": f"Traversal validation failed: {exc}",
            }
        )

    return results


def _check_compliance(spec: DomainSpec) -> list[dict]:
    """W3-02: Validate prohibited factors."""
    results = []

    try:
        from engine.compliance.prohibited_factors import ProhibitedFactorValidator

        validator = ProhibitedFactorValidator(spec)
        for gate in spec.gates:
            validator.validate_gate(gate)
        results.append(
            {
                "check": "W3-02-prohibited-factors",
                "status": "PASS",
                "message": "No prohibited factors in gates",
            }
        )
    except (ValueError, Exception) as exc:
        results.append(
            {
                "check": "W3-02-prohibited-factors",
                "status": "FAIL",
                "message": f"Prohibited factor violation: {exc}",
            }
        )

    return results


def validate_spec(spec_path: Path, strict: bool = False) -> tuple[list[dict], int]:
    """Run all validation checks on a domain spec.

    Returns:
        Tuple of (results, exit_code).
    """
    # Load and parse YAML
    raw = spec_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    # Validate with Pydantic
    try:
        spec = DomainSpec(**data)
    except Exception as exc:
        return [{"check": "schema-validation", "status": "FAIL", "message": f"Schema validation failed: {exc}"}], 1

    # Run all checks
    results: list[dict] = []
    results.extend(_check_cross_references(spec))
    results.extend(_check_gate_compilation(spec))
    results.extend(_check_traversal(spec))
    results.extend(_check_compliance(spec))

    # Determine exit code
    has_fail = any(r["status"] == "FAIL" for r in results)
    has_warn = any(r["status"] == "WARN" for r in results)

    if has_fail:
        exit_code = 1
    elif has_warn and strict:
        exit_code = 1  # Strict mode escalates warnings to failures
    elif has_warn:
        exit_code = 2
    else:
        exit_code = 0

    return results, exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a CEG domain spec YAML")
    parser.add_argument("spec_path", type=Path, help="Path to domain spec YAML file")
    parser.add_argument("--strict", action="store_true", help="Escalate warnings to failures")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON for CI")
    args = parser.parse_args()

    if not args.spec_path.exists():
        print(f"Error: {args.spec_path} not found", file=sys.stderr)
        sys.exit(1)

    results, exit_code = validate_spec(args.spec_path, strict=args.strict)

    if args.json_output:
        output = {"results": results, "exit_code": exit_code, "spec_path": str(args.spec_path)}
        print(json.dumps(output, indent=2))
    else:
        status_emoji = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}
        for r in results:
            status = status_emoji.get(r["status"], r["status"])
            msg = r["message"]
            path = r.get("path", "")
            path_str = f" ({path})" if path else ""
            print(f"  {status} {r['check']}: {msg}{path_str}")

        pass_count = sum(1 for r in results if r["status"] == "PASS")
        fail_count = sum(1 for r in results if r["status"] == "FAIL")
        warn_count = sum(1 for r in results if r["status"] == "WARN")
        print(f"\nSummary: {pass_count} passed, {fail_count} failed, {warn_count} warnings")

        if exit_code == 0:
            print("Result: ALL CHECKS PASSED")
        elif exit_code == 2:
            print("Result: WARNINGS (non-blocking)")
        else:
            print("Result: FAILURES DETECTED")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
