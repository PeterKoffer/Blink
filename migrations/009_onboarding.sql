-- Blink v1 — migration 009: onboarding + adult verification
-- Extend users with child-profile fields. Add parent_invites and
-- consent_records tables for the v1 verification flow described in
-- project_blink_adult_verification.md.
--
-- Design notes:
-- - `avatar_initial` (from migration 001) stays as a simple fallback.
--   New fields give richer avatar data:
--     avatar_type: emoji | icon | shape | initial
--     avatar_value: free-text (1..20 chars) — UI provides a fixed picker
--     avatar_color: #RRGGBB hex
-- - `blink_code` is the child's shareable code (BLINK-XXXXXX, unambiguous
--   alphabet). UNIQUE partial index so existing seed users (no code) remain
--   valid.
-- - `onboarding_status` tracks the phase-transitions in the v1 flow.
--   Existing active users get backfilled to 'active'.
-- - parent_invites carries one pending invite per child. OTP is stored as
--   sha256 hash — not plaintext. Attempts counter bounds brute force.
-- - consent_records captures what was accepted and when, for audit.
--   One active consent per (parent, child, type, version); new versions
--   create new rows.

BEGIN;

-- --- enums ---
CREATE TYPE avatar_type AS ENUM ('emoji', 'icon', 'shape', 'initial');
CREATE TYPE onboarding_status AS ENUM (
    'profile_pending',
    'parent_invited',
    'parent_verified',
    'active',
    'declined'
);
CREATE TYPE parent_invite_status AS ENUM (
    'pending',
    'verified',
    'approved',
    'declined',
    'expired'
);

-- --- users: extend with child-profile columns ---
ALTER TABLE users
    ADD COLUMN avatar_type       avatar_type,
    ADD COLUMN avatar_value      text,
    ADD COLUMN avatar_color      text,
    ADD COLUMN blink_code        text,
    ADD COLUMN onboarding_status onboarding_status;

ALTER TABLE users
    ADD CONSTRAINT users_avatar_color_format CHECK (
        avatar_color IS NULL OR avatar_color ~ '^#[0-9a-fA-F]{6}$'
    ),
    ADD CONSTRAINT users_avatar_value_len CHECK (
        avatar_value IS NULL OR char_length(avatar_value) BETWEEN 1 AND 20
    ),
    ADD CONSTRAINT users_blink_code_format CHECK (
        blink_code IS NULL OR blink_code ~ '^BLINK-[A-Z2-9]{6}$'
    );

CREATE UNIQUE INDEX idx_users_blink_code
    ON users (blink_code)
    WHERE blink_code IS NOT NULL;

CREATE INDEX idx_users_onboarding_status
    ON users (onboarding_status)
    WHERE onboarding_status IS NOT NULL;

-- Backfill: anyone already active gets onboarding_status=active.
UPDATE users SET onboarding_status = 'active'::onboarding_status
 WHERE status = 'active' AND onboarding_status IS NULL;

-- --- parent_invites ---
CREATE TABLE parent_invites (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    child_user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_email_or_phone  text NOT NULL,
    invite_token            text NOT NULL UNIQUE,
    otp_code_hash           text NOT NULL,
    otp_attempts            integer NOT NULL DEFAULT 0,
    status                  parent_invite_status NOT NULL DEFAULT 'pending',
    created_at              timestamptz NOT NULL DEFAULT now(),
    verified_at             timestamptz,
    approved_at             timestamptz,
    expires_at              timestamptz NOT NULL,

    CONSTRAINT pi_contact_len CHECK (char_length(contact_email_or_phone) BETWEEN 3 AND 200),
    CONSTRAINT pi_token_len CHECK (char_length(invite_token) BETWEEN 20 AND 128),
    CONSTRAINT pi_attempts_bound CHECK (otp_attempts BETWEEN 0 AND 20),
    CONSTRAINT pi_expiry_future CHECK (expires_at > created_at),
    CONSTRAINT pi_verified_consistency CHECK (
        status IN ('pending')
        OR (status IN ('verified', 'approved') AND verified_at IS NOT NULL)
        OR status IN ('declined', 'expired')
    )
);

CREATE INDEX idx_pi_child          ON parent_invites (child_user_id);
CREATE INDEX idx_pi_status         ON parent_invites (status);
CREATE INDEX idx_pi_pending_expires ON parent_invites (expires_at)
    WHERE status = 'pending';

-- At most one pending invite per child at a time.
CREATE UNIQUE INDEX idx_pi_one_pending_per_child
    ON parent_invites (child_user_id)
    WHERE status = 'pending';

-- --- consent_records ---
CREATE TABLE consent_records (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_account_id       uuid NOT NULL REFERENCES parent_accounts(id) ON DELETE RESTRICT,
    child_user_id           uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    consent_type            text NOT NULL,
    consent_version         text NOT NULL,
    consent_text            text NOT NULL,
    accepted_at             timestamptz NOT NULL DEFAULT now(),
    ip_address              text,
    user_agent              text,
    created_at              timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT consent_type_known CHECK (
        consent_type IN ('parent_self_declaration')
    ),
    CONSTRAINT consent_version_len CHECK (char_length(consent_version) BETWEEN 1 AND 20),
    CONSTRAINT consent_text_len CHECK (char_length(consent_text) BETWEEN 10 AND 4000)
);

CREATE INDEX idx_consent_parent ON consent_records (parent_account_id, created_at DESC);
CREATE INDEX idx_consent_child  ON consent_records (child_user_id, created_at DESC);

-- One record per (parent, child, type, version) — prevents double-logging.
CREATE UNIQUE INDEX idx_consent_unique_version
    ON consent_records (parent_account_id, child_user_id, consent_type, consent_version);

COMMIT;
