# radar-online: design

Technical design of the hosted, multi-user publication service decided in
[ADR 0014](adr/0014-radar-online-public-reports.md). English only, like the
other design documents. Tasks are tracked in [roadmap Section 9](roadmap.md).

## 1. Scope

radar-online lets a registered user publish, from their local Engineering
Radar, the **global score and category scores** of a repository's latest
scoring run, and serves:

- a public report page and a trends page per published repository;
- a public profile page listing a user's published repositories;
- a shields.io badge per published repository.

Out of scope for the first version: criterion scores, findings, roadmap,
repository ownership verification, open self-service sign-up, history
backfill (the online trend starts at the first upload).

## 2. Components

```
local machine                                   radar.marvinlerouge.dev
-------------                                   -----------------------
radar-dashboard  --"Upload report"-->  radar-api  --HTTPS, API key-->  radar-online API  <-- public browsers
(local mode)       preview, confirm    (payload builder,              (FastAPI + SQLite)      radar-dashboard
                                        disclosure filter)                                      (online mode)
radar-audit publish <repo>  ----------->  same builder
```

- **radar-online API**: new workspace package `radar-online/` (FastAPI,
  SQLModel, Alembic, its own SQLite file). Serves `/api/*`.
- **radar-dashboard, online mode**: same codebase, built with
  `VITE_RADAR_MODE=online`, served as static files at `/` by nginx; `/api` is
  routed to the radar-online API by Traefik, as locally.
- **Payload contract**: one Pydantic schema, `radar_core.publication`,
  imported by both `radar-api` (to build) and `radar-online` (to validate).
  It is the only code radar-online shares with the local side.
- **Email**: SMTP through the Brevo relay in production, Maildev locally (same
  setup as GeoChallenge-Tracker).

## 3. Payload contract (v1)

```json
{
  "schema_version": 1,
  "repository": {"slug": "summit-stats", "display_name": "Summit-Stats"},
  "commit_sha": "40 hex chars",
  "scored_at": "2026-11-05T14:20:00Z",
  "methodology_version": "Quality Framework v1.0",
  "global_score": 7.4,
  "categories": [
    {
      "name": "Security",
      "order": 4,
      "weight": 1.5,
      "status": "scored",
      "implemented": true,
      "value": 6.2,
      "confidence": "HIGH"
    }
  ]
}
```

Rules:

- Built from one local scoring run; only the fields above. A test on the
  builder asserts that no key outside this schema is ever produced (no
  criteria, findings, severity counts, risk, notes, paths).
- `slug`: lowercase letters, digits and hyphens, 1 to 64 chars, unique per
  user. `display_name`: 1 to 100 chars.
- Free text (`display_name`, category `name`, `methodology_version`) is a short
  printable label: no control characters or newlines, no `<` or `>`, so no field
  can carry markup or a data dump. `confidence` is `HIGH`, `MEDIUM`, `LOW` or
  null.
- Scores within 0 to 10 or null, weights within 0 to 100, no NaN or infinity;
  1 to 30 categories with unique names and orders; a non-null `global_score`
  needs at least one scored category; body at most 64 KiB (checked by the API).
- radar-online stores `payload.model_dump(mode="json")` of the validated model,
  never the raw request body.
- `status` is `scored` or `not_yet_audited`; unimplemented categories are sent
  with `implemented: false` and `value: null`, so the online report shows the
  same "Not implemented yet" markers.
- Unknown fields are rejected (`extra="forbid"`), so a newer local version
  cannot leak a field an older server would silently store.

## 4. Data model (radar-online)

| Entity | Fields | Notes |
|---|---|---|
| `User` | id, email (unique, stored and compared lowercase), display_name, slug (unique), message (up to 1000 chars), status, created_at, approved_at | status: `PENDING_EMAIL`, `PENDING_APPROVAL`, `ACTIVE`, `REJECTED`, `DISABLED` |
| `ApiKey` | id, user_id, prefix, key_hash, created_at, revoked_at | key shown once; `prefix` (first 8 chars) identifies it in logs and lists |
| `ActionToken` | id, user_id, purpose, token_hash, expires_at, used_at | purposes: `CONFIRM_EMAIL`, `REVIEW_REQUEST`, `REVEAL_KEY`, `REGENERATE_KEY`; single use |
| `PublishedRepository` | id, user_id, slug, display_name, created_at | unique (user_id, slug); created on first upload |
| `PublishedReport` | id, repository_id, commit_sha, scored_at, uploaded_at, methodology_version, schema_version, global_score, payload (JSON) | unique (repository_id, commit_sha): a new upload for the same commit replaces the row |

Implemented in `radar_online.models` (FEAT-037); deleting a user cascades in the
database to their keys, tokens, repositories and reports. The payload contract is
`radar_core.publication.PublicationPayload`.

Keys and tokens: 32 random bytes, URL-safe; stored as SHA-256 hashes
(high-entropy secrets, no need for a slow hash). Token lifetimes: email
confirmation 48 h, admin review 7 days, key reveal and regeneration 24 h.

## 5. Flows

### 5.1 Registration

