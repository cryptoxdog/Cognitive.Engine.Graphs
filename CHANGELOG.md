# Changelog

All notable changes to L9 Engine will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
