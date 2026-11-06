[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# radar-dashboard

Web dashboard for [Engineering-Radar](../README.md).

`radar-dashboard` is a single-page app over [`radar-api`](../radar-api/README.md):
it shows each audited repository's report, roadmap and score trends, and lets a
human record verdicts, statuses and notes on findings and roadmap items.

## Pages

- `/`: repository list.
- `/repositories/<slug>-<id>`: repository detail, with three tabs.
  - Report: weighted risk bar, severity summary, categories and criteria with
    score gauges, "Not implemented yet" markers (planned criteria collapsed),
    findings grouped by severity then file, a "More" button loading 1000
    findings at a time, a dismissed section, verdict and status selects, and a
    verdict note with preset reasons.
  - Roadmap: roadmap items, their status, done evidence, and a Markdown export.
  - Trends: score history and weighted risk history charts, unimplemented
    categories greyed out.
- `/settings`: API key.

## Stack

Vue 3, Vite, Pinia, Vue Router, Chart.js (`vue-chartjs`), Sentry (`@sentry/vue`).
Tests with Vitest and Playwright. Node `^22.18 || ^23 || >=24.12` (CI uses 24).

## Development

    cd radar-dashboard
    npm ci
    npm run dev

The Vite dev server proxies `/api` to `radar-api` (prefix stripped), at
`http://localhost:8000` by default. Point it at another API with
`RADAR_API_URL`:

    RADAR_API_URL=http://localhost:8020 npm run dev

## API key

Reading needs no key. The `PATCH` calls (verdict, status, note, roadmap
status) send the key saved on the Settings page as `X-API-Key`; it must match
`radar-api`'s `RADAR_API_KEY`. The key is kept in the browser session storage
only.

## Tests

    npm run test:unit       # Vitest, watch mode
    npm run test:coverage   # Vitest, single run with coverage
    npm run test:e2e        # Playwright

The end-to-end run owns its whole stack (`playwright.config.ts`): it seeds a
throwaway SQLite database (`scripts/seed_e2e_db.py`), starts its own
`radar-api` on port 8020 through `uv`, and serves a production build on port
4180. It never touches the real `radar.db`, `.env` or running services. It
needs `uv` and a Playwright browser (`npx playwright install chromium`).

## Quality checks

    npm run lint        # oxlint then ESLint, with --fix
    npm run format      # Prettier on src/
    npm run type-check  # vue-tsc

The pre-commit hook runs these three on dashboard changes. CI runs the lint,
a Prettier check, the type-check, the coverage tests and the end-to-end tests.

## Docker

    scripts/rebuild.sh radar-dashboard

Run from the repo root. The image builds the app with Node, then serves it
with nginx (SPA fallback to `index.html`). Traefik exposes it at
`radar.marvinlerouge.local`, which also routes `/api` to `radar-api`.
Sentry is optional: the `VITE_SENTRY_DSN` (from `SENTRY_FRONTEND_DSN`) and
`VITE_SENTRY_ENVIRONMENT` build args are baked in at build time, so changing
them needs a rebuild. See [`docs/operations.md`](../docs/operations.md).
