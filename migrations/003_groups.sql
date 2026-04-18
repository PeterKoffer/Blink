-- Blink v1 — migration 003: groups
-- groups, group_memberships, group_requests
--
-- Design notes:
-- - `groups.status` drives child-visible state (pending_parent, active, archived).
-- - `member_cap_tier` mirrors project_blink_pricing.md — default 'lille' (up to 10).
-- - `current_plan_tier` is what the parent is currently billed for. Equal to
--   member_cap_tier once billing is in place (EPIC 12). Separated so we can
--   validate memberships against a tier while billing is being set up.
-- - Hard cap of 50 is enforced in application logic, not via DB (since tier
--   can grow). DB-level CHECK on memberships would be too rigid.
-- - `group_memberships` models both current members and historical rows
--   (status = removed/declined). Only 'active' counts toward cap.
-- - `group_requests` carries three kinds of pending actions. Pure polymorphism
--   is avoided — explicit nullable fields per kind instead of a payload blob,
--   so the DB can enforce presence via CHECKs.

BEGIN;

CREATE TYPE group_status         AS ENUM ('pending_parent', 'active', 'archived', 'deleted');
CREATE TYPE group_membership_status AS ENUM ('pending', 'active', 'declined', 'removed');
CREATE TYPE group_member_role    AS ENUM ('member', 'admin', 'creator');
CREATE TYPE group_plan_tier      AS ENUM ('lille', 'normal', 'stor');
CREATE TYPE group_request_type   AS ENUM ('create_group', 'join_group', 'invite_to_group');
CREATE TYPE group_request_status AS ENUM ('pending_parent', 'approved', 'declined', 'canceled');

-- --- groups ---

CREATE TABLE groups (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 text NOT NULL,
    created_by_child_id  uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status               group_status NOT NULL DEFAULT 'pending_parent',
    member_cap_tier      group_plan_tier NOT NULL DEFAULT 'lille',
    current_plan_tier    group_plan_tier NOT NULL DEFAULT 'lille',
    invite_code          text NOT NULL UNIQUE,  -- e.g. "GRUPPE-1247"
    created_at           timestamptz NOT NULL DEFAULT now(),
    approved_at          timestamptz,

    CONSTRAINT groups_name_len CHECK (char_length(name) BETWEEN 1 AND 40),
    CONSTRAINT groups_approved_consistency CHECK (
        (status = 'active' AND approved_at IS NOT NULL)
        OR (status <> 'active')
    ),
    CONSTRAINT groups_invite_code_format CHECK (invite_code ~ '^GRUPPE-\d{4,6}$')
);

CREATE INDEX idx_groups_creator        ON groups (created_by_child_id);
CREATE INDEX idx_groups_status         ON groups (status);
CREATE INDEX idx_groups_invite_code    ON groups (invite_code);

-- --- group_memberships ---
-- active rows only count toward member cap (enforced by app).

CREATE TABLE group_memberships (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id        uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    child_user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            group_member_role NOT NULL DEFAULT 'member',
    status          group_membership_status NOT NULL DEFAULT 'pending',
    created_at      timestamptz NOT NULL DEFAULT now(),
    activated_at    timestamptz,

    CONSTRAINT gm_unique_pair UNIQUE (group_id, child_user_id),
    CONSTRAINT gm_activated_consistency CHECK (
        (status = 'active' AND activated_at IS NOT NULL)
        OR (status <> 'active')
    )
);

CREATE INDEX idx_gm_group_active  ON group_memberships (group_id)      WHERE status = 'active';
CREATE INDEX idx_gm_child_active  ON group_memberships (child_user_id) WHERE status = 'active';
CREATE INDEX idx_gm_group_status  ON group_memberships (group_id, status);

-- --- group_requests ---
-- Three explicit kinds; each requires specific fields. CHECKs enforce shape.

CREATE TABLE group_requests (
    id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type                            group_request_type NOT NULL,
    actor_child_id                  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id                        uuid REFERENCES groups(id) ON DELETE CASCADE,
    target_child_id                 uuid REFERENCES users(id) ON DELETE CASCADE,  -- for invite_to_group
    requested_name                  text,  -- for create_group (group name being requested)
    status                          group_request_status NOT NULL DEFAULT 'pending_parent',
    created_at                      timestamptz NOT NULL DEFAULT now(),
    reviewed_at                     timestamptz,
    reviewed_by_parent_account_id   uuid REFERENCES parent_accounts(id) ON DELETE SET NULL,

    -- Shape constraints per type:
    -- create_group:     requested_name required; group_id may be set (pre-created as pending)
    -- join_group:       group_id required; target_child_id null
    -- invite_to_group:  group_id required; target_child_id required
    CONSTRAINT gr_shape_create CHECK (
        type <> 'create_group' OR (requested_name IS NOT NULL)
    ),
    CONSTRAINT gr_shape_join CHECK (
        type <> 'join_group' OR (group_id IS NOT NULL AND target_child_id IS NULL)
    ),
    CONSTRAINT gr_shape_invite CHECK (
        type <> 'invite_to_group' OR (group_id IS NOT NULL AND target_child_id IS NOT NULL)
    ),
    CONSTRAINT gr_reviewed_consistency CHECK (
        (status IN ('approved', 'declined') AND reviewed_at IS NOT NULL)
        OR (status IN ('pending_parent', 'canceled'))
    )
);

CREATE INDEX idx_gr_actor_pending  ON group_requests (actor_child_id)  WHERE status = 'pending_parent';
CREATE INDEX idx_gr_group_pending  ON group_requests (group_id)        WHERE status = 'pending_parent' AND group_id IS NOT NULL;
CREATE INDEX idx_gr_target_pending ON group_requests (target_child_id) WHERE status = 'pending_parent' AND target_child_id IS NOT NULL;
CREATE INDEX idx_gr_type_status    ON group_requests (type, status);

COMMIT;
