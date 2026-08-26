import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import routers
from app.auth.repository import auth_repository
from app.auth.security import hash_password
from app.config import settings

@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.admin_email and settings.admin_password:
        auth_repository.bootstrap_admin(
            settings.admin_email.lower().strip(),
            hash_password(settings.admin_password.get_secret_value()),
        )
    yield

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
