# L9 Spec Coverage Report

- Generated: 2026-03-02T03:59:08.120687+00:00
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
| action_handler | 0 | 6 | 0 | 6 |
| gds_algorithm | 5 | 0 | 0 | 5 |
| **TOTAL** | **27** | **9** | **0** | **36** |

## ⚠️ PARTIAL

### v1.1_action → `outcomes`
- Spec ref: `v1.1 addition: outcomes action/endpoint`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:274, engine/handlers.py:463

### v1.1_action → `resolve`
- Spec ref: `v1.1 addition: resolve action/endpoint`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:325, engine/handlers.py:464

### v1.1_scoring → `outcome_weighted`
- Spec ref: `v1.1 addition: outcome_weighted scoring type`
- Found in: `tools/spec_extract.py`
- Lines: tools/spec_extract.py:171, tools/spec_extract.py:219

### action_handler → `match`
- Spec ref: `chassis action: match`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:73, engine/handlers.py:460

### action_handler → `sync`
- Spec ref: `chassis action: sync`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:157, engine/handlers.py:461

### action_handler → `admin`
- Spec ref: `chassis action: admin`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:203, engine/handlers.py:462

### action_handler → `query`
- Spec ref: `chassis action: query`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:78, engine/handlers.py:133

### action_handler → `enrich`
- Spec ref: `chassis action: enrich`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:395, engine/handlers.py:467

### action_handler → `healthcheck`
- Spec ref: `chassis action: healthcheck`
- Found in: `engine/handlers.py`
- Lines: engine/handlers.py:390, engine/handlers.py:466

## ✅ IMPLEMENTED

### gates → `range`
- Spec ref: `gates (detected in spec text)`
- Found in: `UniversalDevelopmentPack.yaml`, `current work/3D KG Embedding - HyperGraphs/beam_search.py`, `current work/3D KG Embedding - HyperGraphs/ensemble.py`, `current work/3D KG Embedding - HyperGraphs/kge_orchestrator_integration.py`, `current work/3D KG Embedding - HyperGraphs/test_compound_e3d.py`, `docs/PlasticOS Graph Cognitive Engine.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/performance/test_query_latency.py`, `tests/performance/test_sync_throughput.py`, `tests/unit/test_gates_all_types.py`, `tools/audit_engine.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:125, tools/spec_extract.py:126, tools/spec_extract.py:127, tools/audit_engine.py:75, tests/unit/test_gates_all_types.py:17

### gates → `threshold`
- Spec ref: `gates (detected in spec text)`
- Found in: `.github/pr_review_config.yaml`, `UniversalDevelopmentPack.yaml`, `current work/3D KG Embedding - HyperGraphs/beam_search.py`, `current work/3D KG Embedding - HyperGraphs/test_compound_e3d.py`, `docs/PlasticOS Graph Cognitive Engine.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/config/settings.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `setup-new-workspace.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:125, tests/unit/test_gates_all_types.py:18, tests/unit/test_gates_all_types.py:34, tests/unit/test_gates_all_types.py:78, tests/unit/test_gates_all_types.py:79

### gates → `boolean`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/PlasticOS Graph Cognitive Engine.yaml`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:125, tests/unit/test_gates_all_types.py:16, tests/unit/test_gates_all_types.py:94, tests/unit/test_gates_all_types.py:95, tests/unit/test_gates_all_types.py:98

### gates → `composite`
- Spec ref: `gates (detected in spec text)`
- Found in: `current work/3D KG Embedding - HyperGraphs/beam_search.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:125, tests/unit/test_gates_all_types.py:25, current work/3D KG Embedding - HyperGraphs/beam_search.py:126, engine/gates/compiler.py:44, engine/gates/compiler.py:148

### gates → `enum_map`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:125, tests/unit/test_gates_all_types.py:19, tests/unit/test_gates_all_types.py:126, tests/unit/test_gates_all_types.py:127, tests/unit/test_gates_all_types.py:130

### gates → `exclusion`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/conftest.py`, `tests/integration/test_multi_tenant.py`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:126, tests/conftest.py:142, tests/conftest.py:248, tests/unit/test_gates_all_types.py:20, tests/unit/test_gates_all_types.py:141

### gates → `self_range`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:126, tests/unit/test_gates_all_types.py:21, tests/unit/test_gates_all_types.py:156, tests/unit/test_gates_all_types.py:157, tests/unit/test_gates_all_types.py:160

