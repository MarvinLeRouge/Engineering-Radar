"""FastAPI application entry point for radar-online, served under /api."""

from fastapi import APIRouter, FastAPI
from radar_core.observability import configure_logging, init_error_tracking
from radar_core.request_logging import log_requests

from radar_online.routers import public, reports

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
app.middleware("http")(log_requests)
api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the container and Traefik."""
    return {"status": "ok"}


api.include_router(reports.router)
api.include_router(public.router)
app.include_router(api)
