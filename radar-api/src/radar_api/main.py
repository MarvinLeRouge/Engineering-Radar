"""FastAPI application entry point that registers the radar-api routers."""

from fastapi import FastAPI
from radar_core.observability import configure_logging, init_error_tracking

from radar_api.request_logging import log_requests
from radar_api.routers import findings, history, repositories, roadmap

configure_logging()
init_error_tracking()

app = FastAPI(title="radar-api")
app.middleware("http")(log_requests)
app.include_router(repositories.router)
app.include_router(findings.router)
app.include_router(roadmap.router)
app.include_router(history.router)
