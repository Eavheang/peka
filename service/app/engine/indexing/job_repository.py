from typing import Any, cast
from uuid import UUID

from app.database import get_connection


class IndexJobsRepository:
    def reset_processing(self) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE index_jobs SET status = 'queued', updated_at = CURRENT_TIMESTAMP "
                "WHERE status = 'processing'"
            )

    def claim_next(self) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT jobs.file_id, files.path "
                "FROM index_jobs jobs JOIN files ON files.id = jobs.file_id "
                "WHERE jobs.status = 'queued' AND jobs.attempts < 3 "
                "ORDER BY jobs.attempts, files.created_at "
                "FOR UPDATE OF jobs SKIP LOCKED LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            job = cast(dict[str, Any], row)
            connection.execute(
                "UPDATE index_jobs SET status = 'processing', attempts = attempts + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE file_id = %s",
                (job["file_id"],),
            )
            return job

    def complete(self, file_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE index_jobs SET status = 'completed', last_error = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE file_id = %s",
                (file_id,),
            )

    def fail(self, file_id: UUID, error: str) -> str:
        with get_connection() as connection:
            row = connection.execute(
                "UPDATE index_jobs SET status = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'queued' END, "
                "last_error = %s, updated_at = CURRENT_TIMESTAMP WHERE file_id = %s "
                "RETURNING status",
                (error[:2000], file_id),
            ).fetchone()
            return cast(dict[str, str], row)["status"] if row else "failed"

    def retry_failed(self, file_id: UUID) -> bool:
        with get_connection() as connection:
            return connection.execute(
                "UPDATE index_jobs SET status = 'queued', attempts = 0, last_error = NULL, "
                "updated_at = CURRENT_TIMESTAMP WHERE file_id = %s AND status = 'failed' "
                "RETURNING file_id",
                (file_id,),
            ).fetchone() is not None


index_jobs_repository = IndexJobsRepository()
