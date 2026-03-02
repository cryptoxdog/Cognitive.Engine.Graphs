<!-- L9_META
l9_schema: 1
origin: domain-specific
engine: graph
layer: [test]
tags: [domains, testing, guide]
owner: domain-team
status: active
/L9_META -->

# domains/TESTING_GUIDE.md
"""
L9 Domains - Testing Guide

This guide provides sample queries for testing each domain pack.
"""

## Domain Testing Checklist

For each domain:
- [ ] Domain loads successfully (GET /v1/domains)
- [ ] Sample query returns candidates (POST /v1/match)
- [ ] NULL semantics work (test with missing fields)
- [ ] Bidirectional matching works (if applicable)
- [ ] GDS jobs schedule correctly (if configured)

---

## 1. PLASTICOS (Recycled Plastic Matching)

**Query File**: `domains/plasticos/test-query.json`

```json
{
  "query": {
    "buyer_id": "BUYER_TEST_001",
    "polymer_type": "PP",
    "min_quantity_lbs": 10000,
    "max_price_per_lb": 0.85,
    "contamination_tolerance_ppm": 100,
    "target_mfi": 12.0,
    "color_requirement": "natural",
    "pickup_zip": "28202",
    "lead_time_days": 14
  },
  "match_direction": "buyertosupplier",
  "top_n": 10,
  "weights": {
    "wgeo": 0.30,
    "wprice": 0.25,
    "wquality": 0.20,
    "wvelocity": 0.15
  }
}
```

**Expected Behavior**:
- Filters suppliers by polymer_type, contamination, MFI range
- Scores by distance, price, quality, transaction velocity
- Returns top 10 suppliers

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "Content-Type: application/json" \
  -H "X-Domain-Key: plasticos" \
  -d @domains/plasticos/test-query.json
```

---

## 2. MORTGAGE-BROKERAGE (Loan Matching)

**Query File**: `domains/mortgage-brokerage/test-query.json`

```json
{
  "query": {
    "borrowerid": "BRW_001",
    "creditscore": 720,
    "annualincomeusd": 85000,
    "monthlydebtusd": 1500,
    "loanamountusd": 350000,
    "propertyvalueusd": 450000,
    "downpaymentusd": 100000,
    "propertytype": "singlefamily",
    "propertystate": "NC",
    "occupancy": "owneroccupied",
    "loanpurpose": "purchase",
    "vaeligible": false,
    "firsttimebuyer": false
  },
  "match_direction": "borrowertoproduct",
  "top_n": 5,
  "weights": {
    "wrate": 0.40,
    "wapproval": 0.30,
    "wspeed": 0.20
  }
}
```

**Expected Behavior**:
- Computes DTI (21.2%) and LTV (77.8%)
- Filters products by credit score, DTI, LTV thresholds
- Excludes blacklisted lenders
- Scores by interest rate, approval rate, closing speed

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: mortgage-brokerage" \
  -d @domains/mortgage-brokerage/test-query.json
```

---

## 3. HEALTHCARE-REFERRAL (Provider Matching)

**Query File**: `domains/healthcare-referral/test-query.json`

```json
{
  "query": {
    "patientid": "PAT_12345",
    "age": 45,
    "zipcode": "28202",
    "insuranceplan": "BCBS_PPO",
    "primarycondition": "Type2Diabetes",
    "urgency": "routine",
    "maxdistancemiles": 15.0
  },
  "match_direction": "patienttoprovider",
  "top_n": 5,
  "weights": {
    "wdistance": 0.35,
    "wwait": 0.25,
    "wquality": 0.30
  }
}
```

**Expected Behavior**:
- Filters providers accepting BCBS_PPO insurance
- Checks new patient acceptance and panel capacity
- Scores by distance, wait time, quality score
- HIPAA-compliant (no prohibited factors)

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: healthcare-referral" \
  -d @domains/healthcare-referral/test-query.json
