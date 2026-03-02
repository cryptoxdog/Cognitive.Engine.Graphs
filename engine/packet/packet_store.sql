-- L9 PacketStore v3.0.0 — Full RLS, Security Hardening, Constellation-Ready
-- Zero legacy. Clean-slate DDL.

-- ════════════════════════════════════════════════════════════════
--  EXTENSIONS
-- ════════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ════════════════════════════════════════════════════════════════
--  DROP LEGACY (burn the boats)
-- ════════════════════════════════════════════════════════════════
DROP TABLE IF EXISTS lineage_graph CASCADE;
DROP TABLE IF EXISTS packet_store CASCADE;
DROP TABLE IF EXISTS packet_audit_log CASCADE;

-- ════════════════════════════════════════════════════════════════
--  CORE TABLE
-- ════════════════════════════════════════════════════════════════
CREATE TABLE packet_store (
    -- identity
    packet_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    packet_type         TEXT NOT NULL,
    action              TEXT NOT NULL,
    schema_version      TEXT NOT NULL DEFAULT '3.0.0',

    -- routing
    source_node         TEXT NOT NULL,
    destination_node    TEXT,
    reply_to            TEXT,

    -- tenant (denormalized for RLS performance)
    actor_tenant        TEXT NOT NULL,
    on_behalf_of        TEXT,
    originator_tenant   TEXT NOT NULL,
    org_id              TEXT,
    user_id             TEXT,

    -- payload (encrypted at rest via pgcrypto if classification != 'public')
    envelope            JSONB NOT NULL,          -- full PacketEnvelope serialized
    payload_encrypted   BYTEA,                   -- AES-256 encrypted payload (for restricted/confidential)

    -- security
    content_hash        TEXT NOT NULL,            -- SHA-256
    hash_algorithm      TEXT NOT NULL DEFAULT 'sha256',
    signature           TEXT,                     -- HMAC-SHA256
    signing_key_id      TEXT,
    classification      TEXT NOT NULL DEFAULT 'internal',
    encryption_status   TEXT NOT NULL DEFAULT 'plaintext',

    -- observability
    trace_id            TEXT NOT NULL,
    span_id             TEXT,
    correlation_id      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at         TIMESTAMPTZ DEFAULT now(),

    -- lineage
    parent_ids          UUID[] DEFAULT '{}',
    root_id             UUID,
    generation          INT NOT NULL DEFAULT 0,
    derivation_type     TEXT,

    -- governance
    intent              TEXT,
    compliance_tags     TEXT[] DEFAULT '{}',
    retention_days      INT,
    redaction_applied   BOOLEAN NOT NULL DEFAULT FALSE,
    audit_required      BOOLEAN NOT NULL DEFAULT FALSE,
    data_subject_id     TEXT,                    -- GDPR: who this data is about

    -- labels + expiry
    tags                TEXT[] DEFAULT '{}',
    ttl                 TIMESTAMPTZ,

    -- constraints
    CONSTRAINT uq_content_hash UNIQUE (content_hash, actor_tenant)
);

-- ════════════════════════════════════════════════════════════════
--  LINEAGE GRAPH (materialized derivation chains)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE lineage_graph (
    parent_id   UUID NOT NULL REFERENCES packet_store(packet_id) ON DELETE CASCADE,
    child_id    UUID NOT NULL REFERENCES packet_store(packet_id) ON DELETE CASCADE,
    generation  INT NOT NULL,
    derivation_type TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (parent_id, child_id)
);

-- ════════════════════════════════════════════════════════════════
--  HOP TRACE (constellation journey log)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE hop_trace (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    packet_id   UUID NOT NULL REFERENCES packet_store(packet_id) ON DELETE CASCADE,
    node_id     TEXT NOT NULL,
    action      TEXT NOT NULL,
    entered_at  TIMESTAMPTZ NOT NULL,
    exited_at   TIMESTAMPTZ,
    status      TEXT,
    signature   TEXT,                          -- HMAC proving node touched it
    seq         INT NOT NULL                   -- ordering within packet
);

