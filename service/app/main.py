from fastapi import FastAPI

from app import routers
from app.config import settings


app = FastAPI(title=settings.app_name, debug=settings.debug)

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
