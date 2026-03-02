# L9 Spec Coverage Report

- Generated: 2026-03-02T01:38:06.564214+00:00
- Template tag: `L9_TEMPLATE`

## Summary

| Category | Implemented | Partial | Missing | Total |
|----------|-------------|---------|---------|-------|
| gates | 10 | 0 | 0 | 10 |
| scoring | 7 | 0 | 0 | 7 |
| v1.1_node | 2 | 0 | 0 | 2 |
| v1.1_edge | 2 | 0 | 0 | 2 |
| v1.1_action | 0 | 2 | 0 | 2 |
| v1.1_scoring | 1 | 1 | 0 | 2 |
| action_handler | 0 | 4 | 2 | 6 |
| gds_algorithm | 5 | 0 | 0 | 5 |
| **TOTAL** | **27** | **7** | **2** | **36** |

## ❌ MISSING

### action_handler → `enrich`
- Spec ref: `chassis action: enrich`
- **No code references found**

### action_handler → `healthcheck`
- Spec ref: `chassis action: healthcheck`
- **No code references found**

## ⚠️ PARTIAL

### v1.1_action → `outcomes`
- Spec ref: `v1.1 addition: outcomes action/endpoint`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:219, engine/handlers.py:302

### v1.1_action → `resolve`
- Spec ref: `v1.1 addition: resolve action/endpoint`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:22, engine/handlers.py:75, engine/handlers.py:76, engine/handlers.py:77, engine/handlers.py:117

### v1.1_scoring → `outcome_weighted`
- Spec ref: `v1.1 addition: outcome_weighted scoring type`
- Found in: `tools/spec_extract.py`
- Lines: tools/spec_extract.py:161, tools/spec_extract.py:209

### action_handler → `match`
- Spec ref: `chassis action: match`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:39, engine/handlers.py:299

### action_handler → `sync`
- Spec ref: `chassis action: sync`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:132, engine/handlers.py:300

### action_handler → `admin`
- Spec ref: `chassis action: admin`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:182, engine/handlers.py:301

### action_handler → `query`
- Spec ref: `chassis action: query`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:60, engine/handlers.py:117

## ✅ IMPLEMENTED

### gates → `range`
- Spec ref: `gates (detected in spec text)`
- Found in: `UniversalDevelopmentPack.yaml`, `docs/PlasticOS Graph Cognitive Engine.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/performance/test_query_latency.py`, `tests/performance/test_sync_throughput.py`, `tests/unit/test_gates_all_types.py`, `tools/audit_engine.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:115, tools/spec_extract.py:116, tools/spec_extract.py:117, tools/audit_engine.py:66, tests/unit/test_gates_all_types.py:17

### gates → `threshold`
- Spec ref: `gates (detected in spec text)`
- Found in: `.github/pr_review_config.yaml`, `UniversalDevelopmentPack.yaml`, `docs/PlasticOS Graph Cognitive Engine.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/config/settings.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `setup-new-workspace.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:115, tests/unit/test_gates_all_types.py:18, tests/unit/test_gates_all_types.py:34, tests/unit/test_gates_all_types.py:78, tests/unit/test_gates_all_types.py:79

### gates → `boolean`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/PlasticOS Graph Cognitive Engine.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:115, tests/unit/test_gates_all_types.py:16, tests/unit/test_gates_all_types.py:94, tests/unit/test_gates_all_types.py:95, tests/unit/test_gates_all_types.py:98

### gates → `composite`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:115, tests/unit/test_gates_all_types.py:25, engine/gates/compiler.py:34, engine/gates/compiler.py:138, engine/gates/compiler.py:197

### gates → `enum_map`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:115, tests/unit/test_gates_all_types.py:19, tests/unit/test_gates_all_types.py:126, tests/unit/test_gates_all_types.py:127, tests/unit/test_gates_all_types.py:130

### gates → `exclusion`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/conftest.py`, `tests/integration/test_multi_tenant.py`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:116, tests/conftest.py:132, tests/conftest.py:238, tests/unit/test_gates_all_types.py:20, tests/unit/test_gates_all_types.py:141

### gates → `self_range`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:116, tests/unit/test_gates_all_types.py:21, tests/unit/test_gates_all_types.py:156, tests/unit/test_gates_all_types.py:157, tests/unit/test_gates_all_types.py:160

### gates → `freshness`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/research_agent_domain_spec.yaml`, `engine/config/schema.py`, `engine/config/settings.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:116, tests/unit/test_gates_all_types.py:22, tests/unit/test_gates_all_types.py:173, tests/unit/test_gates_all_types.py:174, tests/unit/test_gates_all_types.py:177

### gates → `temporal_range`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:116, tests/unit/test_gates_all_types.py:23, tests/unit/test_gates_all_types.py:190, tests/unit/test_gates_all_types.py:191, tests/unit/test_gates_all_types.py:194

