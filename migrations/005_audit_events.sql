-- Blink v1 — migration 005: audit events
-- audit_events — append-only log of notable actions for compliance, debugging,
-- and the parent-facing "activity" surfaces (later).
--
-- Design notes:
-- - One of actor_user_id or actor_parent_account_id is typically set; both
--   can be null for system-generated events (e.g. scheduled expirations).
-- - target_type / target_id reference rows in various tables; kept as opaque
--   strings rather than FKs so we can log events for soft-deleted rows.
-- - `payload` is JSONB; event-type-specific fields live inside. Keep top-level
--   table stable, evolve shapes in payload.
-- - No DELETE expected; audit grows forever or is partitioned later.

BEGIN;

CREATE TABLE audit_events (
    id                         bigserial PRIMARY KEY,
    event_type                 text NOT NULL,
    actor_user_id              uuid REFERENCES users(id) ON DELETE SET NULL,
    actor_parent_account_id    uuid REFERENCES parent_accounts(id) ON DELETE SET NULL,
    target_type                text,
    target_id                  text,
    payload                    jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at                 timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT audit_event_type_len CHECK (char_length(event_type) BETWEEN 1 AND 80)
);

CREATE INDEX idx_audit_created_at      ON audit_events (created_at DESC);
CREATE INDEX idx_audit_event_type      ON audit_events (event_type, created_at DESC);
CREATE INDEX idx_audit_actor_user      ON audit_events (actor_user_id, created_at DESC) WHERE actor_user_id IS NOT NULL;
CREATE INDEX idx_audit_actor_parent    ON audit_events (actor_parent_account_id, created_at DESC) WHERE actor_parent_account_id IS NOT NULL;
CREATE INDEX idx_audit_target          ON audit_events (target_type, target_id) WHERE target_type IS NOT NULL;

COMMIT;
