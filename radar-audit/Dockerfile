FROM python:3.14-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# uv pinned to an exact release (FIX-014 floor: >=0.13.4), never :latest; bump it here on purpose.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

# Scoped to the install step, not ENV: at runtime the runners call uv/uvx on audited repos,
# which need Python downloads, the uv cache and their own project environment.
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-audit ./radar-audit

RUN UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 UV_NO_CACHE=1 \
    uv sync --frozen --no-dev --package radar-audit

# Drop root for the running process (semgrep dockerfile.security.missing-user-entrypoint).
# /data is this service's sqlite volume mount point: created with appuser
# ownership here so a fresh named volume inherits it on first creation; an
# already-existing volume from a prior root-run deployment needs a one-time
# `chown -R 1000:1000` on it before the first non-root deploy.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /workspace /data
# Numeric id (appuser, created above with --uid 1000) so the host can resolve it.
USER 1000

ENTRYPOINT ["radar-audit"]
