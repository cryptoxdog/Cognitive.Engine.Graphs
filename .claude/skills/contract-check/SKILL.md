---
name: contract-check
description: Run full contract verification against the CEG codebase
disable-model-invocation: true
---

# Contract Verification

Run the full CEG contract enforcement pipeline.

## Quick Check
```bash
python tools/contract_scanner.py
```
Scans for banned patterns. Maps violations to contract IDs (SEC-001 → Contract 9, ARCH-001 → Contract 1).

## Full Verification
```bash
python tools/verify_contracts.py
```
Verifies all 20 contract doc files exist and are wired to the scanner.

## Manual Contract Audit
For each contract, verify:
1. **Static check**: Does contract_scanner.py have a rule for it?
2. **Unit test**: Does tests/contracts/ have a test for it?
3. **Integration test**: Is the contract exercised end-to-end?
4. **Property test**: Are invariants checked with Hypothesis?

## Banned Pattern Reference
### Critical (merge blocked)
- SEC-001–007: Cypher injection, eval, exec, pickle, yaml.load
- ARCH-001–003: FastAPI/Starlette/uvicorn in engine
- DEL-001–002: httpx/requests in engine
- MEM-001–002: Direct INSERT into packetstore/memory_embeddings
- STUB-001: NotImplementedError outside tests

### High (merge blocked)
- ERR-001–002: Bare except, swallowed exceptions
- DI-001: FastAPI Depends in engine
- OBS-001–002: structlog.configure / logging.basicConfig in engine
- NAME-001: Pydantic Field(alias=...)
- SHARED-001–003: Redefining PacketEnvelope/TenantContext/ExecuteRequest
