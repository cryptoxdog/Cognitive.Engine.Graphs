# L9 Infrastructure as Code (Terraform)

## Overview

Reusable, env-var-driven Terraform modules for deploying L9 Graph Cognitive Engine.
Designed for copy-paste across repos — override via `terraform.tfvars` or env vars.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   ALB/NLB   │────▶│  ECS Fargate │────▶│   Neo4j     │
│  (ingress)  │     │  (API)       │     │  (graph DB) │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐     ┌─────────────┐
                    │   Redis      │     │ CloudWatch   │
                    │   (cache)    │     │ (monitoring) │
                    └──────────────┘     └─────────────┘
```

## Quick Start

```bash
# 1. Configure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# 2. Init
cd iac/
terraform init

# 3. Plan
terraform plan -out=plan.out

# 4. Apply
terraform apply plan.out
```

## Environment Variables (Consistent Across Repos)

All L9 repos use the same env var naming convention:

| Variable | Description | Default |
|----------|-------------|---------|
| `L9_PROJECT` | Project/repo name | `l9-engine` |
| `L9_ENV` | Environment (dev/staging/prod) | `dev` |
| `L9_REGION` | AWS region | `us-east-1` |
| `L9_DOMAIN_KEY` | Default domain pack | — |
| `NEO4J_URI` | Neo4j bolt URI | `bolt://neo4j:7687` |
| `NEO4J_USERNAME` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password (from SSM) | — |
| `NEO4J_DATABASE` | Default database | `neo4j` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `DOMAINS_ROOT` | Path to domain specs | `/app/domains` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `API_PORT` | API listen port | `8000` |
| `API_WORKERS` | Uvicorn worker count | `4` |
| `GDS_ENABLED` | Enable GDS scheduler | `true` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |

### Secret Management

Secrets are stored in AWS SSM Parameter Store:

```
/l9/{env}/neo4j/password
/l9/{env}/redis/auth_token
/l9/{env}/api/secret_key
```

## Module Structure

```
iac/
├── main.tf          # Root — wires modules together
├── variables.tf     # All input variables (override via tfvars)
├── outputs.tf       # Useful outputs (URLs, ARNs)
├── backend.tf       # S3 state backend
├── providers.tf     # AWS provider config
├── terraform.tfvars.example
└── modules/
    ├── networking/  # VPC, subnets, security groups
    ├── neo4j/       # Neo4j on ECS (multi-DB, GDS plugin)
    ├── api/         # FastAPI on ECS Fargate
    ├── redis/       # ElastiCache Redis
    └── monitoring/  # CloudWatch dashboards + alarms
```

## Per-Repo Usage

Copy `iac/` folder into any L9 repo. Override only what differs:

```hcl
# terraform.tfvars
project    = "plasticos"
env        = "prod"
api_image  = "123456789.dkr.ecr.us-east-1.amazonaws.com/plasticos-api:latest"
neo4j_size = "r6i.xlarge"
```

Everything else uses sensible defaults.

## Tear Down

```bash
terraform destroy
```
