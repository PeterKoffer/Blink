# Blink — Frontend Integration (Sprint 6)

This doc describes how to wire the single-file prototype (`kidschat_demo.py`) to
the real backend. The prototype lives in the memory system as `/home/mac/kidschat_demo.py`;
the backend lives in this repo.

The backend and frontend are **separate processes** and remain that way. The
prototype serves HTML/JS on port 8765; the backend (FastAPI) serves the API on
its own port (default 8000).

## What changed in Sprint 6 (backend-side)

- **CORS middleware** — allows the prototype (localhost:8765) to call the API.
  Controlled by `CORS_ORIGINS` env var (comma-separated).
- **Dev auth bypass** — in dev env with `BLINK_DEV_BYPASS_AUTH=true`, the
  backend accepts `X-Dev-User-Id: <uuid>` instead of a Supabase JWT. Lets the
  prototype skip a real OIDC flow during integration.
- **Rate limits** — on create-request, create-group, join, invite, create-message,
  media upload-url + confirm. Fixed-window per-user.
- **/metrics** — Prometheus text format. **/readyz** — checks DB.
- **Structured logging** — one JSON line per request.

## Dev setup (end-to-end)

1. **Backend**

   ```bash
   cd /home/mac/blink
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   cp .env.example .env.dev
   ```

   Edit `.env.dev`:
   ```
   BLINK_ENV=dev
   BLINK_DEV_BYPASS_AUTH=true
   DATABASE_URL=postgresql://...
   CORS_ORIGINS=http://localhost:8765
   # Supabase fields can be placeholders in dev bypass mode
   SUPABASE_JWT_SECRET=dev
   SUPABASE_JWT_ISSUER=dev
   ```

   Run migrations, then:
   ```bash
   python scripts/run_migrations.py
   uvicorn blink.api.app:app --reload --port 8000
   ```

2. **Seed test users** (dev DB, manual SQL):

   ```sql
   INSERT INTO users (id, type, status, display_name)
   VALUES ('11111111-1111-1111-1111-111111111111', 'child', 'active', 'Sofie');

   INSERT INTO users (id, type, status, display_name)
   VALUES ('22222222-2222-2222-2222-222222222222', 'parent', 'active', 'Mor');

   INSERT INTO parent_accounts (id, user_id, display_name, contact_email_or_phone, verified)
   VALUES ('22222222-2222-2222-2222-222222222223',
           '22222222-2222-2222-2222-222222222222',
           'Mor', 'mor@example.dk', true);

   INSERT INTO child_parent_links (child_user_id, parent_account_id, status, activated_at)
   VALUES ('11111111-1111-1111-1111-111111111111',
           '22222222-2222-2222-2222-222222222223',
           'active', now());
   ```

3. **Prototype** — run kidschat_demo.py on port 8765 as usual.

## Wiring the API client

Drop `frontend/blink_api_client.js` into the prototype's HTML. Inside the
existing `<script>` block, instantiate at the top:

```js
const api = new BlinkAPI({
  baseUrl: "http://localhost:8000",
  devUserId: "11111111-1111-1111-1111-111111111111",  // Sofie in child mode
});

// When switching to parent mode, rebuild with the parent's uuid:
// api.devUserId = "22222222-2222-2222-2222-222222222222";
```

### Flow mapping

| Prototype mock state              | Real backend call                                      |
|-----------------------------------|--------------------------------------------------------|
| `renderGroups()` reads `groups[]` | `api.groups.list()` → GroupView[]                      |
| `handleCreateGroup()`             | `api.groups.create({name, initialMemberIds})`          |
| `handleJoinGroup(code)`           | `api.groups.join({inviteCode: code})`                  |
| `renderFriends()` reads `friends[]` | `api.friends.list()`                                 |
| `sendTextMessage()`               | `api.messages.createText({groupId, text, clientMessageId, ttlSeconds})` |
| `sendPhoto()`                     | `api.media.upload({file, groupId, mime, ...})` then `api.messages.createImage(...)` |
| `renderParentPending()`           | `api.parent.pending()`                                 |
| Approve/decline buttons           | `api.parent.approveGroup(id)` etc.                     |
| Parent billing panel              | `api.parent.billing(groupId)` → summary                |

