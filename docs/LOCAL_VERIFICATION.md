# Blink — Lokal verifikation (Sprint 6B → grøn)

Formål: Kør backend + prototype ende-til-ende på din egen maskine og bekræft
at de 7 flows fra checklisten er grønne. Hvis noget fejler: send logs/errors
tilbage pr. afsnittet i bunden.

Testet på macOS + Linux. Windows: brug WSL.

---

## 0. Forudsætninger

Du skal have:
- **Python 3.11+** (`python3 --version` skal vise ≥ 3.11)
- **Postgres 14+** (lokalt, Docker, eller cloud — 3 valg nedenfor)
- **git** (hvis repo skal clones)

Repoet forventes at ligge i `/home/mac/blink/` — ellers tilpas stierne.

---

## 1. Python dependencies

```bash
cd /home/mac/blink
python3 -m venv .venv
source .venv/bin/activate     # macOS/Linux
# Windows WSL: source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

**Tjek:**
```bash
python -c "import fastapi, asyncpg, uvicorn, pydantic, jwt; print('OK')"
```
Skal printe `OK`. Hvis noget fejler, kør `pip install -e ".[dev]"` igen og send
hele outputtet.

---

## 2. Postgres — vælg ÉT af de tre

### Valg A: Docker (hurtigst — anbefalet)

```bash
docker run --name blink-pg \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=blink_dev \
  -p 5432:5432 \
  -d postgres:16

# Vent 3 sekunder, så health check
sleep 3
docker exec blink-pg pg_isready -U postgres
# skal sige: accepting connections
```

DATABASE_URL bliver: `postgresql://postgres:postgres@localhost:5432/blink_dev`

### Valg B: macOS med Homebrew

```bash
brew install postgresql@16
brew services start postgresql@16
createdb blink_dev
```

DATABASE_URL: `postgresql://localhost/blink_dev`

### Valg C: Linux med apt

```bash
sudo apt-get install -y postgresql-16
sudo service postgresql start
sudo -u postgres createdb blink_dev
# Giv dit user adgang:
sudo -u postgres createuser --superuser $USER
```

DATABASE_URL: `postgresql://localhost/blink_dev`

**Tjek (alle valg):**
```bash
psql $DATABASE_URL -c "SELECT version();"
# skal vise "PostgreSQL 16.x ..."
```

---

## 3. .env-fil

```bash
cd /home/mac/blink
cat > .env <<'ENV'
BLINK_ENV=dev
BLINK_LOG_LEVEL=info
BLINK_DEV_BYPASS_AUTH=true

# Indsæt den URL du fik i trin 2 herunder:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/blink_dev

CORS_ORIGINS=http://localhost:8765

# Dev-placeholders — kræves af pydantic-settings, men ikke brugt i bypass mode
SUPABASE_JWT_SECRET=dev-placeholder-not-used
SUPABASE_JWT_ISSUER=dev
SUPABASE_JWT_AUDIENCE=authenticated

# R2 kan være tomme i denne sprint (ikke testet)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=blink-media
R2_ENDPOINT=
ENV
```

**Tjek:**
```bash
python -c "from blink.config import get_settings; s=get_settings(); print('env:', s.blink_env, '| bypass:', s.blink_dev_bypass_auth, '| cors:', s.cors_origins)"
```
Skal vise `env: dev | bypass: True | cors: http://localhost:8765`.

Hvis det fejler med "Field required": rediger .env og sørg for alle lines
ovenfor står nøjagtigt.

---

## 4. Kør migrationer

```bash
cd /home/mac/blink
python scripts/run_migrations.py
```

Forventet output:
```
Pending migrations (8):
  - 001_core_identity
  - 002_social_graph
  - 003_groups
  - 004_parent_policies
  - 005_audit_events
  - 006_messages
  - 007_media
  - 008_group_billing_state
  applying 001_core_identity ...
  applying 002_social_graph ...
  ...
Applied 8 migration(s).
```

**Tjek:**
```bash
psql $DATABASE_URL -c "\dt"
# Skal vise: users, parent_accounts, child_parent_links, friendships,
# friend_requests, groups, group_memberships, group_requests,
# parent_policies, audit_events, messages, media, group_billing_state,
# schema_migrations (14 tabeller)
```

---

## 5. Seed DEV_CHILD_ID + DEV_PARENT_ID

