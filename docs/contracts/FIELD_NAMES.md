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
# L9 Field Name Contract

## Rule
ALL Pydantic model fields use **snake_case**. ALL YAML spec keys use **snake_case**.
There are NO aliases, NO camelCase, NO flatcase fields anywhere in the engine.

When accessing a Pydantic model attribute in Python, the attribute name is IDENTICAL
to the YAML key name. No transformation occurs.

## Canonical Field Names (DomainSpec)

These are the EXACT attribute names. Use these and ONLY these.

### DomainSpec (top-level)
```python
domain_spec.domain                  # DomainMeta
domain_spec.domain.id               # str — also the Neo4j database name
domain_spec.domain.name             # str
domain_spec.domain.version          # str
domain_spec.ontology                # OntologySpec
domain_spec.ontology.nodes          # list[NodeSpec]
domain_spec.ontology.edges          # list[EdgeSpec]
domain_spec.match_entities          # MatchEntitiesSpec
domain_spec.match_entities.candidate  # list[CandidateEntity]
domain_spec.match_entities.query    # list[QueryEntity]
domain_spec.traversal               # TraversalSpec
domain_spec.traversal.steps         # list[TraversalStep]
domain_spec.gates                   # list[GateSpec]
domain_spec.scoring                 # ScoringSpec
domain_spec.scoring.dimensions      # list[ScoringDimension]
domain_spec.scoring.aggregation     # str — "additive" or "multiplicative"
domain_spec.sync                    # SyncSpec
domain_spec.sync.endpoints          # list[SyncEndpoint]
domain_spec.gds_jobs                # list[GDSJobSpec]
domain_spec.compliance              # ComplianceSpec
domain_spec.compliance.prohibited_factors  # list[str]
```


### GateSpec

```python
gate.type                           # GateType enum value
gate.field                          # str — property name on candidate node
gate.query_param                    # str — key in query dict
gate.match_direction                # str — which direction this gate applies to
gate.null_behavior                  # str — "pass" or "fail"
gate.params                         # dict[str, Any] — gate-type-specific parameters
```


### ScoringDimension

```python
dim.type                            # ScoringType enum value
dim.weight                          # float
dim.field                           # str — property name on candidate node
dim.query_param                     # str — key in query dict
dim.params                          # dict[str, Any] — scoring-type-specific parameters
```


### SyncEndpoint

```python
endpoint.path                       # str — e.g., "facilities"
endpoint.target_node                # str — Neo4j label (MUST sanitize before Cypher)
endpoint.id_property                # str — unique key property
endpoint.strategy                   # str — "merge" or "match_set"
endpoint.taxonomy_edges             # list[TaxonomyEdge]
endpoint.children                   # list[ChildSync]
```


### TraversalStep

```python
step.alias                          # str — Cypher variable alias
step.pattern                        # str — MATCH or OPTIONAL MATCH pattern
step.match_directions               # list[str] — which directions include this step
```


## WRONG (will crash)

```python
# ❌ These DO NOT EXIST — agents must never generate these
domain_spec.matchentities           # WRONG: missing underscore
domain_spec.match_entities.candidates  # WRONG: not plural 's'... wait yes it is
domain_spec.nodelabels              # WRONG: not a field
domain_spec.matchdirections         # WRONG: not a top-level field
gate.candidateprop                  # WRONG: field is called 'field'
gate.null_semantics                 # WRONG: field is called 'null_behavior'
dim.computation_type                # WRONG: field is called 'type'
endpoint.targetnode                 # WRONG: missing underscore
endpoint.idproperty                 # WRONG: missing underscore
```


## Enforcement

- Ruff TID251 cannot catch this (it's semantic, not import-based)
- `tools/audit_engine.py` checks for known wrong patterns
- Integration tests must instantiate DomainSpec from real YAML and access all fields

```
