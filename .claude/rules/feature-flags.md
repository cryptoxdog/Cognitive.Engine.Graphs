---
paths:
  - "engine/config/settings.py"
  - "engine/handlers.py"
  - "engine/boot.py"
---
# Feature Flags (engine/config/settings.py)

All in Settings class, controllable via env vars. Contract 21: every behavioral change must be flag-gated.

## Core Engine
| Flag | Default | Purpose |
|------|---------|---------|
| gds_enabled | True | GDS scheduler toggle |
| kge_enabled | False | KGE embedding scoring dimension |
| pareto_enabled | True | Multi-objective Pareto-optimal scoring |
| pareto_weight_discovery_enabled | False | Learned weight trade-offs from outcomes |

## Wave 1 — Invariant Hardening
| Flag | Default | Purpose |
|------|---------|---------|
| domain_strict_validation | True | Cross-reference validation at domain load |
| score_clamp_enabled | True | Clamp dimension scores to [0, 1] |
| strict_null_gates | True | Reject gates with null-resolved parameters |
| max_hop_hard_cap | 10 | Maximum traversal hops |
| param_strict_mode | True | Raise on derived parameter resolution failures |

## Wave 2 — Scoring Refinement
| Flag | Default | Purpose |
|------|---------|---------|
| feedback_enabled | False | Outcome feedback loop |
| confidence_check_enabled | True | Ensemble confidence bounds |
| monoculture_threshold | 0.70 | Single-dimension dominance cap |
| ensemble_max_divergence | 0.30 | GDS/KGE score divergence cap |
| score_normalize | False | Post-query min-max normalization |

## Entity Resolution
| Flag | Default | Purpose |
|------|---------|---------|
| resolution_min_confidence | 0.6 | Minimum similarity for dedup merge |
| resolution_density_tolerance | 0.05 | Density tolerance |
| resolution_mfi_tolerance | 5.0 | MFI tolerance |

## Scoring Weights (Contract 22: sum ≤ 1.0)
| Weight | Default | Enforced by |
|--------|---------|-------------|
| w_structural | 0.30 | boot.py _assert_default_weight_sum() |
| w_geo | 0.25 | boot.py _assert_default_weight_sum() |
| w_reinforcement | 0.20 | boot.py _assert_default_weight_sum() |
| w_freshness | 0.10 | boot.py _assert_default_weight_sum() |
| **Sum** | **0.85** | Must be ≤ 1.0 |