-- ════════════════════════════════════════════════════════════════
--  DELEGATION CHAIN (authorization audit trail)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE delegation_chain (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    packet_id   UUID NOT NULL REFERENCES packet_store(packet_id) ON DELETE CASCADE,
    delegator   TEXT NOT NULL,
    delegatee   TEXT NOT NULL,
    scope       TEXT[] NOT NULL,               -- permitted actions
    granted_at  TIMESTAMPTZ NOT NULL,
    expires_at  TIMESTAMPTZ,
    proof_hash  TEXT,                          -- HMAC of delegation grant
    seq         INT NOT NULL                   -- ordering within packet
);

-- ════════════════════════════════════════════════════════════════
--  AUDIT LOG (append-only, immutable)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE packet_audit_log (
    audit_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    packet_id           UUID,                          -- no FK: survives packet deletion
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT now(),
    action              TEXT NOT NULL,                 -- AuditAction enum value
    severity            TEXT NOT NULL DEFAULT 'info', -- info | warning | critical
    actor               TEXT NOT NULL,                 -- who performed the action
    tenant              TEXT NOT NULL,                 -- org isolation key (actor_tenant)
    trace_id            TEXT,                          -- W3C trace context
    resource            TEXT,                          -- e.g., "Facility:42"
    resource_type       TEXT,                          -- e.g., "Facility"
    detail              TEXT,                          -- human-readable description
    payload_hash        TEXT,                          -- SHA-256 of related payload
    compliance_tags     TEXT[] DEFAULT '{}',           -- GDPR, SOC2, ECOA
    pii_fields_accessed TEXT[] DEFAULT '{}',
    data_subject_id     TEXT,                          -- GDPR right-to-delete tracking
    outcome             TEXT NOT NULL DEFAULT 'success', -- success | failure | denied
    metadata            JSONB DEFAULT '{}',
    ip_address          INET,
    performed_by        TEXT                           -- legacy: node or user that did it
);