Image fetch in chat:
```js
const { url } = await api.media.getReadUrl(mediaId);
imgEl.src = url;  // signed URL, 60s TTL
```

## Error handling

`BlinkAPIError` carries a typed `code` + `details` body. Map common ones:

```js
try { await api.groups.create(body); }
catch (e) {
  if (e instanceof BlinkAPIError) {
    switch (e.code) {
      case "upgrade_required":
        // e.details: currentTier, requiredTier, currentMemberCount, currentCap
        showUpgradeCta(e.details);
        break;
      case "hard_cap_exceeded":
        showBlockingModal("Gruppen kan ikke have mere end 50 medlemmer");
        break;
      case "policy_blocked":
        showParentMessage(`Din voksne har slået "${e.details.policyKey}" fra`);
        break;
      case "rate_limited":
        showToast(`Prøv igen om ${e.details.retryAfterSeconds} sek`);
        break;
      case "unsupported":
        showErr(`Ikke muligt i v1: ${e.details.feature}`);
        break;
      default:
        showGenericError(e.message);
    }
  }
}
```

## UI states that must exist (spec del 4)

- **Pending create-group** — render with the grayscale pending style (already
  in prototype). Respond to approve via refresh.
- **Policy blocked** — parent-readable message referencing `policyKey`.
- **Upgrade required** — parent sees `requiredTier` + CTA; child sees
  "gruppen er fuld, din voksne kan åbne plads til flere".
- **Hard cap** — child: "gruppen har nået max størrelse"; parent: "Blink-grupper
  kan have op til 50 medlemmer".
- **Upload failed** — retry toast, re-enable send button.
- **Confirm failed** — same.
- **Message send failed** — re-enable send, keep text in input.
- **Approve/decline success** — remove row, toast.
- **Activate/upgrade success** — parent billing panel updates tier/cap.

## Manual verification checklist

Run both servers. For each row, perform the action in the browser and check
what the backend logs show (or rows in DB).

| # | Flow                                  | Backend evidence                                     |
|---|---------------------------------------|------------------------------------------------------|
| 1 | Open prototype, switch to child       | GET /groups 200 in logs                              |
| 2 | Create small group (5 friends)        | POST /groups 201; row in `groups`, billing trigger fires |
| 3 | Create 11-member group → blocked      | POST /groups 409 `upgrade_required` with `requiredTier=normal` |
| 4 | Invite a friend                       | POST /groups/{id}/invite 200; pending row in `group_memberships` |
| 5 | Switch to parent, approve group       | POST /parent/requests/group/{id}/approve 200; group status→active |
| 6 | Send text message                     | POST /messages 200; row in `messages`; counter `blink_messages_created_total{type="text"}` increments |
| 7 | Send image (upload → confirm → msg)   | POST /media/upload-url 200; PUT to R2; POST /media/confirm 200; POST /messages 200; `usage_status='attached'` |
| 8 | Open image (fetch read url)           | GET /media/{id}/url 200; URL loads in browser        |
| 9 | Wait past TTL                         | `run_expiration.py` flips message status; counter `blink_messages_expired_total` increments |
| 10 | Parent billing view                  | GET /parent/groups/{id}/billing 200 with current_cap |
| 11 | Activate at normal tier              | POST /parent/groups/{id}/activate 200; billing_state.status=active |
| 12 | Hit rate limit (send 61 messages in a minute) | 429 `rate_limited` with Retry-After header  |
| 13 | /metrics endpoint                    | curl returns Prometheus text with all counters       |
| 14 | /readyz                              | 200 "ready" when DB is up; 503 when pool down       |

## What is NOT wired in Sprint 6

- Real OIDC login — dev bypass only. Sprint 7+ when Supabase Auth is real.
- Automatic prototype rewrite — this doc + the JS client make it possible,
  but the 2700-line kidschat_demo.py is not yet modified. Recommended approach:
  do it section by section, starting with `renderGroups()` and `renderPending()`,
  behind a `USE_BACKEND` flag so mock and real can coexist during migration.
- Direct chats — backend still has no `chats` table; prototype's direct chat
  section stays fully mocked. Future migration adds `chats` table + FK on
  `messages.chat_id` + routes.
- Stripe/Paddle — billing endpoints are product-logic only; no payment capture.
