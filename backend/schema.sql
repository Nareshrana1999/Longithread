-- Longithread - illustrative starting schema.
-- The app now enforces, in the data/API layer: tenant isolation, consent records
-- gating per-patient processing, and a hash-chained (tamper-evident) audit trail.
-- Production hardening still required: DB-level RLS policies, revoke-only append
-- grants on audit_events, retention policy, and migration tooling.
-- Enforce tenant isolation at the database AND API layers, never only in the UI.

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email TEXT NOT NULL,
    role TEXT NOT NULL,               -- clinician | coordinator | admin
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    external_ref TEXT,
    condition TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_patients_tenant ON patients(tenant_id);

CREATE TABLE IF NOT EXISTS source_documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    document_type TEXT NOT NULL,       -- lab_report | discharge_summary | prescription | scanned_lab
    storage_key TEXT NOT NULL,
    content_hash TEXT NOT NULL,        -- de-duplication
    is_quarantined BOOLEAN NOT NULL DEFAULT FALSE, -- prompt-injection / untrusted text
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_docs_tenant ON source_documents(tenant_id);
CREATE INDEX IF NOT EXISTS ix_docs_patient ON source_documents(patient_id);

CREATE TABLE IF NOT EXISTS clinical_observations (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    source_document_id UUID,
    code TEXT NOT NULL,                -- normalized terminology code (LOINC-ish)
    value_numeric DOUBLE PRECISION,
    value_text TEXT,
    unit TEXT,
    observed_at TIMESTAMPTZ,
    extraction_status TEXT NOT NULL,   -- extracted | validated | flagged | rejected
    conflict_with UUID,                -- pointer to contradicting observation
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_obs_tenant ON clinical_observations(tenant_id);
CREATE INDEX IF NOT EXISTS ix_obs_patient ON clinical_observations(patient_id);

CREATE TABLE IF NOT EXISTS follow_up_tasks (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    rule_id TEXT NOT NULL,             -- versioned, clinician-approved rule identifier
    rule_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending | accepted | edited | rejected | done
    due_at TIMESTAMPTZ,
    reviewed_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_tasks_tenant ON follow_up_tasks(tenant_id);

-- Tamper-evident, append-only audit trail. Never UPDATE or DELETE rows here.
-- content_hash commits to this event's fields + prev_hash (the previous event's
-- content_hash in the same tenant), so edits/deletions/reordering are detectable.
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    seq BIGINT NOT NULL,               -- monotonic within a tenant
    actor_id UUID,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    detail JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    content_hash TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    UNIQUE (tenant_id, seq)
);
CREATE INDEX IF NOT EXISTS ix_audit_tenant_seq ON audit_events(tenant_id, seq);

-- Consent / lawful-basis history. Append-only: the latest row per
-- (tenant, patient, purpose) sets state (granted true/false).
CREATE TABLE IF NOT EXISTS consent_records (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    purpose TEXT NOT NULL,             -- e.g. record_processing
    basis TEXT NOT NULL,               -- e.g. explicit_consent | revoked_by_patient
    granted BOOLEAN NOT NULL,
    recorded_by UUID,
    recorded_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_consent_tenant ON consent_records(tenant_id);
CREATE INDEX IF NOT EXISTS ix_consent_patient ON consent_records(patient_id);