```bash
psql $DATABASE_URL <<'SQL'
BEGIN;

-- Sofie (barn)
INSERT INTO users (id, type, status, display_name, avatar_initial)
VALUES ('11111111-1111-1111-1111-111111111111', 'child', 'active', 'Sofie', 'S');

-- Mor (voksen bruger + parent account)
INSERT INTO users (id, type, status, display_name, avatar_initial)
VALUES ('22222222-2222-2222-2222-222222222222', 'parent', 'active', 'Mor', 'M');

INSERT INTO parent_accounts (id, user_id, display_name, contact_email_or_phone, verified)
VALUES ('22222222-2222-2222-2222-222222222223',
        '22222222-2222-2222-2222-222222222222',
        'Mor', 'mor@example.dk', true);

-- Link: Mor er linket til Sofie
INSERT INTO child_parent_links (child_user_id, parent_account_id, status, activated_at)
VALUES ('11111111-1111-1111-1111-111111111111',
        '22222222-2222-2222-2222-222222222223',
        'active', now());

COMMIT;

-- Verificér
SELECT u.display_name, u.type FROM users u;
SELECT pa.display_name FROM parent_accounts pa;
SELECT cpl.status FROM child_parent_links cpl;
SQL
```

Forventet output nederst:
```
 display_name | type
--------------+--------
 Sofie        | child
 Mor          | parent

 display_name
--------------
 Mor

 status
--------
 active
```

---

## 6. Start backend (terminal 1)

```bash
cd /home/mac/blink
source .venv/bin/activate
uvicorn blink.api.app:app --reload --port 8000
```

Forventet output (JSON pr. linje):
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxx]
INFO:     Started server process [xxxx]
INFO:     Application startup complete.
```

**Lad denne terminal køre.**

**Tjek (ny terminal):**
```bash
curl -sS http://localhost:8000/healthz
# {"status":"ok"}

curl -sS http://localhost:8000/readyz
# ready

curl -sS http://localhost:8000/metrics | head -5
# # HELP blink_http_requests_total ...
```

---

## 7. Slå USE_BACKEND=true i prototypen

```bash
# macOS:
sed -i '' 's/const USE_BACKEND = false/const USE_BACKEND = true/' /home/mac/kidschat_demo.py
# Linux:
# sed -i 's/const USE_BACKEND = false/const USE_BACKEND = true/' /home/mac/kidschat_demo.py

# Verificér:
grep "const USE_BACKEND" /home/mac/kidschat_demo.py
# skal vise: const USE_BACKEND = true;
```

---

## 8. Start prototype (terminal 2)

```bash
# Hvis en gammel prototype kører på :8765:
pkill -f "python3 /home/mac/kidschat_demo.py" || true

python3 /home/mac/kidschat_demo.py &
sleep 1
curl -sS -o /dev/null -w "prototype: %{http_code}\n" http://localhost:8765/
# prototype: 200
curl -sS -o /dev/null -w "api client: %{http_code}\n" http://localhost:8765/blink_api_client.js
# api client: 200
```

---

## 9. Smoke-test backend via curl (før browser)

Kør hver af disse og tjek status + body er fornuftig. Dette isolerer om
fejl ligger i backend eller frontend.

```bash
BASE=http://localhost:8000
CHILD="11111111-1111-1111-1111-111111111111"
PARENT="22222222-2222-2222-2222-222222222222"

# a. Tom gruppeliste (forventet: {"groups":[]})
curl -sS -H "X-Dev-User-Id: $CHILD" $BASE/groups

# b. Opret gruppe (forventet: 201, body med "group" + "pendingApproval":true)
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-Dev-User-Id: $CHILD" \
  -d '{"name":"CurlTest","initialMemberIds":[]}' \
  $BASE/groups

# c. List igen (forventet: én gruppe, status "pending_parent")
curl -sS -H "X-Dev-User-Id: $CHILD" $BASE/groups

# d. Parent pending (forventet: group_requests har én entry)
curl -sS -H "X-Dev-User-Id: $PARENT" $BASE/parent/requests/pending

# e. Approve den pending gruppe (kopier request_id fra d)
REQID=<indsæt-request-id-her>
curl -sS -X POST \
  -H "X-Dev-User-Id: $PARENT" \
  $BASE/parent/requests/group/$REQID/approve

