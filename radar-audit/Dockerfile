FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-audit ./radar-audit

RUN uv sync --frozen --package radar-audit

# Drop root for the running process (semgrep dockerfile.security.missing-user-entrypoint).
# /data is this service's sqlite volume mount point: created with appuser
# ownership here so a fresh named volume inherits it on first creation; an
# already-existing volume from a prior root-run deployment needs a one-time
# `chown -R 1000:1000` on it before the first non-root deploy.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /workspace /data
USER appuser

ENTRYPOINT ["uv", "run", "--package", "radar-audit", "radar-audit"]
