from fastapi import FastAPI

from radar_api.routers import findings, repositories

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
app.include_router(findings.router)
