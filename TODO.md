# TODO — Graph Cognitive Engine

## 🚀 Deployment Pipeline

### 1. Merge PRs
- [ ] Review and merge any open PRs
- [ ] Resolve merge conflicts if present
- [ ] Ensure all PR checks pass before merge

### 2. Preflight Check
- [ ] Run `make lint` — ruff check + mypy
- [ ] Run `python tools/verify_contracts.py` — 20 contracts present
- [ ] Run `python tools/contract_scanner.py` — no violations
- [ ] Verify `.env` / secrets configured (KUBECONFIG, SLACK_WEBHOOK_URL)
- [ ] Review uncommitted changes in git status

### 3. Testing
- [ ] Run `make test` — full pytest suite
- [ ] Run `make test-unit` — gate compilation, scoring math
- [ ] Run `make test-integration` — testcontainers-neo4j pipeline
- [ ] Run `make test-compliance` — prohibited factors enforcement
- [ ] Verify <200ms p95 match latency (performance)

### 4. Deploy
- [ ] Build Docker image: `make build`
- [ ] Push to registry
- [ ] Deploy to staging: `make deploy ENV=staging`
- [ ] Smoke test staging endpoints
- [ ] Deploy to production: `make deploy ENV=prod`
- [ ] Verify health check: `GET /v1/health`

---

## 📋 Open Items

### Configuration
- [ ] Set GitHub Secrets: KUBECONFIG, SLACK_WEBHOOK_URL
- [ ] Configure branch protection (contract-files, contract-scan, lint, test)
- [ ] Decide: Should MEDIUM audit findings fail CI?
- [ ] Decide: Should `artifacts/` outputs be committed?

### Cleanup
- [ ] Review 8 modified files in git status
- [ ] Commit or discard uncommitted changes
- [ ] Wire `make audit` into local/dev workflow

---

## 📝 Notes

**Last GMP:** GMP-130 — L9 Contract Enforcement System (2026-03-01)

**Uncommitted Files:**
- `chassis/actions.py`
- `engine/compliance/audit.py`
- `engine/config/settings.py`
- `engine/gds/scheduler.py`
- `engine/handlers.py`
- `engine/packet/packet_store.sql`
- `engine/sync/generator.py`
- `scripts/entrypoint.sh`
