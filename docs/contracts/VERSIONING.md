# Contract Versioning Policy

> Semantic versioning for all CEG contract files. All contracts start at `1.0.0`.

## Policy

- **MAJOR**: Breaking change — field removed, type changed, required field added to existing schema
- **MINOR**: Backward-compatible addition — new optional field, new endpoint, new action
- **PATCH**: Non-breaking correction — description clarification, example update, typo fix

## Contract File Header

Every contract file MUST begin with:

```yaml
# ═══════════════════════════════════════════════════════════════
# Contract: {name}
# Source:   {file_path}:{line_number}
# Version:  1.0.0
# Updated:  {ISO 8601 date}
# ═══════════════════════════════════════════════════════════════
```

## Breaking Change Protocol

1. Announce in PR description with label `contract:breaking`
2. Bump MAJOR version in contract file header
3. Update all `$ref` consumers
4. Add migration guide under `x-migration-notes`
5. Tag commit with `contract-v{X}.{Y}.{Z}`

## Current Versions

| File | Version | Last Updated |
|------|---------|--------------|
| `api/openapi.yaml` | 1.0.0 | 2026-04-05 |
| `agents/tool-schemas/*.schema.json` | 1.0.0 | 2026-04-05 |
| `data/models/*.schema.json` | 1.0.0 | 2026-04-05 |
| `events/asyncapi.yaml` | 1.0.0 | 2026-04-05 |
| `config/env-contract.yaml` | 1.0.0 | 2026-04-05 |
| `dependencies/*.yaml` | 1.0.0 | 2026-04-05 |
