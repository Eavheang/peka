from app.auth.routes import router as auth_router
from app.auth.model import User  # noqa: F401 - register table in shared metadata

routers = [
    auth_router,
]

