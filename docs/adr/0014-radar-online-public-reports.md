# 0014. radar-online: public, sanitized reports and badges

**Status:** Accepted
**Date:** 2026-11-07
**Deciders:** Jean Ceugniet
**Sources:** design discussion of 2026-11-07, [radar-online design](../radar-online-design.md)

## Context

The quality badge served by `radar-api` only works locally: the API runs on
the developer's machine, so a README badge pointing at it is unreachable for
anyone else. Publishing the full report is not an option either: findings name
files, lines, vulnerable packages and leaked secrets, and even per-criterion
scores tell an attacker where to look (a 0/10 on "Secrets in tracked history"
announces that a secret sits in a public git history).

## Decision

- **A separate hosted service, `radar-online`**, at `radar.marvinlerouge.dev`
  behind the existing Traefik, with its own FastAPI API and its own SQLite
  database. It never receives `radar-core` audit data: its data model holds
  users, API keys, published repositories and published reports only.
- **Disclosure: global score and category scores only.** No criterion score,
  no finding, file, severity count, recommendation, verdict note or risk index
  ever leaves the local machine. The filter is applied locally, before
  sending, and the user sees the exact payload and confirms it.
- **Upload is server to server.** The dashboard's "Upload report" button calls
  the local `radar-api`, which builds the payload and sends it with the
  user's radar-online API key read from the local `.env`. The key never
  reaches a browser. A `radar-audit publish <repo>` command does the same from
  the CLI.
- **One trend point per commit.** A new upload for a commit already published
  replaces that commit's report; re-scoring after a verdict change leaves no
  stray point.
- **Self-assessed scores, namespaced per user.** The audit runs on the user's
  machine, so nothing can prove the scores are genuine; public pages and the
  badge say "self-assessed". Reports live under `/u/<user>/<repo>`, so a user
  never claims a repository's global identity. Ownership verification is out
  of scope for the first version.
- **Registration on request, approved by the admin.** A visitor requests an
  account; a confirmation email (Brevo SMTP relay) proves the address; the
  confirmation then emails the admin, who accepts or refuses. On acceptance
  the user receives a one-time link revealing their API key. A lost key is
  replaced through an email link, which revokes the previous one.
- **No email link acts on its own.** Every link leads to a page where an
  explicit click (a POST) performs the action, because mail security scanners
  open links automatically. Tokens are random, stored hashed, single use and
  expiring.
- **API keys are stored hashed**, shown once, revocable.
- **One dashboard codebase** with an `online` build mode: no roadmap, no
  findings, no verdicts, no local settings; adds the public profile, the
  registration and key pages.

## Consequences

- A public README badge and a shareable report page become possible without
  exposing anything exploitable.
- The trust model is explicit: radar-online displays what a user chose to
  publish, labelled as self-assessed.
- The project gains its first hosted, multi-user component: email delivery,
  rate limiting, backups and personal data (email addresses) now matter,
  including real account deletion.
- The payload is self-describing (methodology version, category names, order,
  weights), so radar-online needs no copy of the taxonomy and old reports
  stay readable after a methodology change.

## Alternatives considered

- **Publish the full report behind obscurity (unlisted URL):** rejected, the
  findings would still be one leaked link away from public.
- **Publish criterion scores too:** rejected, a criterion score already
  discloses a weakness (secrets, vulnerable dependencies or images).
- **Upload straight from the browser:** rejected, the radar-online key would
  live in the browser and CORS would have to be opened on radar-online.
- **Open self-service sign-up:** rejected for the first version, an admin
  approval step keeps spam and abuse out at no cost while the user base is
  small.
- **Reuse `radar-api` with an online flag:** rejected, its data model is
  exactly the data that must not be hosted.
