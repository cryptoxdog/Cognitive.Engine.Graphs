<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [changelog]
owner: engine-team
status: active
/L9_META -->

# Changelog

All notable changes to L9 Engine will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-03-10 — KGE Mathematical Core Hardening

### Patches Applied
- `transformations.py`: Added `Shear` class (5th CompoundE3D primitive)
- `ensemble.py`: Fixed `_borda_count()` normalization bug (literal `0` replaced with actual rank index)
- `ensemble.py`: Added `_rrf_score()` to `RankAggregationEnsemble`
- `ensemble.py`: Added `compute_entropy_confidence()` to `MixtureOfExpertsEnsemble`
- `compound_e3d.py`: Added `_head_ops`, `_tail_ops`, `_platt_alpha`, `_platt_beta` fields to `__init__`
- `compound_e3d.py`: Replaced TransE `_distance()` with CompoundE3D block-diagonal operator scoring (with TransE fallback)
- `compound_e3d.py`: Added `calibrate_platt()` for Platt scaling
- `compound_e3d.py`: Added `build_icp_centroid()` and `score_against_icp()`
- `beam_search.py`: Added `CascadeVariant` dataclass
- `beam_search.py`: Replaced random `_score_candidate()` stub with embedding-based evaluation; added `_stopping_criterion()`
- `assembler.py`: Replaced `_compile_communitymatch()` with soft Jaccard/lift implementation
- `assembler.py`: Replaced `_compile_pricealignment()` with log-ratio distance
- `assembler.py`: Replaced `_compile_temporalproximity()` with multi-signal exponential decay

### Not Changed
- All L9_META headers
- All public API signatures
- PacketEnvelope schema
- DomainSpec YAML structure
- EnsembleResult dataclass
- All existing tests (all must still pass)

## [Unreleased]

### Added
- 10 gate types: threshold, range, boolean, enum_map, exclusion, self_range, freshness, temporal_range, traversal, composite
- Scoring assembler with geodecay, inverse linear, candidate property computations
- Multi-tenant architecture (database-per-tenant)
- YAML-driven domain specification system
- Bidirectional matching with gate/scoring inversion
- UNWIND-based bulk sync (MERGE and MATCH/SET strategies)
- GDS scheduler for PageRank, community detection, similarity
- ECOA/HIPAA compliance enforcement (prohibited factors, PII handling)
- Audit logging with configurable retention
- Terraform IaC (ECS Fargate, Neo4j, Redis, monitoring)
- Grafana dashboards (API, Neo4j, overview)
- Operational scripts (setup, dev, test, build, deploy, seed, migrate, health)
- 200+ tests with 70%+ coverage target
- Prometheus metrics endpoint
- Docker Compose local dev stack
- Multi-stage Dockerfile

### Domain Packs
- Plastics marketplace (plasticos)
- Mortgage brokerage
- Healthcare matching

## [0.1.0] - 2026-02-28

### Added
- Initial release
- Core engine architecture
- Gate compiler
- Scoring assembler
- Sync generator
- Domain spec loader