# f. List groups igen som barn (forventet: status nu "active")
curl -sS -H "X-Dev-User-Id: $CHILD" $BASE/groups
```

Hvis a–f passerer, er backend OK og frontend er næste skridt.
Hvis nogen fejler, stop her og send outputtet.

---

## 10. Browser-test — de 7 flows

Åbn http://localhost:8765 i Chrome/Firefox. Åbn DevTools (F12) → **Console**
og **Network** tabs.

| # | Flow | Handling | Forventet |
|---|------|----------|-----------|
| 1 | Pitch | Hjemmesiden loader | Pitch-skærm viser, ingen console errors, `/blink_api_client.js` 200 i Network |
| 2 | Grupper fra backend | Tryk "Prøv barnets oplevelse" | Grupper-tab loader. Network viser `GET /groups` 200. Gruppen "CurlTest" (aktiv, fra trin 9f) vises |
| 3 | Opret gruppe | Tryk "Opret gruppe" → navn "Browser1" → "Opret" | Network: `POST /groups` 201. Success-skærm: "Afventer godkendelse". Tilbage → "Browser1" vises som pending (gråtonet med puls-prik) |
| 4 | Parent pending | Tilbage → tap "Forælder" → accept intro → dashboard | Network: `GET /parent/requests/pending` 200. Anmodninger-tab viser "Browser1" under "Vil oprette gruppe" |
| 5 | Approve group | Tryk "Godkend" på Browser1 | Network: `POST /parent/requests/group/{id}/approve` 200 → dernæst `GET /parent/requests/pending` 200 (ny fetch) → `GET /groups` 200. Toast "Godkendt". Pending-listen er tom |
| 6 | Åbn gruppe | Tilbage til barn-mode → tap "Browser1" | Chat åbner. Network: `GET /groups/{id}/messages` 200 (tom liste = ingen beskeder endnu) |
| 7 | Send tekstbesked | Skriv "Hej" → send | Network: `POST /messages` 200. Besked dukker op i chatten med backend-ID. Backend terminal logger JSON med `"path":"/messages","status":200` |

### Hvis et flow fejler

**Flow 2 (grupper loader ikke):**
- Console error "Failed to fetch" → backend kører ikke, eller CORS mangler
- Console error "CORS policy" → CORS_ORIGINS er ikke sat i .env
- Network 401 → dev bypass virker ikke — tjek `BLINK_DEV_BYPASS_AUTH=true`
- Network 403 → wrong user type (er DEV_CHILD_ID 'child' i DB?)

**Flow 3 (opret gruppe fejler):**
- 409 `upgrade_required` → du prøver at oprette med >10 members (ikke i denne test)
- 409 `hard_cap_exceeded` → samme
- 422 → request body er forkert — kopiér exact body fra Network-fanen

**Flow 5 (approve fejler):**
- 403 `authz_error` → forælder ikke linket til barnet (tjek `child_parent_links` tabel)
- 404 → request_id forkert eller allerede reviewed
- 409 → allerede godkendt

**Flow 7 (send tekst fejler):**
- 403 → Sofie er ikke aktivt medlem af gruppen (godkendelsen nåede ikke at aktivere membership — tjek `group_memberships` tabel status)
- 422 `validation_error` → tekst tom, over 1000 chars
- 429 `rate_limited` → du har sendt 61+ beskeder på under et minut

---

## 11. Hvad du skal sende retur hvis noget fejler

Kopiér og paste ALT af følgende ind i din besked:

```
1. Hvilket flow/trin der fejler (fx "Flow 5, approve group")

2. Browser console (F12 → Console):
   - ALLE røde/gule linjer, ikke kun den første
   - Inklusiv stack traces

3. Network-fanen, den fejlende request:
   - URL
   - Method
   - Status code
   - Request Headers (især Authorization / X-Dev-User-Id)
   - Request Payload (hvis POST)
   - Response body (hvis ikke tom)

4. Backend terminal (uvicorn):
   - De sidste 20 linjer, inklusiv selve fejl-linjen
   - Især linjer med "status":4xx eller "status":5xx
   - Exception traceback hvis nogen

5. DB tilstand:
   psql $DATABASE_URL -c "SELECT id, type, status, display_name FROM users;"
   psql $DATABASE_URL -c "SELECT child_user_id, parent_account_id, status FROM child_parent_links;"
   psql $DATABASE_URL -c "SELECT id, name, status, member_cap_tier FROM groups;"
   psql $DATABASE_URL -c "SELECT type, status, actor_child_id, group_id, target_child_id FROM group_requests ORDER BY created_at DESC LIMIT 5;"
   psql $DATABASE_URL -c "SELECT group_id, child_user_id, role, status FROM group_memberships ORDER BY created_at DESC LIMIT 10;"

6. (Hvis relevant) Metrics snapshot:
   curl -s http://localhost:8000/metrics | grep -E 'blink_http_requests_total|blink_upgrade_required|blink_rate_limited'
```

Med de 6 datapunkter kan jeg pin-pointe problemet uden gætteri.

---

## 12. Når alt er grønt — hvad næste?

Når flows 1–7 er grønne:
- `USE_BACKEND=true` er hermed verificeret som default-duelig
- Sprint 7 kan begynde: wire flere flows (friends list, join group, image upload)
- Alternativt: skriv backend integration tests der ikke kræver browser

Behold terminalen med uvicorn åben — når du laver frontend-ændringer, kan
prototypen retestes mod samme backend uden re-seed.

Tear down når du er færdig:
```bash
# Stop prototype
pkill -f "python3 /home/mac/kidschat_demo.py"
# Stop backend: Ctrl+C i terminal 1
# Stop Postgres (Docker)
docker stop blink-pg && docker rm blink-pg
# Eller Homebrew:
# brew services stop postgresql@16
```