```

---

## 4. FREIGHT-MATCHING (Load-Carrier Matching)

**Query File**: `domains/freight-matching/test-query.json`

```json
{
  "query": {
    "loadid": "LOAD_9876",
    "pickuplat": 35.2271,
    "pickuplon": -80.8431,
    "deliverylat": 33.7490,
    "deliverylon": -84.3880,
    "weightlbs": 42000,
    "equipmenttype": "van",
    "pickupdate": "2026-03-05T08:00:00Z",
    "deliverydate": "2026-03-06T17:00:00Z",
    "ratepermile": 2.50
  },
  "match_direction": "loadtocarrier",
  "top_n": 10,
  "weights": {
    "wdeadhead": 0.40,
    "wrate": 0.25,
    "wontime": 0.20
  }
}
```

**Expected Behavior**:
- Filters carriers by weight capacity, equipment type
- Checks availability window
- Scores by deadhead distance, rate alignment, on-time rating

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: freight-matching" \
  -d @domains/freight-matching/test-query.json
```

---

## 5. ROOFING-COMPANY (Contractor-Project Matching)

**Query File**: `domains/roofing-company/test-query.json`

```json
{
  "query": {
    "projectid": "PROJ_RF_001",
    "zipcode": "28202",
    "rooftype": "asphalt",
    "squarefeet": 2400,
    "urgency": "standard",
    "hasinsuranceclaim": true,
    "budgetusd": 12000,
    "desiredstartdate": "2026-03-15"
  },
  "match_direction": "projecttocontractor",
  "top_n": 5,
  "weights": {
    "wrating": 0.35,
    "wcapacity": 0.25,
    "wprice": 0.25
  }
}
```

**Expected Behavior**:
- Filters contractors servicing zip 28202
- Checks specialty match (asphalt roofing)
- Verifies capacity and insurance licensing
- Scores by project rating, capacity utilization, price

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: roofing-company" \
  -d @domains/roofing-company/test-query.json
```

---

## 6. EXECUTIVE-ASSISTANT (Task-Expert Matching)

**Query File**: `domains/executive-assistant/test-query.json`

```json
{
  "query": {
    "taskid": "TASK_001",
    "category": "research",
    "priority": "high",
    "estimatedhours": 4.0,
    "deadline": "2026-02-28T17:00:00Z",
    "requiredskills": "market-research,data-analysis"
  },
  "match_direction": "tasktoexpert",
  "top_n": 3,
  "weights": {
    "wcompletion": 0.40,
    "wresponse": 0.30,
    "wutilization": 0.20
  }
}
```

**Expected Behavior**:
- Filters experts with required skills
- Checks availability (hours) and utilization
- Scores by completion rate, response time, current utilization

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: executive-assistant" \
  -d @domains/executive-assistant/test-query.json
```

---

## 7. RESEARCH-AGENT (Paper-Dataset Matching)

**Query File**: `domains/research-agent/test-query.json`

```json
{
  "query": {
    "queryid": "QUERY_001",
    "query": "transformer architectures for vision",
    "domain": "cv",
    "mindate": "2023-01-01",
    "requirescode": true,
    "requiresdataset": false
  },
  "match_direction": "querytopaper",
  "top_n": 10,
  "weights": {
    "wcitation": 0.35,
    "wrepro": 0.30,
    "wrecency": 0.20
  }
}
```

**Expected Behavior**:
- Filters papers by publication date (>= 2023-01-01)
- Requires code availability
- Scores by citation count, reproducibility, recency

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: research-agent" \
  -d @domains/research-agent/test-query.json
```

---

## 8. AIOS-GOD-AGENT (Tool Orchestration)

**Query File**: `domains/aios-god-agent/test-query.json`

```json
{
  "query": {
    "intentid": "INTENT_001",
    "userinput": "search arxiv for recent papers and summarize",
    "category": "search",
    "requiredcapabilities": "search,summarization,pdf-parsing",
    "maxexecutiontimeseconds": 60
  },
  "match_direction": "intenttotool",
  "top_n": 5,
  "weights": {
    "wreliability": 0.40,
    "wspeed": 0.30,
    "wcost": 0.20
  }
}
```

**Expected Behavior**:
- Filters tools with required capabilities
- Checks execution time limit
- Scores by reliability, execution speed, cost

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: aios-god-agent" \
  -d @domains/aios-god-agent/test-query.json
```