### gates → `freshness`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/research_agent_domain_spec.yaml`, `engine/config/schema.py`, `engine/config/settings.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:126, tests/unit/test_gates_all_types.py:22, tests/unit/test_gates_all_types.py:173, tests/unit/test_gates_all_types.py:174, tests/unit/test_gates_all_types.py:177

### gates → `temporal_range`
- Spec ref: `gates (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_gates_all_types.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:126, tests/unit/test_gates_all_types.py:23, tests/unit/test_gates_all_types.py:190, tests/unit/test_gates_all_types.py:191, tests/unit/test_gates_all_types.py:194

### gates → `traversal`
- Spec ref: `gates (detected in spec text)`
- Found in: `.github/pr_review_config.yaml`, `current work/l9_audit_fixes/engine/config/loader.py`, `current work/l9_audit_fixes/engine/handlers.py`, `current work/l9_audit_fixes/engine/scoring/assembler.py`, `current work/l9_audit_fixes/tests/test_config_loader.py`, `current work/l9_audit_fixes/tests/test_handlers.py`, `current work/l9_audit_fixes/tests/test_scoring_extended.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/__init__.py`, `engine/config/loader.py`, `engine/config/schema.py`, `engine/gates/compiler.py`, `engine/gates/null_semantics.py`, `engine/gates/registry.py`, `engine/gates/types/__init__.py`, `engine/gates/types/all_gates.py`, `engine/handlers.py`, `engine/scoring/assembler.py`, `engine/traversal/__init__.py`, `engine/traversal/assembler.py`, `engine/traversal/resolver.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/conftest.py`, `tests/integration/test_null_semantics.py`, `tests/performance/test_query_latency.py`, `tests/test_config_loader.py`, `tests/test_handlers.py`, `tests/test_scoring_extended.py`, `tests/unit/test_gates_all_types.py`, `tools/audit_rules.yaml`, `tools/l9_meta_injector.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:127, tools/l9_meta_injector.py:162, tools/l9_meta_injector.py:163, tools/l9_meta_injector.py:164, tests/conftest.py:150

### scoring → `geo_decay`
- Spec ref: `scoring (detected in spec text)`
- Found in: `current work/l9_audit_fixes/engine/scoring/assembler.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `engine/config/schema.py`, `engine/config/settings.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_scoring.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:169, tests/unit/test_scoring.py:46, tests/unit/test_scoring.py:47, tests/unit/test_scoring.py:51, current work/l9_audit_fixes/engine/scoring/assembler.py:47

### scoring → `log_normalized`
- Spec ref: `scoring (detected in spec text)`
- Found in: `current work/l9_audit_fixes/engine/scoring/assembler.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:169, current work/l9_audit_fixes/engine/scoring/assembler.py:48, current work/l9_audit_fixes/engine/scoring/assembler.py:81, engine/config/schema.py:95, engine/scoring/assembler.py:48

### scoring → `community_match`
- Spec ref: `scoring (detected in spec text)`
- Found in: `current work/l9_audit_fixes/engine/scoring/assembler.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:169, current work/l9_audit_fixes/engine/scoring/assembler.py:49, current work/l9_audit_fixes/engine/scoring/assembler.py:85, engine/config/schema.py:96, engine/config/schema.py:308

### scoring → `inverse_linear`
- Spec ref: `scoring (detected in spec text)`
- Found in: `current work/l9_audit_fixes/engine/scoring/assembler.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/unit/test_scoring.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:170, tests/unit/test_scoring.py:65, tests/unit/test_scoring.py:71, current work/l9_audit_fixes/engine/scoring/assembler.py:50, current work/l9_audit_fixes/engine/scoring/assembler.py:92

### scoring → `candidate_property`
- Spec ref: `scoring (detected in spec text)`
- Found in: `current work/l9_audit_fixes/engine/scoring/assembler.py`, `current work/l9_audit_fixes/tests/test_scoring_extended.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/aios_god_agent_domain_spec.yaml`, `domains/executive_assistant_domain_spec.yaml`, `domains/freight_matching_domain_spec.yaml`, `domains/healthcare_referral_domain_spec.yaml`, `domains/legal_discovery_domain_spec.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `domains/research_agent_domain_spec.yaml`, `domains/roofing_company_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tests/integration/test_null_semantics.py`, `tests/test_scoring_extended.py`, `tests/unit/test_scoring.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:170, tests/test_scoring_extended.py:2, tests/test_scoring_extended.py:65, tests/test_scoring_extended.py:66, tests/test_scoring_extended.py:67

### scoring → `custom_cypher`
- Spec ref: `scoring (detected in spec text)`
- Found in: `current work/l9_audit_fixes/engine/scoring/assembler.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/repo_as_agent_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:170, current work/l9_audit_fixes/engine/scoring/assembler.py:60, current work/l9_audit_fixes/engine/scoring/assembler.py:62, engine/config/schema.py:102, engine/config/schema.py:302

