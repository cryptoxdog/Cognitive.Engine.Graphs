<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [config]
tags: [feature-flags, behavioral-gates, settings]
owner: platform
status: active
/L9_META -->

# FEATURE_FLAGS.md — CEG Feature Flag Registry

**Purpose**: Complete inventory of all behavioral feature flags in engine/config/settings.py

**Source**: .claude/rules/feature-flags.md (SHA: f074961)

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Contract 21: Feature Flag Discipline

**Rule**: Every behavioral change MUST be gated by a boolean flag in `engine/config/settings.py`.

**Pattern**:
```python
# In settings.py
class Settings(BaseSettings):
    my_new_feature_enabled: bool = Field(default=False, description="...")

# In code
from engine.config.settings import settings

if settings.my_new_feature_enabled:
    # new behavior
else:
    # existing behavior (safe fallback)
```

**Agent Guidance**: Always gate behavioral changes with feature flags. True = safety/production-ready. False = experimental.

---

## Core Engine Flags

| Flag | Default | Purpose | Subsystem |
|------|---------|---------|-----------|
| `gds_enabled` | True | GDS scheduler toggle | engine/gds/ |
| `kge_enabled` | False | KGE embedding scoring dimension | engine/kge/ |
| `pareto_enabled` | True | Multi-objective Pareto-optimal scoring | engine/scoring/ |
| `pareto_weight_discovery_enabled` | False | Learned weight trade-offs from outcomes | engine/feedback/ |

---

## Wave 1 — Invariant Hardening

| Flag | Default | Purpose | Enforcement |
|------|---------|---------|-------------|
| `domain_strict_validation` | True | Cross-reference validation at domain load | engine/config/loader.py |
| `score_clamp_enabled` | True | Clamp dimension scores to [0, 1] | engine/scoring/ |
| `strict_null_gates` | True | Reject gates with null-resolved parameters | engine/gates/ |
| `max_hop_hard_cap` | 10 | Maximum traversal hops | engine/traversal/ |
| `param_strict_mode` | True | Raise on derived parameter resolution failures | engine/config/ |

---

## Wave 2 — Scoring Refinement

| Flag | Default | Purpose | Subsystem |
|------|---------|---------|-----------|
| `feedback_enabled` | False | Outcome feedback loop | engine/feedback/ |
| `confidence_check_enabled` | True | Ensemble confidence bounds | engine/scoring/ |
| `monoculture_threshold` | 0.70 | Single-dimension dominance cap | engine/scoring/ |
| `ensemble_max_divergence` | 0.30 | GDS/KGE score divergence cap | engine/scoring/ |
| `score_normalize` | False | Post-query min-max normalization | engine/scoring/ |

---

## Entity Resolution

| Flag | Default | Purpose | Subsystem |
|------|---------|---------|-----------|
| `resolution_min_confidence` | 0.6 | Minimum similarity for dedup merge | engine/resolution/ |
| `resolution_density_tolerance` | 0.05 | Density tolerance | engine/resolution/ |
| `resolution_mfi_tolerance` | 5.0 | MFI tolerance | engine/resolution/ |

---

## Scoring Weights (Contract 22: Sum ≤ 1.0)

**Enforced by**: `engine/boot.py::_assert_default_weight_sum()`

| Weight | Default | Purpose |
|--------|---------|---------|
| `w_structural` | 0.30 | Graph structure scoring |
| `w_geo` | 0.25 | Geospatial proximity scoring |
| `w_reinforcement` | 0.20 | Feedback loop reinforcement |
| `w_freshness` | 0.10 | Temporal recency scoring |
| **Sum** | **0.85** | Must be ≤ 1.0 |

**Agent Rule**: When adding a new scoring weight, reduce existing weights proportionally to maintain sum ≤ 1.0. The startup assertion will fail otherwise.

---

## Flag Usage in Code

### Adding a New Flag

```python
# 1. Add to engine/config/settings.py
class Settings(BaseSettings):
    my_feature_enabled: bool = Field(
        default=False,  # always False for new experimental features
        description="Enable experimental feature X",
    )

# 2. Use in code
from engine.config.settings import settings

async def handle_match(tenant: str, payload: dict) -> dict:
    if settings.my_feature_enabled:
        result = await new_experimental_logic(tenant, payload)
    else:
        result = await existing_stable_logic(tenant, payload)
    return result

# 3. Test both paths
def test_match_with_feature_enabled(monkeypatch):
    monkeypatch.setattr("engine.config.settings.settings.my_feature_enabled", True)
    # test new path

def test_match_with_feature_disabled(monkeypatch):
    monkeypatch.setattr("engine.config.settings.settings.my_feature_enabled", False)
    # test existing path
```

### Environment Variable Override

All flags are controllable via environment variables:

```bash
# In .env or runtime environment
MY_FEATURE_ENABLED=true

# Pydantic Settings automatically maps:
# MY_FEATURE_ENABLED env var → Settings.my_feature_enabled field
```

---

## Flag Lifecycle

1. **Experimental** (default=False): New feature under development, not production-ready
2. **Beta** (default=False, documented in CHANGELOG): Feature ready for opt-in testing
3. **GA** (default=True): Feature promoted to general availability
4. **Deprecated** (default=True, logged warning): Feature scheduled for removal
5. **Removed**: Flag and code deleted

**Agent Rule**: Never remove a flag in the same PR that adds it. Flags must go through at least one release cycle before removal.

---

## Flag Audit

Run this command to verify all flags in settings.py are documented here:

```bash
# Extract flag names from settings.py
grep -E "^\s+[a-z_]+: bool = Field" engine/config/settings.py | awk '{print $1}' | sort

# Compare to this document
# Any mismatch = documentation drift
```

---

## Related Contracts

- **C-021**: Feature Flag Discipline — every behavioral change gated by flag
- **C-022**: Scoring Weight Ceiling — default weights sum ≤ 1.0, enforced at startup
- **C-024**: Resilience Patterns — no module-level globals (flags via Settings singleton)

---

## References

- Source: `.claude/rules/feature-flags.md`
- Settings implementation: `engine/config/settings.py`
- Startup enforcement: `engine/boot.py`
- Weight sum assertion: `engine/boot.py::_assert_default_weight_sum()`
