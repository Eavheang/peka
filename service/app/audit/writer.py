import logging
from uuid import UUID

from app.audit.repository import audit_repository
from app.audit.schemas import AuditEventType

logger = logging.getLogger(__name__)


def record(
    event_type: AuditEventType,
    summary: str,
    actor_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Persist one audit event. Failures are logged and never raised to callers."""
    try:
        audit_repository.insert(event_type, summary, actor_id, metadata or {})
    except Exception as error:
        logger.warning("Failed to record audit event: %s", error)
