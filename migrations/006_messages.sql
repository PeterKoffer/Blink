-- Blink v1 — migration 006: messages
-- messages table + enums + constraints + indexes
--
-- Design notes:
-- - Exactly one of group_id or chat_id is set. There is no chats table yet
--   (direct chats are not backend-modeled in v1); chat_id exists as a nullable
--   column with a CHECK constraint, ready for a future migration to add the
--   chats table and a FK. Sprint 3 API only populates group_id.
-- - media_id is a nullable placeholder for Sprint 4. Once the media table
--   exists, a later migration adds the FK.
-- - Three enums:
--     message_type:   text | image  (API accepts only 'text' in Sprint 3)
--     ephemeral_mode: timer | after_read  (DB allows both; API rejects
--                                          'after_read' explicitly per
--                                          project_blink_messages.md v1)
--     message_status: active | expired | deleted
-- - Idempotency: UNIQUE(sender_id, client_message_id). Scoped globally per
--   sender to match project_blink_messages.md — simpler than chat-scoped
--   and still catches client retries.
-- - CHECK (type='text' ⇒ text non-null ∧ media null ∧ 1..2000 chars): DB is
--   a safety net. API enforces tighter bounds (1..1000).
-- - Partial indexes on WHERE status='active' — the vast majority of reads
--   target active messages, and expired ones will be many after the engine runs.

BEGIN;

CREATE TYPE message_type AS ENUM ('text', 'image');
CREATE TYPE ephemeral_mode AS ENUM ('timer', 'after_read');
CREATE TYPE message_status AS ENUM ('active', 'expired', 'deleted');

CREATE TABLE messages (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id            uuid REFERENCES groups(id) ON DELETE CASCADE,
    chat_id             uuid,  -- no FK yet; chats table does not exist in v1
    type                message_type NOT NULL,
    text_content        text,
    media_id            uuid,  -- FK added in Sprint 4 migration
    client_message_id   text NOT NULL,
    ephemeral_mode      ephemeral_mode NOT NULL,
    ttl_seconds         integer NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    status              message_status NOT NULL DEFAULT 'active',

    CONSTRAINT msg_scope_exactly_one CHECK (
        (group_id IS NOT NULL AND chat_id IS NULL)
        OR (group_id IS NULL AND chat_id IS NOT NULL)
    ),
    CONSTRAINT msg_text_shape CHECK (
        type <> 'text'
        OR (
            text_content IS NOT NULL
            AND media_id IS NULL
            AND char_length(text_content) BETWEEN 1 AND 2000
        )
    ),
    CONSTRAINT msg_image_shape CHECK (
        type <> 'image'
        OR (text_content IS NULL AND media_id IS NOT NULL)
    ),
    CONSTRAINT msg_ttl_range CHECK (ttl_seconds BETWEEN 1 AND 604800),
    CONSTRAINT msg_client_id_len CHECK (char_length(client_message_id) BETWEEN 1 AND 100),
    CONSTRAINT msg_expires_after_created CHECK (expires_at > created_at)
);

-- Idempotency (per sender, across all scopes — matches project_blink_messages.md)
CREATE UNIQUE INDEX idx_messages_idempotency
    ON messages (sender_id, client_message_id);

-- Listing active messages in a group, newest first
CREATE INDEX idx_messages_group_active
    ON messages (group_id, created_at DESC)
    WHERE status = 'active' AND group_id IS NOT NULL;

-- Listing active messages in a direct chat (populated in later sprint)
CREATE INDEX idx_messages_chat_active
    ON messages (chat_id, created_at DESC)
    WHERE status = 'active' AND chat_id IS NOT NULL;

-- Expiration scan — the expiration job targets this
CREATE INDEX idx_messages_active_expires
    ON messages (expires_at)
    WHERE status = 'active';

COMMIT;