### scoring → `temporal_decay`
- Spec ref: `scoring (detected in spec text)`
- Found in: `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:171, tools/spec_extract.py:219, graph-cognitive-engine-spec-v1.1.0.yaml:1967

### v1.1_node → `TransactionOutcome`
- Spec ref: `v1.1 addition: TransactionOutcome node`
- Found in: `current work/l9_audit_fixes/engine/handlers.py`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/handlers.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:216, engine/handlers.py:275, engine/handlers.py:292, current work/l9_audit_fixes/engine/handlers.py:275, current work/l9_audit_fixes/engine/handlers.py:292

### v1.1_node → `SignalEvent`
- Spec ref: `v1.1 addition: SignalEvent node`
- Found in: `docs/plasticos_domain_spec_v0.4.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:216, docs/plasticos_domain_spec_v0.4.yaml:546, docs/plasticos_domain_spec_v0.4.yaml:1039, docs/plasticos_domain_spec_v0.4.yaml:1634

### v1.1_edge → `RESULTED_IN`
- Spec ref: `v1.1 addition: RESULTED_IN edge`
- Found in: `current work/l9_audit_fixes/engine/handlers.py`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/handlers.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:217, engine/handlers.py:275, engine/handlers.py:300, current work/l9_audit_fixes/engine/handlers.py:275, current work/l9_audit_fixes/engine/handlers.py:300

### v1.1_edge → `RESOLVED_FROM`
- Spec ref: `v1.1 addition: RESOLVED_FROM edge`
- Found in: `current work/l9_audit_fixes/engine/handlers.py`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/handlers.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:217, engine/handlers.py:326, engine/handlers.py:342, current work/l9_audit_fixes/engine/handlers.py:326, current work/l9_audit_fixes/engine/handlers.py:342

### v1.1_scoring → `temporal_decay`
- Spec ref: `v1.1 addition: temporal_decay scoring type`
- Found in: `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:171, tools/spec_extract.py:219, graph-cognitive-engine-spec-v1.1.0.yaml:1967

### gds_algorithm → `louvain`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/l9_meta_injector.py`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:276, tools/l9_meta_injector.py:168, engine/gds/scheduler.py:7, engine/gds/scheduler.py:14, engine/gds/scheduler.py:40

### gds_algorithm → `cooccurrence`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:276, engine/gds/scheduler.py:41, engine/gds/scheduler.py:87, engine/gds/scheduler.py:88, engine/gds/scheduler.py:166

### gds_algorithm → `reinforcement`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/config/settings.py`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:276, engine/config/settings.py:68, engine/gds/scheduler.py:14, engine/gds/scheduler.py:42, engine/gds/scheduler.py:89

### gds_algorithm → `temporal_recency`
- Spec ref: `gds (detected in spec text)`
- Found in: `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `engine/gds/scheduler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/audit_rules.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:276, engine/gds/scheduler.py:92, engine/gds/scheduler.py:285, graph-cognitive-engine-spec-v1.1.0.yaml:584, graph-cognitive-engine-spec-v1.1.0.yaml:621

### gds_algorithm → `similarity`
- Spec ref: `gds (detected in spec text)`
- Found in: `current work/3D KG Embedding - HyperGraphs/beam_search.py`, `current work/l9_audit_fixes/engine/scoring/assembler.py`, `docs/plasticos_domain_spec_v0.3.0.yaml`, `docs/plasticos_domain_spec_v0.4.yaml`, `domains/MASTER-SPEC-ALL-DOMAINS.yaml`, `domains/mortgage_brokerage_domain_spec.yaml`, `engine/config/schema.py`, `engine/scoring/assembler.py`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `tools/spec_extract.py`
- Lines: tools/spec_extract.py:277, current work/3D KG Embedding - HyperGraphs/beam_search.py:315, current work/3D KG Embedding - HyperGraphs/beam_search.py:326, current work/3D KG Embedding - HyperGraphs/beam_search.py:327, current work/3D KG Embedding - HyperGraphs/beam_search.py:328
