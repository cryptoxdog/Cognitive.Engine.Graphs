<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Omit memory system from scope it was only an example of how the envelope was used but it was a WIP. I wanna only use the concept but rebuilt it completely as I just said to be used inside a constellation ai ecosystem- full rls per product and full security hardening / hashing / tracing for auditability

Four files. 45K chars. Zero memory substrate dependency. Built for a constellation.

## The Files

| File | Chars | Purpose |
| :-- | :-- | :-- |
| **packet_envelope.py** | 13,035 | The schema — every byte in the constellation is this |
| **packet_store.sql** | 18,447 | DDL with full RLS, audit log, GDPR erasure, lineage walks |
| **chassis_contract.py** | 4,329 | Inflate ingress, deflate egress, delegate between nodes |
| **test_packet_envelope.py** | 9,297 | 30 tests: immutability, integrity, delegation chains, stacked ops |

## What's New vs. Everything Before

The old envelope was a flat 16-field container designed for a memory system's event log. This is a **constellation routing protocol** with cryptographic integrity.[^1]

### Addressing — packets know where they're going

`PacketAddress` has `source_node`, `destination_node`, `reply_to` . When PlasticOS delegates to the EnrichmentAPI, the packet says exactly where it came from, where it's going, and where to send the response. The old envelope had no concept of destination.

### Tenant Context Stack — multi-tenant delegation

`TenantContext` carries `actor` (who's doing it), `on_behalf_of` (who authorized it), `originator` (who started the chain), `org_id`, and `user_id` . When Agent (L9 internal) orchestrates a match for Acme using GlobalCorp's data, all three identity layers are on the packet. The old envelope had a single flat `tenant_id`.

### Delegation Chain — cryptographic authorization audit

`DelegationLink` records who authorized whom to do what, with scoped permissions and optional HMAC proof . The `delegate_to_node()` function in the chassis contract auto-appends delegation links and sets `audit_required=True` . Stacked delegation (Agent → Tool A → Tool B → Tool C) accumulates links — the test suite proves a 2-hop chain preserves `root_id` and carries both delegation records .

### Hop Trace — constellation journey log

`HopEntry` records every node the packet touched, with timestamps, status, and optional HMAC signature . This is the equivalent of HTTP `Via` headers but for AI tools. The SQL stores these in a dedicated `hop_trace` table with per-packet ordering .

### Full RLS — per-product tenant isolation

The SQL has `ROW LEVEL SECURITY` on every table :


| Table | RLS Policy |
| :-- | :-- |
| `packet_store` | Tenant sees packets where they are `actor`, `originator`, or `on_behalf_of` |
| `hop_trace` | Inherits packet tenant isolation via subquery |
| `delegation_chain` | Visible to both `delegator` and `delegatee` tenants |
| `packet_audit_log` | Tenant sees own audit entries; insert-only (no delete/update) |
| `lineage_graph` | Visible if either parent or child belongs to your tenant |

Three roles: `l9_product` (RLS-enforced), `l9_admin` (bypasses RLS for GDPR/governance), `l9_auditor` (read-only audit access) .

### Security Hardening

`PacketSecurity` carries `content_hash` (SHA-256), optional `signature` (HMAC-SHA256), `signing_key_id`, `classification` (public/internal/confidential/restricted), `encryption_status`, and `pii_fields` tuple for GDPR ops . The hash covers `(packet_type, action, payload, tenant, address)` — canonical JSON, sorted keys, deterministic .

### Governance

`PacketGovernance` carries `intent`, `compliance_tags` (GDPR/SOC2/ECOA/HIPAA), `retention_days`, `redaction_applied`, `audit_required`, and `data_subject_id` for right-to-delete . The SQL has a `gdpr_erase_subject()` function that logs to audit before deleting .

### No UPDATE Policy

There is deliberately **no UPDATE RLS policy** on `packet_store` . Packets are immutable. If you need to change data, `derive()` a new packet. The audit trail is append-only.

### Constellation Flow Example

```
Agent creates REQUEST packet
  → address: {source: "agent", dest: "plasticos", reply_to: "agent"}
  → tenant: {actor: "acme", originator: "acme"}

Agent delegates to PlasticOS via delegate_to_node()
  → delegation_chain: [{delegator: "agent", delegatee: "plasticos", scope: ("match",)}]
  → hop_trace: [{node: "agent", action: "delegate", status: "delegated"}]

PlasticOS delegates to EnrichmentAPI
  → delegation_chain grows to 2 links
  → hop_trace grows to 2 entries
  → lineage.generation = 2, root_id = original request

EnrichmentAPI responds via deflate_egress()
  → address: {source: "enrichment", dest: "plasticos"}
  → hop_trace: 3 entries total
  → Full audit trail in packet_audit_log
  → RLS ensures Acme sees everything, other tenants see nothing
```

Every hop is signed, every delegation is scoped, every packet is hashable, every tenant is isolated, every action is auditable .

<div align="center">⁂</div>

[^1]: PacketEnvelope-PacketStore-Architecture.md

