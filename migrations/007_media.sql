-- Blink v1 — migration 007: media
-- media table + enums + FK from messages.media_id.
--
-- Design notes (ref project_blink_media.md):
-- - Three independent status fields. Never collapse them.
--     upload_status: upload lifecycle (pending/ready/failed)
--     access_status: product-visibility (active/expired/deleted)
--     usage_status:  has it been attached to a message yet? (unused/attached)
-- - uploader_id is the ONLY caller allowed to attach this media to a
--   message. Enforced in app layer; not a DB CHECK because the check would
--   cross tables. Ownership semantics are documented + tested.
-- - group_id/chat_id mirrors messages. Chats table does not exist yet;
--   chat_id is nullable, no FK. Future migration wires FK when chats arrive.
-- - mime whitelist enforced at DB level — tight. v1 is JPEG + WebP only.
-- - 1 MB hard max as a CHECK. API enforces the same + client-side compression.
-- - r2_key is globally unique; generated as m/YYYY/MM/DD/<uuid>.<ext>.
-- - expires_at is the physical retention boundary. Default 7 days after
--   created_at (enforced in app). R2 lifecycle rule sweeps in parallel.
-- - messages.media_id FK is added here; ON DELETE RESTRICT so we never
--   silently lose message rows if media is hard-deleted. Soft delete via
--   access_status='deleted' is the product-correct path.

BEGIN;

CREATE TYPE media_upload_status AS ENUM ('pending', 'ready', 'failed');
CREATE TYPE media_access_status AS ENUM ('active', 'expired', 'deleted');
CREATE TYPE media_usage_status  AS ENUM ('unused', 'attached');

CREATE TABLE media (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id        uuid REFERENCES groups(id) ON DELETE CASCADE,
    chat_id         uuid,  -- no FK yet; chats table does not exist in v1
    r2_key          text NOT NULL UNIQUE,
    mime            text NOT NULL,
    size_bytes      integer NOT NULL,
    width           integer,
    height          integer,
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    upload_status   media_upload_status NOT NULL DEFAULT 'pending',
    access_status   media_access_status NOT NULL DEFAULT 'active',
    usage_status    media_usage_status  NOT NULL DEFAULT 'unused',

    CONSTRAINT media_scope_exactly_one CHECK (
        (group_id IS NOT NULL AND chat_id IS NULL)
        OR (group_id IS NULL AND chat_id IS NOT NULL)
    ),
    CONSTRAINT media_size_range CHECK (size_bytes BETWEEN 1 AND 1048576),
    CONSTRAINT media_mime_whitelist CHECK (mime IN ('image/jpeg', 'image/webp')),
    CONSTRAINT media_expires_after_created CHECK (expires_at > created_at),
    CONSTRAINT media_dimensions_positive CHECK (
        (width IS NULL OR width > 0) AND (height IS NULL OR height > 0)
    )
);

CREATE INDEX idx_media_uploader          ON media (uploader_id);
CREATE INDEX idx_media_group             ON media (group_id) WHERE group_id IS NOT NULL;
CREATE INDEX idx_media_chat              ON media (chat_id)  WHERE chat_id  IS NOT NULL;
CREATE INDEX idx_media_upload_status     ON media (upload_status);
CREATE INDEX idx_media_access_status     ON media (access_status);
CREATE INDEX idx_media_active_expires    ON media (expires_at) WHERE access_status = 'active';
CREATE INDEX idx_media_usage_cleanup     ON media (access_status, created_at)
    WHERE access_status IN ('expired', 'deleted');

-- --- messages.media_id FK (deferred from migration 006) ---
ALTER TABLE messages
    ADD CONSTRAINT fk_messages_media
    FOREIGN KEY (media_id)
    REFERENCES media(id)
    ON DELETE RESTRICT;

COMMIT;
