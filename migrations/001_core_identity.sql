-- Blink v1 — migration 001: core identity
-- users, parent_accounts, child_parent_links
--
-- Design notes:
-- - Every actor in Blink is a row in `users`. Children and parents share the
--   base table so foreign keys from other tables can be unified.
-- - `users.auth_user_id` optionally references Supabase's auth.users. It's
--   nullable because a child may be onboarded by a parent before the child
--   has their own sign-in credentials (parent controls early onboarding).
-- - `parent_accounts` carries the verified-adult data. One parent_account
--   per user_id (1:1 with users of type='parent').
-- - `child_parent_links` is many-to-many: a child can have multiple
--   guardians, a parent can oversee multiple children.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid

-- --- Enums ---

CREATE TYPE user_type AS ENUM ('child', 'parent', 'pending');
CREATE TYPE user_status AS ENUM ('pending_activation', 'active', 'suspended', 'deactivated');
CREATE TYPE link_status AS ENUM ('pending', 'active', 'revoked');

-- --- users ---
-- Base table for every person in the system.

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type            user_type NOT NULL,
    status          user_status NOT NULL DEFAULT 'active',
    display_name    text,
    avatar_initial  char(1),
    auth_user_id    uuid UNIQUE,  -- Supabase auth.users.id — null for children without own login
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT users_display_name_len CHECK (
        display_name IS NULL OR (char_length(display_name) BETWEEN 1 AND 40)
    )
);

CREATE INDEX idx_users_type_status ON users (type, status);
CREATE INDEX idx_users_auth_user_id ON users (auth_user_id) WHERE auth_user_id IS NOT NULL;

-- --- parent_accounts ---
-- Adult-verified account data. Payment, contact, and policy attachment go here.

CREATE TABLE parent_accounts (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    display_name             text NOT NULL,
    contact_email_or_phone   text NOT NULL,
    verified                 boolean NOT NULL DEFAULT false,
    created_at               timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT parent_accounts_display_name_len CHECK (char_length(display_name) BETWEEN 1 AND 80),
    CONSTRAINT parent_accounts_contact_len CHECK (char_length(contact_email_or_phone) BETWEEN 3 AND 200)
);

CREATE INDEX idx_parent_accounts_contact ON parent_accounts (contact_email_or_phone);
CREATE INDEX idx_parent_accounts_verified ON parent_accounts (verified) WHERE verified = true;

-- --- child_parent_links ---
-- Many-to-many linking children to parent accounts. A child cannot act without
-- at least one ACTIVE link; authz helpers enforce this.

CREATE TABLE child_parent_links (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    child_user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_account_id   uuid NOT NULL REFERENCES parent_accounts(id) ON DELETE CASCADE,
    relation_type       text,        -- free-form for now: "parent", "guardian", "step-parent", ...
    status              link_status NOT NULL DEFAULT 'pending',
    created_at          timestamptz NOT NULL DEFAULT now(),
    activated_at        timestamptz,

    CONSTRAINT cpl_unique_pair UNIQUE (child_user_id, parent_account_id),
    CONSTRAINT cpl_activated_when_active CHECK (
        (status = 'active' AND activated_at IS NOT NULL)
        OR (status <> 'active')
    )
);

CREATE INDEX idx_cpl_child_active   ON child_parent_links (child_user_id)     WHERE status = 'active';
CREATE INDEX idx_cpl_parent_active  ON child_parent_links (parent_account_id) WHERE status = 'active';
CREATE INDEX idx_cpl_status         ON child_parent_links (status);

COMMIT;
