FROM python:3.12-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN pip install --no-cache-dir "uv>=0.13.4"

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-api ./radar-api

RUN uv sync --frozen --package radar-api

# Drop root for the running process (semgrep dockerfile.security.missing-user).
# /data is this service's sqlite volume mount point: created with appuser
# ownership here so a fresh named volume inherits it on first creation; an
# already-existing volume from a prior root-run deployment needs a one-time
# `chown -R 1000:1000` on it before the first non-root deploy.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /workspace /data
USER appuser

EXPOSE 8000

CMD ["uv", "run", "--package", "radar-api", "uvicorn", "radar_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
