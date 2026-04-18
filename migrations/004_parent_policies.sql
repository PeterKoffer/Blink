-- Blink v1 — migration 004: parent policies
-- parent_policies — per-child policy rules the adult can toggle.
--
-- Design notes:
-- - One row per child. Created lazily on first parent interaction; the
--   resolver returns defaults if no row exists yet (see src/blink/policies/parent.py).
-- - `max_group_members` is capped to the v1 HARD_MAX_GROUP_MEMBERS (50) via CHECK.
-- - No parent_account_id on this table: policy follows the child, not a
--   specific parent. A child with multiple linked parents shares one policy
--   that any linked parent can edit.
-- - `updated_by_parent_account_id` tracks last editor for audit without
--   enforcing exclusive ownership.

BEGIN;

CREATE TABLE parent_policies (
    child_user_id                    uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    may_create_groups                boolean NOT NULL DEFAULT true,
    require_group_approval           boolean NOT NULL DEFAULT true,
    may_join_groups                  boolean NOT NULL DEFAULT true,
    require_group_invite_approval    boolean NOT NULL DEFAULT true,
    max_group_members                integer NOT NULL DEFAULT 20,
    may_send_images                  boolean NOT NULL DEFAULT true,

    created_at                       timestamptz NOT NULL DEFAULT now(),
    updated_at                       timestamptz NOT NULL DEFAULT now(),
    updated_by_parent_account_id     uuid REFERENCES parent_accounts(id) ON DELETE SET NULL,

    CONSTRAINT pp_max_members_range CHECK (max_group_members BETWEEN 2 AND 50)
);

-- Trigger to keep updated_at fresh on any UPDATE.
CREATE OR REPLACE FUNCTION parent_policies_touch_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER parent_policies_touch
    BEFORE UPDATE ON parent_policies
    FOR EACH ROW
    EXECUTE FUNCTION parent_policies_touch_updated_at();

COMMIT;
