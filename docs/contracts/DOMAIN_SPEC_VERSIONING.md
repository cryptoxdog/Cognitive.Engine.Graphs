<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts]
owner: platform
status: active
/L9_META -->

<!-- L9_TEMPLATE: true -->
# L9 Domain Spec Versioning Contract

## Rule
Domain spec YAMLs use semantic versioning with stage suffixes that indicate
how the spec was produced. The version drives schema migration behavior.

## Version Format
```

{major}.{minor}.{patch}-{stage}

```

## Stages (in order)
| Stage | Meaning | Who/What Creates It |
|-------|---------|-------------------|
| `seed` | Auto-generated from CRM field scan | ENRICH schema discovery (Phase 0) |
| `discovered` | Fields added by enrichment passes | ENRICH convergence loop (Phase 1-2) |
| `inferred` | Derived fields added by inference | ENRICH inference engine (Phase 2-4) |
| `proposed` | Gates/scoring auto-proposed | ENRICH convergence (Phase 6) |
| `reviewed` | Human-reviewed and approved | Human approval |
| `production` | Deployed and active | Release process |

## Example Progression
```

0.1.0-seed         → CRM scan: name, city, phone, notes, category
0.2.0-discovered   → Enrichment added: materials_handled, process_types, contamination_tolerance
0.3.0-inferred     → Inference added: material_grade, facility_tier, buyer_class
0.4.0-proposed     → Auto-proposed gates and scoring dimensions
1.0.0-reviewed     → Human approved all proposed changes
1.0.0-production   → Deployed to graph engine
1.1.0-discovered   → New enrichment cycle discovered: moisture_tolerance

```

## Field Metadata on Discovered/Inferred Fields
```yaml
- name: material_grade
  type: enum
  values: [A, B+, B, C, D]
  managed_by: computed                    # "api" | "computed" | "enrichment" | "gds"
  derived_from: [materials_handled, contamination_tolerance, process_types]
  discovery_confidence: 0.85
  auto_proposed: true
```


## BANNED

```python
# ❌ No version-less specs
domain:
  id: plasticos
  # version: ???     ← MISSING — every spec MUST have a version

# ❌ No arbitrary version strings
  version: "latest"     # WRONG
  version: "v2"         # WRONG — use semver
  version: "2026-03-01" # WRONG — use semver with stage
```


## Migration Rules

- `seed` → `discovered`: ADD columns only. Never drop.
- `discovered` → `inferred`: ADD computed columns. Set `managed_by: computed`.
- Any stage → `production`: Requires human review OR auto-approval (Autonomous tier).
- Major version bump: Breaking ontology change (node/edge type renamed or removed).
- Minor version bump: New fields, gates, or scoring dimensions added.
- Patch version bump: Threshold/parameter tuning only.

```
