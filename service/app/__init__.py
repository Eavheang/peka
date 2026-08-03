from app.auth.routes import router as auth_router
from app.auth.model import User  # noqa: F401 - register table in shared metadata
from app.files.routes import router as files_router
from app.files.model import StoredFile  # noqa: F401 - register table in shared metadata
from app.engine.OKFExtractor.model import OKFJob  # noqa: F401 - register table in shared metadata

routers = [
    auth_router,
    files_router,
]