1. Visitor fills `/register`: email, display name, public slug, optional
   message. Rate limited per IP, honeypot field, slug and email uniqueness
   checked. User created as `PENDING_EMAIL`; a `CONFIRM_EMAIL` token is
   emailed.
2. The link opens `/confirm-email?token=...`; the page shows a "Confirm my
   address" button. The POST marks the user `PENDING_APPROVAL` and emails the
   admin (`RADAR_ONLINE_ADMIN_EMAIL`) the request details with a
   `REVIEW_REQUEST` link.
3. The admin link opens `/review?token=...`, showing the request and two
   buttons. **Accept**: user `ACTIVE`, a `REVEAL_KEY` link is emailed to the
   user. **Refuse**: user `REJECTED`, a short refusal email is sent.
4. `/reveal-key?token=...` shows a "Show my API key" button; the POST creates
   the key and displays it once, with copy instructions for the local `.env`.

### 5.2 Lost key

`/lost-key` asks for the email address and always answers the same message,
whether or not the account exists. For an `ACTIVE` user, a `REGENERATE_KEY`
link is emailed; its page's POST revokes every previous key and shows the new
one once.

### 5.3 Publishing

1. Local `radar-api` exposes `GET /repositories/{id}/publish-preview` (the
   exact payload) and `POST /repositories/{id}/publish` (protected by the
   local API key). It reads `RADAR_ONLINE_URL` and `RADAR_ONLINE_API_KEY` from
   the local `.env`.
2. The dashboard's "Upload report" button opens a modal showing the preview,
   then posts on confirmation and links to the public page on success.
3. radar-online `POST /api/reports` (header `X-API-Key`) validates the
   payload, creates the `PublishedRepository` on first upload, then inserts or
   replaces the report for that commit. Response: the public report URL.
4. `radar-audit publish <repo>` calls the same builder and sends directly.

### 5.4 Unpublishing and account deletion

With the key: `DELETE /api/repositories/{slug}` (repository and all its
reports), `DELETE /api/repositories/{slug}/reports/{commit_sha}`,
`DELETE /api/me` (account, keys, tokens, repositories and reports).

## 6. API (radar-online)

| Method and path | Auth | Purpose |
|---|---|---|
| `POST /api/registrations` | none, rate limited | registration request |
| `POST /api/registrations/confirm` | token | email confirmed |
| `GET /api/reviews/{token}` | token | request details for the admin page |
| `POST /api/reviews/{token}` | token | accept or refuse |
| `POST /api/keys/reveal` | token | create and return the first key |
| `POST /api/keys/lost` | none, rate limited | email a regeneration link |
| `POST /api/keys/regenerate` | token | revoke old keys, return a new one |
| `POST /api/reports` | API key | publish (insert or replace by commit) |
| `DELETE /api/repositories/{slug}` | API key | unpublish a repository |
| `DELETE /api/repositories/{slug}/reports/{commit_sha}` | API key | remove one report |
| `DELETE /api/me` | API key | delete the account |
| `GET /api/users/{user}` | public | profile and published repositories |
| `GET /api/users/{user}/repositories/{slug}/report` | public | latest report |
| `GET /api/users/{user}/repositories/{slug}/history` | public | one point per commit, oldest first |
| `GET /api/users/{user}/repositories/{slug}/badge` | public | shields.io endpoint JSON |

Public reads send `Cache-Control: public, max-age=300`. The badge reads
"quality: 7.4/10 (self-assessed)", grey "not published" when nothing exists.

## 7. Online dashboard

- Routes: `/u/:user` (profile), `/u/:user/:repo` (report and trends tabs),
  `/register`, `/confirm-email`, `/review`, `/reveal-key`, `/lost-key`.
- Report tab: global gauge and category gauges only, with "Not implemented
  yet" markers, the commit, the scoring date, the methodology version and a
  "self-assessed" note. No findings, no severity summary, no risk bar.
- Trends tab: the score history chart, fed by the history endpoint.
- The build mode selects the router, the API client and hides local-only UI;
  shared components (gauges, charts) are reused unchanged.

## 8. Security and operations

- HTTPS only, behind Traefik on `radar.marvinlerouge.dev`; images run as uid
  1000, uv pinned, as for the local services.
- Rate limits on registration, lost key and report upload.
- Keys and tokens never logged; Sentry events scrubbed of `X-API-Key` and
  `token` values.
- Daily SQLite backup (`sqlite3 .backup`) kept outside the container.
- Personal data: email, display name, optional message; a privacy note on the
  registration page; `DELETE /api/me` removes everything.
- Configuration (server `.env`): `RADAR_ONLINE_DATABASE_URL`,
  `RADAR_ONLINE_PUBLIC_URL`, `RADAR_ONLINE_ADMIN_EMAIL`, `SMTP_HOST`,
  `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM`, Sentry and
  logging variables. Local `.env`: `RADAR_ONLINE_URL`, `RADAR_ONLINE_API_KEY`.

## 9. Open points for later versions

- Repository ownership verification (GitHub OAuth or a token file committed
  in the repository).
- Self-service key management page (list, revoke) once a login exists.
- History backfill from local scoring runs, with a way to skip runs flagged
  as tooling bugs.
