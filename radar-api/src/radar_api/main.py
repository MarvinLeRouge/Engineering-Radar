from fastapi import FastAPI

from radar_api.routers import findings, repositories, roadmap

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
app.include_router(findings.router)
app.include_router(roadmap.router)
