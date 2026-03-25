---
name: domain-spec
description: Create or validate a domain spec YAML file for the CEG engine
---

# Domain Spec Authoring

Create or modify a domain spec YAML for the graph cognitive engine.

## Steps

1. **Read the target vertical requirements** from the user
2. **Load schema reference**: Read `engine/config/schema.py` to understand all available spec types
3. **Load an example**: Read `domains/` for an existing spec to follow the pattern
4. **Author the spec** with these required sections:
   - `ontology` — node types, edge types, property declarations
   - `match_entities` — source and target entity definitions
   - `query_schema` — input parameter definitions
   - `traversal` — path patterns with bounded hops (max 10)
   - `gates` — filter definitions using the 10 gate types
   - `scoring` — ranking dimensions using the 13 computation types
   - `sync` — entity ingestion endpoints
5. **Validate**: Run `python -m tools.validate_domain path/to/spec.yaml --strict`
6. **Cross-reference check**: Ensure all edge source/target types reference declared node types, all gate fields reference declared properties, weight overrides sum ≤ 1.0

## Gate Types (10)
range, threshold, boolean, composite, enummap, exclusion, selfrange, freshness, temporalrange, traversal

## Scoring Computations (13)
geodecay, lognormalized, communitymatch, inverselinear, candidateproperty, weightedrate, pricealignment, temporalproximity, customcypher, traversalalias, kge, variantdiscovery, ensembleconfidence

## Validation Checklist
- [ ] All node/edge types in ontology are referenced correctly
- [ ] Gate field references match declared node properties
- [ ] Scoring weight overrides sum ≤ 1.0
- [ ] Traversal hops bounded (max 10)
- [ ] Compliance section declares PII fields if applicable
- [ ] `python -m tools.validate_domain` passes with `--strict`
