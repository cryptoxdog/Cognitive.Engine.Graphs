# System State

Update this file when merging PRs.

## Open PRs (seL4 Upgrade Program)
| PR | Wave | Title | Status |
|----|------|-------|--------|
| #57 | 1 | Invariant & Validation Hardening | OPEN |
| #58 | 2 | Refinement-Inspired Scoring | OPEN |
| #59 | 3 | Capability & Access Control | OPEN |
| #60 | 4 | State Management & Resilience | OPEN |
| #64 | 5 | Correctness Tooling & Verification | OPEN |
| #63 | 6 | Dormant Feature Activation | OPEN |
| #65 | — | seL4 Technical & Executive Documentation | OPEN |
| #66 | — | CLAUDE.md Comprehensive Revision | OPEN |

## Dormant Subsystems
| System | Blocker | Activation |
|--------|---------|------------|
| KGE (CompoundE3D) | kge_enabled=False | Wave 6 merge → trigger_kge admin subaction |
| GDPR erasure | erase_subject() unwired | Wave 6 merge → erase_subject admin subaction |
| PostgreSQL persistence | Not in docker-compose | Provision PostgreSQL → wire asyncpg.Pool |
| LLM security | FeatureNotEnabled | Set LLM_PROVIDER + LLM_API_KEY |
