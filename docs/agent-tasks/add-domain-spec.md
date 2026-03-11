# Task: Add a New Domain Spec

```
task: Add domain "<domain_id>"
tier: 2
contracts_to_read:
  - docs/contracts/DOMAIN_SPEC_VERSIONING.md
  - docs/contracts/FIELD_NAMES.md
  - docs/contracts/PYDANTIC_YAML_MAPPING.md
```

## Preconditions
- `make test` passes
- Domain ID is unique (not in `domains/` yet)
- Ontology (nodes, edges) is defined

## Steps
1. Create `domains/<domain_id>/spec.yaml`
   - All YAML keys snake_case
   - Version: `0.1.0-seed`
   - Required sections: domain, ontology, traversal, gates, scoring, sync, compliance
2. Validate: `python -c "from engine.config.loader import DomainPackLoader; DomainPackLoader(...).load_domain('<domain_id>')"`
3. Add test in `tests/unit/test_config_loader.py`
   - Spec loads without error
   - All required sections present
   - Version format valid
4. Run `make agent-check`

## Acceptance Criteria
- [ ] spec.yaml exists at `domains/<domain_id>/spec.yaml`
- [ ] All YAML keys snake_case (no camelCase, no flatcase)
- [ ] Config loader validates without error
- [ ] Version follows DOMAIN_SPEC_VERSIONING.md format
- [ ] `make agent-check` exits 0
