FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-audit ./radar-audit

RUN uv sync --frozen --package radar-audit

ENTRYPOINT ["uv", "run", "--package", "radar-audit", "radar-audit"]
