FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY radar-core ./radar-core
COPY radar-api ./radar-api

RUN uv sync --frozen --package radar-api

EXPOSE 8000

CMD ["uv", "run", "--package", "radar-api", "uvicorn", "radar_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