-- ════════════════════════════════════════════════════════════════
--  INDEXES
-- ════════════════════════════════════════════════════════════════
CREATE INDEX idx_ps_actor_tenant     ON packet_store (actor_tenant);
CREATE INDEX idx_ps_originator       ON packet_store (originator_tenant);
CREATE INDEX idx_ps_trace            ON packet_store (trace_id);
CREATE INDEX idx_ps_correlation      ON packet_store (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX idx_ps_source_node      ON packet_store (source_node);
CREATE INDEX idx_ps_dest_node        ON packet_store (destination_node) WHERE destination_node IS NOT NULL;
CREATE INDEX idx_ps_type_action      ON packet_store (packet_type, action);
CREATE INDEX idx_ps_created          ON packet_store (created_at DESC);
CREATE INDEX idx_ps_ttl              ON packet_store (ttl) WHERE ttl IS NOT NULL;
CREATE INDEX idx_ps_root             ON packet_store (root_id) WHERE root_id IS NOT NULL;
CREATE INDEX idx_ps_classification   ON packet_store (classification);
CREATE INDEX idx_ps_data_subject     ON packet_store (data_subject_id) WHERE data_subject_id IS NOT NULL;
CREATE INDEX idx_ps_tags             ON packet_store USING GIN (tags);
CREATE INDEX idx_ps_compliance       ON packet_store USING GIN (compliance_tags);
CREATE INDEX idx_ps_envelope         ON packet_store USING GIN (envelope jsonb_path_ops);

CREATE INDEX idx_ht_packet           ON hop_trace (packet_id, seq);
CREATE INDEX idx_dc_packet           ON delegation_chain (packet_id, seq);
CREATE INDEX idx_pal_packet          ON packet_audit_log (packet_id);
CREATE INDEX idx_pal_tenant          ON packet_audit_log (tenant, timestamp DESC);
CREATE INDEX idx_lg_child            ON lineage_graph (child_id);

-- ════════════════════════════════════════════════════════════════
--  ROW-LEVEL SECURITY
-- ════════════════════════════════════════════════════════════════

ALTER TABLE packet_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE hop_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE delegation_chain ENABLE ROW LEVEL SECURITY;
ALTER TABLE packet_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE lineage_graph ENABLE ROW LEVEL SECURITY;

-- Tenant isolation: each product/tenant sees only its own packets
-- current_setting('app.current_tenant') set by chassis on each connection

CREATE POLICY tenant_isolation_select ON packet_store
    FOR SELECT USING (
        actor_tenant = current_setting('app.current_tenant', true)
        OR originator_tenant = current_setting('app.current_tenant', true)
        OR on_behalf_of = current_setting('app.current_tenant', true)
    );

CREATE POLICY tenant_isolation_insert ON packet_store
    FOR INSERT WITH CHECK (
        actor_tenant = current_setting('app.current_tenant', true)
    );

CREATE POLICY tenant_isolation_delete ON packet_store
    FOR DELETE USING (
        actor_tenant = current_setting('app.current_tenant', true)
    );

-- No UPDATE policy: packets are immutable. No updates allowed.
-- If you need to change data, derive() a new packet.

-- Hop trace inherits packet tenant isolation
CREATE POLICY hop_tenant ON hop_trace
    FOR ALL USING (
        packet_id IN (
            SELECT packet_id FROM packet_store
            WHERE actor_tenant = current_setting('app.current_tenant', true)
               OR originator_tenant = current_setting('app.current_tenant', true)
        )
    );

-- Delegation chain: visible to both delegator and delegatee tenants
CREATE POLICY deleg_tenant ON delegation_chain
    FOR ALL USING (
        delegator = current_setting('app.current_tenant', true)
        OR delegatee = current_setting('app.current_tenant', true)
    );

-- Audit log: tenant sees only its own audit entries
CREATE POLICY audit_tenant ON packet_audit_log
    FOR SELECT USING (
        tenant = current_setting('app.current_tenant', true)
    );

-- Audit log: insert-only, no delete/update
CREATE POLICY audit_insert ON packet_audit_log
    FOR INSERT WITH CHECK (true);

-- Lineage: visible if either end is yours
CREATE POLICY lineage_tenant ON lineage_graph
    FOR ALL USING (
        parent_id IN (SELECT packet_id FROM packet_store WHERE actor_tenant = current_setting('app.current_tenant', true))
        OR child_id IN (SELECT packet_id FROM packet_store WHERE actor_tenant = current_setting('app.current_tenant', true))
    );

-- ════════════════════════════════════════════════════════════════
--  SERVICE ROLES
-- ════════════════════════════════════════════════════════════════

-- Product role: RLS-enforced, used by engine connections
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'l9_product') THEN
        CREATE ROLE l9_product NOLOGIN;
    END IF;
END $$;

GRANT SELECT, INSERT, DELETE ON packet_store TO l9_product;
GRANT SELECT, INSERT ON hop_trace TO l9_product;
GRANT SELECT, INSERT ON delegation_chain TO l9_product;
GRANT INSERT, SELECT ON packet_audit_log TO l9_product;
GRANT SELECT, INSERT, DELETE ON lineage_graph TO l9_product;

-- Admin role: bypasses RLS for cross-tenant ops (governance, GDPR)
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'l9_admin') THEN
        CREATE ROLE l9_admin NOLOGIN BYPASSRLS;
    END IF;
END $$;

GRANT ALL ON ALL TABLES IN SCHEMA public TO l9_admin;

-- Audit role: read-only on audit log, no RLS bypass
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'l9_auditor') THEN
        CREATE ROLE l9_auditor NOLOGIN;
    END IF;
END $$;

GRANT SELECT ON packet_audit_log TO l9_auditor;

-- ════════════════════════════════════════════════════════════════
--  FUNCTIONS
-- ════════════════════════════════════════════════════════════════

-- Idempotent insert: checks content_hash+tenant, returns existing if dup
CREATE OR REPLACE FUNCTION insert_packet_idempotent(p_envelope JSONB)
RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE
    v_id UUID;
    v_hash TEXT;
    v_tenant TEXT;
