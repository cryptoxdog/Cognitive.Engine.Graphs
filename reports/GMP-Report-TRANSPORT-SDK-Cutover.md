# GMP Report — Transport SDK Cutover

## Header

- GMP ID: `TRANSPORT-SDK-CUTOVER`
- Title: Replace local chassis transport with `constellation-node-sdk`
- Tier: `T3/T4 transport boundary`
- Date: `2026-04-11`
- Status: `PARTIAL-VALIDATED`

## Locked TODO Plan

- Lock SDK package/import surface and target adoption mode
- Replace local `/v1/execute` runtime with the SDK node runtime
- Re-register handlers through the SDK registry
- Move active outbound transport to Gate-only egress
- Remove duplicate local chassis transport files
- Retarget transport tests to `TransportPacket`
- Update env/contract/workflow references

## Scope Boundaries

- Modified live transport/runtime files only; business enrichment logic remained intact.
- Did not edit the attached plan file.
- Did not push or commit.

## Files Modified

- `pyproject.toml`
- `requirements-ci.txt`
- `app/core/config.py`
- `app/main.py`
- `app/api/v1/chassis_endpoint.py`
- `app/engines/graph_sync_client.py`
- `app/engines/orchestration_layer.py`
- `app/engines/packet_router.py`
- `app/engines/handlers.py`
- `app/services/chassis_handlers.py`
- `app/services/graph_return_channel.py`
- `app/services/contract_enforcement.py`
- `app/services/convergence_helpers.py`
- `app/services/graph_sync_hooks.py`
- `tests/unit/test_orchestration_layer.py`
- `tests/test_pr21_packet_router.py`
- `tests/services/test_graph_return_channel.py`
- `tests/unit/test_chassis_contract.py`
- `tests/contracts/test_packet_envelope_contract.py`
- `tests/contracts/tier2/test_enforcement_packet_runtime.py`
- `tests/services/test_contract_enforcement.py`
- `tests/contracts/test_config_env_contract.py`
- `tests/integration/test_gap_fixes.py`
- `docs/contracts/agents/protocols/packet-envelope.yaml`
- `docs/contracts/config/env-contract.yaml`
- `.env.example`
- `workflow_state.md`

## Files Removed

- `chassis/__init__.py`
- `chassis/router.py`
- `chassis/registry.py`
- `chassis/envelope.py`
- `chassis/node_client.py`
- `chassis/lifecycle.py`
- `chassis/middleware.py`
- `app/engines/chassis_contract.py`
- `app/services/packet_enforcement.py`

## Validation Results

- Installed SDK locally with:
  - `python3 -m pip install --user --break-system-packages "git+https://github.com/cryptoxdog/Gate_SDK.git@main"`
- Installed storage-layer imports needed by the broader slice:
  - `python3 -m pip install --user --break-system-packages sqlalchemy asyncpg`
- Passed targeted validation slice:
  - `python3 -m pytest --no-cov tests/unit/test_orchestration_layer.py tests/test_pr21_packet_router.py tests/services/test_graph_return_channel.py tests/unit/test_chassis_contract.py tests/contracts/test_packet_envelope_contract.py -q`
- Result:
  - `30 passed`
- Passed broader transport-adjacent slice:
  - `python3 -m pytest --no-cov tests/services/test_contract_enforcement.py tests/contracts/test_config_env_contract.py tests/compliance/test_architecture.py tests/contracts/tier2/test_enforcement_packet_runtime.py -q`
  - `126 passed` when run together with `tests/integration/test_gap_fixes.py`, with only 8 failures remaining in that legacy integration file

## Phase 5 Recursive Verification

- Runtime ingress now comes from `create_node_app(...)` in `app/main.py`.
- Active handler registration uses `constellation_node_sdk.runtime.handlers.register_handler`.
- Active outbound transport uses `GateClient`/`TransportPacket`; direct peer `httpx` transport was removed from the live runtime helpers.
- Packet/runtime tests now validate SDK behavior instead of the deleted local chassis internals.

## Outstanding Items

- Broader suite validation still needs a full run beyond the targeted transport slice.
- Legacy config fields `graph_node_url`, `score_node_url`, and `route_node_url` remain as backward-compatible settings and should be pruned in a later cleanup once downstream dependencies are confirmed.
- `tests/integration/test_gap_fixes.py` still targets older convergence/result-store/config behavior unrelated to the transport SDK cutover and was not rewritten in this GMP.

## Final Declaration

- The repo’s active transport boundary has been cut over from the local `chassis/` implementation to `constellation-node-sdk`.
- The cutover is validated for the primary runtime/handler/egress/test path, with broader suite confirmation still pending.
