from fastapi import FastAPI

from app.config import settings
from app.routes import routers


app = FastAPI(title=settings.app_name, debug=settings.debug)

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