BEGIN
    v_hash   := p_envelope->>'content_hash';
    v_tenant := p_envelope->'tenant'->>'actor';

    SELECT packet_id INTO v_id
    FROM packet_store
    WHERE content_hash = v_hash AND actor_tenant = v_tenant;

    IF v_id IS NOT NULL THEN
        INSERT INTO packet_audit_log (packet_id, tenant, action, actor, detail)
        VALUES (v_id, v_tenant, 'DEDUP_SKIP', p_envelope->'address'->>'source_node', 'Duplicate content hash');
        RETURN v_id;
    END IF;

    INSERT INTO packet_store (
        packet_id, packet_type, action, schema_version,
        source_node, destination_node, reply_to,
        actor_tenant, on_behalf_of, originator_tenant, org_id, user_id,
        envelope, content_hash, hash_algorithm, signature, signing_key_id,
        classification, encryption_status,
        trace_id, span_id, correlation_id,
        parent_ids, root_id, generation, derivation_type,
        intent, compliance_tags, retention_days,
        redaction_applied, audit_required, data_subject_id,
        tags, ttl
    ) VALUES (
        (p_envelope->>'packet_id')::UUID,
        p_envelope->>'packet_type',
        p_envelope->>'action',
        COALESCE(p_envelope->>'schema_version', '3.0.0'),
        p_envelope->'address'->>'source_node',
        p_envelope->'address'->>'destination_node',
        p_envelope->'address'->>'reply_to',
        p_envelope->'tenant'->>'actor',
        p_envelope->'tenant'->>'on_behalf_of',
        COALESCE(p_envelope->'tenant'->>'originator', p_envelope->'tenant'->>'actor'),
        p_envelope->'tenant'->>'org_id',
        p_envelope->'tenant'->>'user_id',
        p_envelope,
        v_hash,
        COALESCE(p_envelope->'security'->>'hash_algorithm', 'sha256'),
        p_envelope->'security'->>'signature',
        p_envelope->'security'->>'signing_key_id',
        COALESCE(p_envelope->'security'->>'classification', 'internal'),
        COALESCE(p_envelope->'security'->>'encryption_status', 'plaintext'),
        p_envelope->'observability'->>'trace_id',
        p_envelope->'observability'->>'span_id',
        p_envelope->'observability'->>'correlation_id',
        COALESCE(
            (SELECT array_agg(elem::UUID) FROM jsonb_array_elements_text(p_envelope->'lineage'->'parent_ids') AS elem),
            '{}'
        ),
        (p_envelope->'lineage'->>'root_id')::UUID,
        COALESCE((p_envelope->'lineage'->>'generation')::INT, 0),
        p_envelope->'lineage'->>'derivation_type',
        p_envelope->'governance'->>'intent',
        COALESCE(
            (SELECT array_agg(elem) FROM jsonb_array_elements_text(p_envelope->'governance'->'compliance_tags') AS elem),
            '{}'
        ),
        (p_envelope->'governance'->>'retention_days')::INT,
        COALESCE((p_envelope->'governance'->>'redaction_applied')::BOOLEAN, FALSE),
        COALESCE((p_envelope->'governance'->>'audit_required')::BOOLEAN, FALSE),
        p_envelope->'governance'->>'data_subject_id',
        COALESCE(
            (SELECT array_agg(elem) FROM jsonb_array_elements_text(p_envelope->'tags') AS elem),
            '{}'
        ),
        (p_envelope->>'ttl')::TIMESTAMPTZ
    )
    RETURNING packet_id INTO v_id;

    -- auto-populate lineage_graph
    INSERT INTO lineage_graph (parent_id, child_id, generation, derivation_type)
    SELECT unnest(COALESCE(
        (SELECT array_agg(elem::UUID) FROM jsonb_array_elements_text(p_envelope->'lineage'->'parent_ids') AS elem),
        '{}'::UUID[]
    )), v_id,
    COALESCE((p_envelope->'lineage'->>'generation')::INT, 0),
    p_envelope->'lineage'->>'derivation_type';

    -- auto-populate hop_trace
    INSERT INTO hop_trace (packet_id, node_id, action, entered_at, exited_at, status, signature, seq)
    SELECT v_id,
           elem->>'node_id', elem->>'action',
           (elem->>'entered_at')::TIMESTAMPTZ,
           (elem->>'exited_at')::TIMESTAMPTZ,
           elem->>'status', elem->>'signature',
           (row_number() OVER ())::INT
    FROM jsonb_array_elements(COALESCE(p_envelope->'hop_trace', '[]'::JSONB)) AS elem;

    -- auto-populate delegation_chain
    INSERT INTO delegation_chain (packet_id, delegator, delegatee, scope, granted_at, expires_at, proof_hash, seq)
    SELECT v_id,
           elem->>'delegator', elem->>'delegatee',
           (SELECT array_agg(s) FROM jsonb_array_elements_text(elem->'scope') AS s),
           (elem->>'granted_at')::TIMESTAMPTZ,
           (elem->>'expires_at')::TIMESTAMPTZ,
           elem->>'proof_hash',
           (row_number() OVER ())::INT
    FROM jsonb_array_elements(COALESCE(p_envelope->'delegation_chain', '[]'::JSONB)) AS elem;

    -- audit log
    INSERT INTO packet_audit_log (packet_id, tenant, action, actor)
    VALUES (v_id, v_tenant, 'INSERT', p_envelope->'address'->>'source_node');

    RETURN v_id;
