# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [build]
# tags: [L9_TEMPLATE, build, commands]
# owner: platform
# status: active
# --- /L9_META ---
# ─────────────────────────────────────────────────────────────
# L9 Graph Cognitive Engine — Makefile
# ─────────────────────────────────────────────────────────────

.PHONY: dev dev-build dev-down dev-logs dev-restart health
.PHONY: test test-unit test-integration seed shell neo4j-shell

# ── Docker Compose ─────────────────────────────────────────

dev:Start all services (detached)
	docker compose up -d

dev-build:Rebuild API image and start
	docker compose up -d --build

dev-down:Stop all services
	docker compose down

dev-logs:Tail all logs
	docker compose logs -f

dev-restart:Restart API only (fast iteration)
	docker compose restart api

# ── Health & Status ────────────────────────────────────────

health:Check all service health
	@echo "── API ──"
	@curl -sf http://localhost:8000/v1/health | python -m json.tool || echo "API: DOWN"
	@echo "── Neo4j ──"
	@docker exec l9-graph-neo4j cypher-shell -u neo4j -p l9-dev-password "RETURN 'ok'" 2>/dev/null || echo "Neo4j: DOWN"
	@echo "── Redis ──"
	@docker exec l9-graph-redis redis-cli ping || echo "Redis: DOWN"

# ── Testing ────────────────────────────────────────────────

test:Run full test suite
	docker compose exec api python -m pytest tests/ -v --tb=short

test-unit:Unit tests only (no Neo4j needed)
	docker compose exec api python -m pytest tests/unit/ -v --tb=short

test-integration:Integration tests (needs Neo4j)
	docker compose exec api python -m pytest tests/integration/ -v --tb=short

# ── Data Seeding ───────────────────────────────────────────

seed:Seed PlasticOS domain data into Neo4j
	docker compose exec api python -m engine.scripts.seed

# ── Shell Access ───────────────────────────────────────────

shell:Python shell inside API container
	docker compose exec api python

neo4j-shell:Cypher shell into Neo4j
	docker exec -it l9-graph-neo4j cypher-shell -u neo4j -p l9-dev-password

redis-shell:Redis CLI
	docker exec -it l9-graph-redis redis-cli

# ── Local Dev (API outside Docker, DBs in Docker) ─────────

local-dbs:Start only Neo4j + Redis
	docker compose up -d neo4j redis

local-api:Run API locally against Dockerized DBs
	PLASTICOS_NEO4J_URI=bolt://localhost:7687 \
	PLASTICOS_NEO4J_PASSWORD=l9-dev-password \
	PLASTICOS_REDIS_URL=redis://localhost:6379/0 \
	PLASTICOS_LOG_LEVEL=debug \
	uvicorn engine.api.app:create_app --factory --reload --port 8000

# ── Cleanup ────────────────────────────────────────────────

clean:	## Remove volumes + containers
	docker compose down -v --remove-orphans

# ── Quality Gates (local, no Docker) ───────────────────────

.PHONY: lint typecheck check

lint:	## Ruff lint + format (autofix)
	ruff check . --fix
	ruff format .

typecheck:	## MyPy type checking on engine/
	mypy engine/

check:	## Full local quality gate (lint + types + unit tests)
	@echo "── Lint ──"
	@ruff check . --fix
	@ruff format .
	@echo "── Type Check ──"
	@mypy engine/
	@echo "── Unit Tests ──"
	@PYTHONPATH="$${PYTHONPATH}:." python3 -m pytest tests/ -m "unit" --tb=short -q
	@echo "── All checks passed ──"

# ── L9_TEMPLATE Audit & Coverage ──────────────────────────

.PHONY: audit audit-strict coverage

audit:Run full architecture audit + spec coverage
	python3 tools/audit_engine.py
	python3 tools/spec_extract.py --fail-on NONE
	@echo "Reports in artifacts/"

audit-strict:Audit with strict failure (blocks on MISSING spec features)
	python3 tools/audit_engine.py
	python3 tools/spec_extract.py --fail-on MISSING

coverage:Spec coverage matrix only (no architecture audit)
	python3 tools/spec_extract.py --fail-on NONE
