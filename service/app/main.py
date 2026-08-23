import logging
from contextlib import asynccontextmanager

import fastapi
from fastapi import FastAPI

from app import routers
from app.config import settings
from app.auth.repository import auth_repository
from app.auth.security import hash_password
from app.engine.okf.worker import run_worker_in_thread


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.admin_email and settings.admin_password:
        auth_repository.bootstrap_admin(
            settings.admin_email.lower().strip(),
            hash_password(settings.admin_password.get_secret_value()),
        )
    worker_thread, worker_stop = run_worker_in_thread()
    yield
    worker_stop.set()
    worker_thread.join(timeout=10)
    if worker_thread.is_alive():
        logging.getLogger(__name__).warning("OKF worker did not stop cleanly")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

for router in routers:
    app.include_router(router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
