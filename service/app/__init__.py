from app.auth.routes import router as auth_router
from app.auth.model import Invitation, User  # noqa: F401 - register tables in shared metadata
from app.audit.model import AuditEvent  # noqa: F401 - register table in shared metadata
from app.audit.routes import router as audit_router
from app.files.routes import router as files_router
from app.files.model import StoredFile  # noqa: F401 - register table in shared metadata
from app.engine.okf.job_model import OKFJob  # noqa: F401 - register table in shared metadata
from app.engine.chunks.chunk_model import KnowledgeChunk  # noqa: F401 - register table in shared metadata
from app.engine.chunks.chunk_set_model import ChunkSet  # noqa: F401 - register table in shared metadata
from app.engine.search.routes import router as search_router
from app.chat.routes import router as chat_router
from app.workspace_settings import router as workspace_settings_router
from app.chat.model import ChatMessage, Conversation  # noqa: F401 - register chat tables in shared metadata

routers = [
    auth_router,
    files_router,
    search_router,
    chat_router,
    workspace_settings_router,
    audit_router,
]
