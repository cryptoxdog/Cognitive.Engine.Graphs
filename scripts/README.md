<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [scripts]
tags: [L9_TEMPLATE, scripts, docs]
owner: platform
status: active
/L9_META -->

# L9 Scripts & Dashboards

## Scripts

Operational scripts for build, deploy, test, and maintenance.
All scripts use consistent env vars from `.env` or `iac/terraform.tfvars`.

```
scripts/
├── setup.sh              # One-shot local dev environment setup
├── dev.sh                # Start local dev stack (docker-compose)
├── test.sh               # Run test suite with coverage
├── build.sh              # Build & push Docker image
├── deploy.sh             # Deploy via Terraform
├── seed.sh               # Seed Neo4j with sample data per domain
├── migrate.sh            # Run schema constraints/indexes
├── health.sh             # Health check all services
└── gds-trigger.sh        # Manually trigger GDS jobs
```

## Dashboards

Grafana dashboards (JSON models) importable into any Grafana instance.
Also works with Grafana Cloud free tier.

```
dashboards/
├── grafana-api.json          # API latency, throughput, errors
├── grafana-neo4j.json        # Neo4j queries, heap, page cache
├── grafana-overview.json     # Single-pane system overview
└── docker-compose.monitoring.yml  # Grafana + Prometheus local stack
```

## Usage

```bash
# First time setup
chmod +x scripts/*.sh
./scripts/setup.sh

# Daily dev
./scripts/dev.sh          # Start everything
./scripts/test.sh         # Run tests
./scripts/health.sh       # Check services

# Deploy
./scripts/build.sh        # Build image
./scripts/deploy.sh prod  # Deploy to prod
```
