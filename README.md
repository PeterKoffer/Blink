# Blink v1 backend

Privat gruppechat for børn. Se memory-filerne for kanoniske v1-beslutninger:
- `project_blink.md` — master spec
- `project_blink_media.md` — medie-arkitektur
- `project_blink_messages.md` — message contract
- `project_blink_pricing.md` — group pricing
- `project_blink_backlog.md` — engineering backlog

## Sprint 1 status

Denne kodebase dækker **EPIC 1–3** af backlog'en:
- Projektstruktur + env-setup
- DB schema v1 (migrations)
- Auth context + rollemodel
- Central authz-lag (deny-by-default)
- Parent policy foundation

**Ikke bygget endnu** (senere sprints): friend/group endpoints, message create, media, billing, integrationer.

## Stack

- **Python 3.11+** / **FastAPI** (async)
- **asyncpg** direkte mod Postgres (ingen ORM)
- **pydantic** / **pydantic-settings** for config og types
- **PyJWT** for Supabase Auth verification
- **Postgres** (via Supabase)
- **Raw SQL migrations** — ingen ORM-schema-magi

Hvorfor Python: matcher prototypen (`kidschat_demo.py`), asyncpg er produktions-hurtig, FastAPI giver typesikre endpoints via Pydantic.

## Kør lokalt

```bash
# 1. Virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Miljø
cp .env.example .env.dev
# udfyld DATABASE_URL og SUPABASE_JWT_SECRET

# 3. Kør migrations
python scripts/run_migrations.py

# 4. Start dev-server (Sprint 2+ når endpoints findes)
# uvicorn blink.app:app --reload
```

## Projektstruktur

```
blink/
├── migrations/              # rå SQL, versionerede fra 001_
├── scripts/run_migrations.py
└── src/blink/
    ├── config.py            # env → typed settings
    ├── db.py                # asyncpg pool
    ├── types.py             # domain enums (UserType, GroupStatus, ...)
    ├── errors.py            # AuthError, AuthzError, NotFoundError
    ├── auth/
    │   ├── context.py       # AuthContext dataclass
    │   └── resolver.py      # resolve JWT → AuthContext
    ├── authz/
    │   └── require.py       # require_* deny-by-default helpers
    └── policies/
        └── parent.py        # resolve_parent_policy + defaults
```

## Kanoniske regler (v1 — skal respekteres)

- Grupper primære, direkte chats sekundære
- Kun `timer` ephemeral mode — `after_read` afvises eksplicit
- R2 for billeder, appserver ser aldrig bytes
- PUT TTL 5 min, GET TTL 60 sek
- Media ownership + kontekst match tvunget
- `usage_status` håndhæver ingen-genbrug
- Ingen forwarding, ingen video, ingen offentlighed i v1
- Max 50 medlemmer pr. gruppe (hard cap)
