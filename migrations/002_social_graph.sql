-- Blink v1 — migration 002: social graph
-- friendships, friend_requests
--
-- Design notes:
-- - Friendships are symmetric but we canonicalize ordering to avoid duplicates:
--   child_user_id_a < child_user_id_b (enforced by CHECK).
-- - friend_requests carry direction (requester -> target). Parent approval is
--   tracked on the request row; on approval, a friendships row is created.
-- - Only one non-terminal request is allowed between any ordered pair to
--   prevent spam. Terminal statuses (approved/declined/canceled) can coexist
--   historically, but a new request cannot be opened while one is pending.

BEGIN;

CREATE TYPE friendship_status AS ENUM ('active', 'blocked', 'removed');
CREATE TYPE friend_request_status AS ENUM (
    'pending_parent',
    'approved',
    'declined',
    'canceled'
);

-- --- friendships ---
-- Symmetric edge; canonical ordering prevents duplicate rows.

CREATE TABLE friendships (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    child_user_id_a     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    child_user_id_b     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status              friendship_status NOT NULL DEFAULT 'active',
    created_at          timestamptz NOT NULL DEFAULT now(),
    approved_at         timestamptz NOT NULL,

    CONSTRAINT friendships_distinct CHECK (child_user_id_a <> child_user_id_b),
    CONSTRAINT friendships_canonical_order CHECK (child_user_id_a < child_user_id_b),
    CONSTRAINT friendships_unique_pair UNIQUE (child_user_id_a, child_user_id_b)
);

CREATE INDEX idx_friendships_a_active ON friendships (child_user_id_a) WHERE status = 'active';
CREATE INDEX idx_friendships_b_active ON friendships (child_user_id_b) WHERE status = 'active';

-- --- friend_requests ---
-- Directed. One pending request per requester-target ordered pair at a time.

CREATE TABLE friend_requests (
    id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_child_id              uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_child_id                 uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status                          friend_request_status NOT NULL DEFAULT 'pending_parent',
    method                          text,         -- 'qr' | 'code' | future values; checked in app layer
    created_at                      timestamptz NOT NULL DEFAULT now(),
    reviewed_at                     timestamptz,
    reviewed_by_parent_account_id   uuid REFERENCES parent_accounts(id) ON DELETE SET NULL,

    CONSTRAINT friend_req_distinct CHECK (requester_child_id <> target_child_id),
    CONSTRAINT friend_req_reviewed_consistency CHECK (
        (status IN ('approved', 'declined') AND reviewed_at IS NOT NULL)
        OR (status IN ('pending_parent', 'canceled'))
    )
);

-- Only one active request per directed pair (pending_parent blocks new ones).
CREATE UNIQUE INDEX idx_friend_req_one_pending
    ON friend_requests (requester_child_id, target_child_id)
    WHERE status = 'pending_parent';

CREATE INDEX idx_friend_req_target_pending ON friend_requests (target_child_id)    WHERE status = 'pending_parent';
CREATE INDEX idx_friend_req_requester      ON friend_requests (requester_child_id);

COMMIT;
