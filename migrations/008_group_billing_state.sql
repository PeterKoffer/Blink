-- Blink v1 — migration 008: group billing state + tier enforcement cleanup
-- group_billing_state + drop redundant groups.current_plan_tier.
--
-- Design notes (ref project_blink_pricing.md):
-- - Gruppen er betalende enhed. 1:1 med groups (UNIQUE group_id).
-- - Status enum: inactive | active | grace | canceled | unpaid — matches
--   the billing states discussed in the backlog. No external provider
--   is wired in this sprint; status transitions happen via our own service.
-- - `current_tier` on billing_state mirrors the 3 v1 tiers: lille/normal/stor.
--   It's the billing-side record of what the parent is subscribed at.
-- - `groups.member_cap_tier` remains as the hot-path cap reference used by
--   every join/invite/approve. activate/upgrade keep both fields in sync
--   inside one transaction.
-- - `groups.current_plan_tier` (from migration 003) is dropped as redundant:
--   billing_state.current_tier holds the same information with clearer roles.
-- - An AFTER INSERT trigger on groups auto-creates a billing_state row, so
--   every group always has a row. Existing rows are backfilled at the end.
-- - updated_at trigger reuses the function defined in migration 004.

BEGIN;

CREATE TYPE billing_status AS ENUM (
    'inactive',
    'active',
    'grace',
    'canceled',
    'unpaid'
);

CREATE TABLE group_billing_state (
    id                                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id                          uuid NOT NULL UNIQUE REFERENCES groups(id) ON DELETE CASCADE,
    status                            billing_status NOT NULL DEFAULT 'inactive',
    current_tier                      group_plan_tier NOT NULL DEFAULT 'lille',
    activated_by_parent_account_id    uuid REFERENCES parent_accounts(id) ON DELETE SET NULL,
    activated_at                      timestamptz,
    current_period_start              timestamptz,
    current_period_end                timestamptz,
    cancel_at_period_end              boolean NOT NULL DEFAULT false,
    created_at                        timestamptz NOT NULL DEFAULT now(),
    updated_at                        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT gbs_period_consistency CHECK (
        (current_period_start IS NULL AND current_period_end IS NULL)
        OR (current_period_start IS NOT NULL
            AND current_period_end IS NOT NULL
            AND current_period_end > current_period_start)
    ),
    CONSTRAINT gbs_activated_consistency CHECK (
        status <> 'inactive' OR activated_at IS NULL
    )
);

CREATE INDEX idx_gbs_status      ON group_billing_state (status);
CREATE INDEX idx_gbs_period_end  ON group_billing_state (current_period_end)
    WHERE status IN ('active', 'grace');

-- Reuse the updated_at trigger function defined in migration 004.
CREATE TRIGGER gbs_touch
    BEFORE UPDATE ON group_billing_state
    FOR EACH ROW
    EXECUTE FUNCTION parent_policies_touch_updated_at();

-- Auto-create a billing_state row whenever a new group is created.
CREATE OR REPLACE FUNCTION ensure_group_billing_state_row()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO group_billing_state (group_id) VALUES (NEW.id)
    ON CONFLICT (group_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER groups_ensure_billing
    AFTER INSERT ON groups
    FOR EACH ROW
    EXECUTE FUNCTION ensure_group_billing_state_row();

-- Backfill existing groups (pre-migration 008).
INSERT INTO group_billing_state (group_id)
SELECT id FROM groups
ON CONFLICT (group_id) DO NOTHING;

-- --- Cleanup: groups.current_plan_tier is redundant given billing_state ---
-- Safe to drop: only repos/groups.py reads it and that module is updated in
-- this sprint to no longer reference the column.
ALTER TABLE groups DROP COLUMN IF EXISTS current_plan_tier;

COMMIT;
