"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [intake]
tags: [intake, crm, pipeline]
owner: engine-team
status: active
--- /L9_META ---

engine/intake — CRM-to-YAML pipeline + impact reporter.

Maps customer CRM exports against the graph spec ontology,
discovers vertical-standard fields, compiles a domain_spec.yaml
with three-source field hierarchy, and scores against gates + edges.
"""

from engine.intake.intake_schema import (
    FieldMapping,
    FieldOrigin,
    ImpactAnalysis,
    IntakeResult,
    ScanResult,
)

__all__ = [
    "FieldMapping",
    "FieldOrigin",
    "ImpactAnalysis",
    "IntakeResult",
    "ScanResult",
]
