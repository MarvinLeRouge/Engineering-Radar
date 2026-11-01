"""FastAPI application entry point that registers the radar-api routers."""

from fastapi import FastAPI

from radar_api.routers import findings, history, repositories, roadmap

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
app.include_router(findings.router)
app.include_router(roadmap.router)
app.include_router(history.router)
