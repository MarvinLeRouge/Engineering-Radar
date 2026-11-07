"""FastAPI application entry point for radar-online, served under /api."""

from fastapi import APIRouter, FastAPI
from radar_core.observability import configure_logging, init_error_tracking

configure_logging()
init_error_tracking()

# Traefik routes /api to this service and serves the dashboard on the same host, so
# every route, the OpenAPI schema and the docs live under /api.
app = FastAPI(
    title="radar-online",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
)
api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the container and Traefik."""
    return {"status": "ok"}


app.include_router(api)
