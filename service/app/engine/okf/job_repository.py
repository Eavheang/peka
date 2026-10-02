from typing import Any, cast
from uuid import UUID

from app.database import get_connection


class OKFJobsRepository:
    def reset_processing(self) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE okf_jobs SET status = 'queued', updated_at = CURRENT_TIMESTAMP "
                "WHERE status = 'processing'"
            )

    def claim_next(self) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT jobs.file_id, files.path "
                "FROM okf_jobs jobs JOIN files ON files.id = jobs.file_id "
                "WHERE jobs.status = 'queued' AND jobs.attempts < 3 "
                "ORDER BY jobs.attempts, files.created_at "
                "FOR UPDATE OF jobs SKIP LOCKED LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            job = cast(dict[str, Any], row)
            connection.execute(
                "UPDATE okf_jobs SET status = 'processing', attempts = attempts + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE file_id = %s",
                (job["file_id"],),
            )
            return job

    def complete(self, file_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE okf_jobs SET status = 'completed', last_error = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE file_id = %s",
                (file_id,),
            )
        _record_sync_end(file_id, "completed")

    def fail(self, file_id: UUID, error: str) -> str:
        with get_connection() as connection:
            row = connection.execute(
                "UPDATE okf_jobs SET status = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'queued' END, "
                "last_error = %s, updated_at = CURRENT_TIMESTAMP WHERE file_id = %s "
                "RETURNING status",
                (error[:2000], file_id),
            ).fetchone()
            status = cast(dict[str, str], row)["status"] if row else "failed"
        if row is not None:
            _record_sync_end(file_id, status)
        return status

    def retry_failed(self, file_id: UUID) -> bool:
        with get_connection() as connection:
            return connection.execute(
                "UPDATE okf_jobs SET status = 'queued', attempts = 0, last_error = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE file_id = %s AND status = 'failed' "
                "RETURNING file_id",
                (file_id,),
            ).fetchone() is not None


def _record_sync_end(file_id: UUID, status: str) -> None:
    from app.audit.writer import record

    if status == "completed":
        summary = "Sync completed"
    elif status == "failed":
        summary = "Sync failed"
    else:
        return
    record("sync", summary, metadata={"file_id": str(file_id), "status": status})


okf_jobs_repository = OKFJobsRepository()
