<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [deployment, infrastructure, hetzner]
owner: engine-team
status: active
/L9_META -->

# Deployment — L9 Graph Cognitive Engine

## Production Server

The Graph Cognitive Engine is deployed on Hetzner Cloud.

### Server Details

| Property | Value |
|----------|-------|
| **Provider** | Hetzner Cloud |
| **Server Name** | `l9-ceg` |
| **Server ID** | `#123423549` |
| **Plan** | CX33 |
| **IPv4** | `178.104.43.11` |
| **IPv6** | `2a01:4f8:1c19:15e4::/64` |
| **vCPU** | 4 (x86) |
| **RAM** | 8 GB |
| **Disk** | 80 GB Local |
| **Traffic** | 20 TB/month |
| **Cost** | $5.99/month |
| **Labels** | `managed_by: l9agent`, `role: ceg` |

### Network Endpoints

| Service | Endpoint | Port |
|---------|----------|------|
| **API** | `http://178.104.43.11:8000` | 8000 |
| **Health Check** | `http://178.104.43.11:8000/v1/health` | 8000 |
| **Neo4j Browser** | `http://178.104.43.11:7474` | 7474 |
| **Neo4j Bolt** | `bolt://178.104.43.11:7687` | 7687 |
| **Redis** | `redis://178.104.43.11:6379` | 6379 |

### SSH Access

```bash
ssh root@178.104.43.11
```

### Deployment Path

```
/opt/ceg/
```

The repo is cloned directly on the server and containers are built locally.

### Environment Variables (Production)

Set via docker-compose or systemd environment:

```bash
L9_ENV=prod
L9_LIFECYCLE_HOOK=engine.boot:GraphLifecycle
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<from-secrets>
REDIS_URL=redis://redis:6379/0
API_PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=[]
DOMAINS_ROOT=domains
```

## Deployment Commands

### Check Server Health

```bash
# API health
curl http://178.104.43.11:8000/v1/health

# Neo4j connectivity
curl http://178.104.43.11:7474

# SSH and check containers
ssh root@178.104.43.11 "docker ps"
```

### Deploy New Version

```bash
# SSH to server, pull latest, rebuild and restart
ssh root@178.104.43.11 "cd /opt/ceg && git pull origin main && docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml up -d"
```

### View Logs

```bash
ssh root@178.104.43.11 "cd /opt/ceg && docker compose -f docker-compose.prod.yml logs -f api"
```

### Restart Services

```bash
ssh root@178.104.43.11 "cd /opt/ceg && docker compose -f docker-compose.prod.yml restart api"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    l9-ceg (178.104.43.11)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   API       │  │   Neo4j     │  │   Redis     │         │
│  │  :8000      │  │  :7474/7687 │  │  :6379      │         │
│  │             │  │             │  │             │         │
│  │ FastAPI +   │  │ Graph DB +  │  │ Cache +     │         │
│  │ Uvicorn     │  │ GDS Plugin  │  │ Sessions    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Monitoring

- **Prometheus Metrics**: `http://178.104.43.11:8000/v1/metrics`
- **Health Check**: `http://178.104.43.11:8000/v1/health`

## Backup & Recovery

Neo4j data is stored in Docker volumes. Backup commands:

```bash
# Backup Neo4j
ssh root@178.104.43.11 "docker exec neo4j neo4j-admin database dump neo4j --to-path=/backups"

# Copy backup locally
scp root@178.104.43.11:/opt/l9-ceg/backups/neo4j.dump ./backups/
```

## Firewall Rules

Managed via Hetzner Cloud Firewall. Required ports:

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | Restricted IPs | SSH |
| 8000 | TCP | 0.0.0.0/0 | API |
| 7474 | TCP | Restricted IPs | Neo4j Browser |
| 7687 | TCP | Restricted IPs | Neo4j Bolt |

## Related Documentation

- [Infrastructure as Code](../iac/README.md)
- [Docker Compose (prod)](../docker-compose.prod.yml)
- [Dockerfile (prod)](../Dockerfile.prod)
