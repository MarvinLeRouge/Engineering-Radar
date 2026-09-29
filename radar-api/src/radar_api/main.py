from fastapi import FastAPI

from radar_api.routers import repositories

app = FastAPI(title="radar-api")
app.include_router(repositories.router)