### gates → `traversal`
- Spec ref: `gates (detected in spec text)`
- Found in: `.github/pr_review_config.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/__init__.py`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `engine/handlers.py`, `engine/traversal/__init__.py`, `engine/traversal/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/conftest.py`, `tests/integration/test_null_semantics.py`, `tests/performance/test_query_latency.py`, `tests/unit/test_gates_all_types.py`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:117, tests/conftest.py:140, engine/handlers.py:21, engine/handlers.py:22, engine/handlers.py:41

### scoring → `geo_decay`
- Spec ref: `scoring (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `engine/config/schema.py`, `engine/config/settings.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_scoring.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:159, tests/unit/test_scoring.py:46, tests/unit/test_scoring.py:47, tests/unit/test_scoring.py:51, engine/config/settings.py:60

### scoring → `log_normalized`
- Spec ref: `scoring (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:159, engine/config/schema.py:86, engine/scoring/assembler.py:63, engine/scoring/assembler.py:64, engine/scoring/assembler.py:95

### scoring → `community_match`
- Spec ref: `scoring (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:159, engine/config/schema.py:87, engine/config/schema.py:297, engine/scoring/assembler.py:65, engine/scoring/assembler.py:66

### scoring → `inverse_linear`
- Spec ref: `scoring (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_scoring.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:160, tests/unit/test_scoring.py:65, tests/unit/test_scoring.py:71, engine/config/schema.py:88, engine/scoring/assembler.py:67

### scoring → `candidate_property`
- Spec ref: `scoring (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_scoring.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:160, tests/unit/test_scoring.py:28, tests/unit/test_scoring.py:93, tests/unit/test_scoring.py:100, tests/unit/test_scoring.py:123

### scoring → `custom_cypher`
- Spec ref: `scoring (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:160, engine/config/schema.py:93, engine/config/schema.py:291, engine/scoring/assembler.py:71, graph-cognitive-engine-spec-v1.1.0.yaml:245

### scoring → `temporal_decay`
- Spec ref: `scoring (detected in spec text)`
- Found in: `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:161, tools/spec_extract.py:209, graph-cognitive-engine-spec-v1.1.0.yaml:1958

### v1.1_node → `TransactionOutcome`
- Spec ref: `v1.1 addition: TransactionOutcome node`
- Found in: `docs/plasticos_domain_spec_v0.4.yaml`, `engine/handlers.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:206, engine/handlers.py:221, engine/handlers.py:238, docs/plasticos_domain_spec_v0.4.yaml:523, docs/plasticos_domain_spec_v0.4.yaml:1028

### v1.1_node → `SignalEvent`
- Spec ref: `v1.1 addition: SignalEvent node`
- Found in: `docs/plasticos_domain_spec_v0.4.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:206, docs/plasticos_domain_spec_v0.4.yaml:546, docs/plasticos_domain_spec_v0.4.yaml:1039, docs/plasticos_domain_spec_v0.4.yaml:1634

### v1.1_edge → `RESULTED_IN`
- Spec ref: `v1.1 addition: RESULTED_IN edge`
- Found in: `docs/plasticos_domain_spec_v0.4.yaml`, `engine/handlers.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:207, engine/handlers.py:221, engine/handlers.py:250, docs/plasticos_domain_spec_v0.4.yaml:1026, docs/plasticos_domain_spec_v0.4.yaml:1635

### v1.1_edge → `RESOLVED_FROM`
- Spec ref: `v1.1 addition: RESOLVED_FROM edge`
- Found in: `docs/plasticos_domain_spec_v0.4.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:207, docs/plasticos_domain_spec_v0.4.yaml:1037, docs/plasticos_domain_spec_v0.4.yaml:1635

### v1.1_scoring → `temporal_decay`
- Spec ref: `v1.1 addition: temporal_decay scoring type`
- Found in: `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:161, tools/spec_extract.py:209, graph-cognitive-engine-spec-v1.1.0.yaml:1958

### gds_algorithm → `louvain`
- Spec ref: `gds (detected in spec text)`
- Found in: `.coderabbit.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:266, engine/gds/scheduler.py:4, engine/gds/scheduler.py:30, engine/gds/scheduler.py:75, engine/gds/scheduler.py:76

### gds_algorithm → `cooccurrence`
- Spec ref: `gds (detected in spec text)`
- Found in: `.coderabbit.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:266, engine/gds/scheduler.py:31, engine/gds/scheduler.py:77, engine/gds/scheduler.py:78, engine/gds/scheduler.py:143

### gds_algorithm → `reinforcement`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/config/settings.py`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:266, engine/config/settings.py:58, engine/gds/scheduler.py:4, engine/gds/scheduler.py:32, engine/gds/scheduler.py:79

### gds_algorithm → `temporal_recency`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:266, engine/gds/scheduler.py:82, engine/gds/scheduler.py:262, graph-cognitive-engine-spec-v1.1.0.yaml:575, graph-cognitive-engine-spec-v1.1.0.yaml:612

### gds_algorithm → `similarity`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/config/schema.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:267, engine/config/schema.py:427, graph-cognitive-engine-spec-v1.1.0.yaml:4, graph-cognitive-engine-spec-v1.1.0.yaml:446, graph-cognitive-engine-spec-v1.1.0.yaml:448