---

## 9. REPO-AS-AGENT (Code-Contributor Matching)

**Query File**: `domains/repo-as-agent/test-query.json`

```json
{
  "query": {
    "issueid": "ISSUE_456",
    "title": "Fix authentication bug in login flow",
    "labels": "bug,security,authentication",
    "affectedfiles": "src/auth/login.py,src/middleware/auth.py",
    "priority": "high",
    "estimatedcomplexity": "medium"
  },
  "match_direction": "issuetocontributor",
  "top_n": 3,
  "weights": {
    "wcontribution": 0.35,
    "wspeed": 0.30,
    "wexpertise": 0.25
  }
}
```

**Expected Behavior**:
- Filters contributors with code ownership of affected files
- Checks capacity (active PRs)
- Scores by contribution score, resolution speed, expertise match

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: repo-as-agent" \
  -d @domains/repo-as-agent/test-query.json
```

---

## 10. LEGAL-DISCOVERY (Case-Document Matching)

**Query File**: `domains/legal-discovery/test-query.json`

```json
{
  "query": {
    "caseid": "CASE_2026_001",
    "jurisdiction": "NC",
    "casetype": "civil",
    "topics": "contract-dispute,breach-of-contract,damages",
    "daterangestart": "2020-01-01",
    "daterangeend": "2025-12-31",
    "includeprivileged": false
  },
  "match_direction": "casetodocument",
  "top_n": 20,
  "weights": {
    "wrelevance": 0.40,
    "wcitation": 0.30,
    "wtemporal": 0.20
  }
}
```

**Expected Behavior**:
- Filters documents by jurisdiction (NC)
- Excludes privileged documents
- Filters by temporal range (2020-2025)
- Scores by relevance, citation authority, temporal proximity

**Test Command**:
```bash
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: legal-discovery" \
  -d @domains/legal-discovery/test-query.json
```

---

## NULL Semantics Testing

Test each domain with missing optional fields:

```bash
# Test with minimal required fields only
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: {domain-id}" \
  -d '{
    "query": {
      "id": "TEST_001",
      # ... only required fields
    },
    "match_direction": "{direction}",
    "top_n": 5
  }'
```

Expected: Gates with `nullbehavior: pass` should allow candidates through.

---

## Performance Benchmarking

```bash
# Load test with Apache Bench
ab -n 1000 -c 10 -T 'application/json' \
  -H "X-Domain-Key: {domain-id}" \
  -p test-query.json \
  http://localhost:8000/v1/match

# Target metrics:
# - p95 latency: < 500ms
# - p99 latency: < 1s
# - Throughput: > 100 QPS
```

---

## GDS Job Verification

For domains with GDS jobs:

```bash
# Check scheduler status
curl http://localhost:8000/v1/admin/gds/status

# Manually trigger job
curl -X POST http://localhost:8000/v1/admin/gds/trigger/{job_name}

# View job results
curl http://localhost:8000/v1/admin/gds/results/{job_name}
```

---

## Multi-Tenant Isolation Testing

```bash
# Create test data in domain A
curl -X POST http://localhost:8000/v1/sync/Supplier \
  -H "X-Domain-Key: plasticos" \
  -d @supplier-data.json

# Query domain B (should see zero results)
curl -X POST http://localhost:8000/v1/match \
  -H "X-Domain-Key: mortgage-brokerage" \
  -d @test-query.json

# Expected: Zero cross-domain leakage
```

---

## Troubleshooting

### Domain fails to load
- Check YAML syntax: `yamllint domains/{domain-id}/spec.yaml`
- Verify all cross-references (gates → ontology, GDS → edges)
- Check logs: `docker logs {container-id}`

### Query returns zero candidates
- Check gates: disable one by one to find blocker
- Verify traversal patterns match ontology
- Test with broader parameters

### Scoring produces unexpected results
- Set all weights to 0.0 except one to isolate dimension
- Check NULL values in properties used by scoring
- Verify computation type matches data distribution

---

## Next Steps

1. Run all 10 domain tests
2. Fix any validation errors
3. Benchmark performance
4. Load production data
5. Configure GDS jobs
6. Deploy to staging