END;
$$;

-- GDPR right-to-delete: removes all packets for a data subject
CREATE OR REPLACE FUNCTION gdpr_erase_subject(p_subject_id TEXT, p_performed_by TEXT)
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
    v_count INT;
BEGIN
    -- Log before delete (audit survives)
    INSERT INTO packet_audit_log (packet_id, tenant, action, actor, detail, metadata)
    SELECT packet_id, actor_tenant, 'GDPR_DELETE', p_performed_by,
           'Right to erasure request',
           jsonb_build_object('data_subject_id', p_subject_id, 'reason', 'right_to_erasure')
    FROM packet_store WHERE data_subject_id = p_subject_id;

    DELETE FROM packet_store WHERE data_subject_id = p_subject_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- TTL pruning
CREATE OR REPLACE FUNCTION prune_expired_packets()
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE v_count INT;
BEGIN
    INSERT INTO packet_audit_log (packet_id, tenant, action, actor, detail)
    SELECT packet_id, actor_tenant, 'TTL_PRUNE', 'system', 'Expired packet pruned'
    FROM packet_store WHERE ttl < now();

    DELETE FROM packet_store WHERE ttl < now();
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- Lineage walk: all ancestors of a packet
CREATE OR REPLACE FUNCTION get_ancestry(p_packet_id UUID)
RETURNS TABLE(packet_id UUID, generation INT, derivation_type TEXT) LANGUAGE SQL AS $$
    WITH RECURSIVE ancestors AS (
        SELECT parent_id AS packet_id, lg.generation, lg.derivation_type
        FROM lineage_graph lg WHERE lg.child_id = p_packet_id
        UNION ALL
        SELECT lg.parent_id, lg.generation, lg.derivation_type
        FROM lineage_graph lg JOIN ancestors a ON lg.child_id = a.packet_id
    )
    SELECT * FROM ancestors;
$$;

-- Lineage walk: all descendants of a packet
CREATE OR REPLACE FUNCTION get_descendants(p_packet_id UUID)
RETURNS TABLE(packet_id UUID, generation INT, derivation_type TEXT) LANGUAGE SQL AS $$
    WITH RECURSIVE descendants AS (
        SELECT child_id AS packet_id, lg.generation, lg.derivation_type
        FROM lineage_graph lg WHERE lg.parent_id = p_packet_id
        UNION ALL
        SELECT lg.child_id, lg.generation, lg.derivation_type
        FROM lineage_graph lg JOIN descendants d ON lg.parent_id = d.packet_id
    )
    SELECT * FROM descendants;
$$;
