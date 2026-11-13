[🇫🇷 Version française](docs/i18n/fr/CONTRIBUTING.fr.md) | 🇬🇧 English version

---

# Contributing to Engineering Radar

This is primarily a personal project. External contributions (bug reports, fixes, small improvements) are welcome but limited in scope.

## Prerequisites

- Python 3.14 (pinned in `.python-version`, uv installs it if missing)
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Node.js `^22.18.0 || ^23.0.0 || >=24.12.0` (the `engines` field of `radar-dashboard/package.json`; CI uses 24) and npm, for the dashboard

## Local setup

```bash
git clone https://github.com/MarvinLeRouge/Engineering-Radar.git
cd Engineering-Radar
uv sync
npm ci --prefix radar-dashboard
uv run pre-commit install
```

## Running tests

```bash
uv run --package radar-core pytest
uv run --package radar-audit pytest
uv run --package radar-api pytest
cd radar-dashboard
npm run test:coverage   # Vitest unit tests with coverage
npm run test:e2e        # Playwright end-to-end tests (run `npx playwright install chromium` once first)
```

## Workflow

1. Fork the repository and create a branch off `main`.
2. Make your change, with tests covering it.
3. Commit following the convention below.
4. Push and open a pull request against `main`.
5. Pre-commit hooks (see below) must pass before review.

## Branch naming

| Type | Prefix |
|---|---|
| Feature | `feat/short-description` |
| Bug fix | `fix/short-description` |
| Chore | `chore/short-description` |
| Documentation | `docs/short-description` |
| Refactor | `refactor/short-description` |
| Tests | `test/short-description` |

Use lowercase kebab-case. No special characters.

## Commit convention

Follow [Conventional Commits](https://www.conventionalcommits.org/), imperative mood, lowercase summary, no trailing period, with a mandatory `Modified files:` section:

```
<type>(<optional scope>): <short summary>

Modified files:
- path/to/file-a.ext - what was changed
- path/to/file-b.ext - what was changed
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`.

## Code style

Pre-commit hooks (`.pre-commit-config.yaml`) check every commit:

- Python (`radar-core`, `radar-audit`, `radar-api`): `ruff` (lint, with fixes), `ruff-format`, and `mypy --strict` per package.
- Dashboard (`radar-dashboard`): `oxlint` and `eslint` (with fixes), `prettier`, and `vue-tsc`, through its npm scripts. They need `npm ci` to have been run in `radar-dashboard/`.

A hook that fixes or reformats files fails the commit: review the changes and commit again. Run `uv run pre-commit run --all-files` to check everything at once.

CI (`.github/workflows/ci.yml`) runs the tests of every package with an 80% coverage gate, the dashboard's lint, format and type checks, its Playwright end-to-end tests, and a `pip-audit` scan of the locked Python dependencies (`uv.lock`) that fails on any known vulnerability. The Python lint and type checks run only in the pre-commit hooks.

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it.

## License

By contributing, you agree that your contributions will be licensed under the project's license (see [LICENSE](LICENSE)).
