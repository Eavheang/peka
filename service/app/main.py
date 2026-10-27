import asyncio
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI

from app import routers
from app.auth.repository import auth_repository
from app.auth.security import hash_password
from app.config import settings

@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.admin_email and settings.admin_password:
        email = settings.admin_email.lower().strip()
        password_hash = hash_password(settings.admin_password.get_secret_value())
        # `docker compose restart` ignores depends_on health, so Postgres may still be starting up.
        for attempt in range(30):
            try:
                auth_repository.bootstrap_admin(email, password_hash)
                break
            except psycopg.OperationalError:
                if attempt == 29:
                    raise
                await asyncio.sleep(1)
    yield

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
