import logging
from uuid import UUID

from app.audit.repository import audit_repository

logger = logging.getLogger(__name__)


def record(
    type: str,
    summary: str,
    actor_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Persist one audit event. Failures are logged and never raised to callers."""
    try:
        if actor_id is not None and not isinstance(actor_id, UUID):
            actor_id = UUID(str(actor_id))
        audit_repository.insert(type, summary, actor_id, dict(metadata or {}))
    except Exception as error:
        logger.warning("Failed to record audit event: %s", error)
