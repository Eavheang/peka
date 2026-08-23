from typing import Any, cast
from uuid import UUID

from app.database import get_connection


class FilesRepository:
    def create_many(self, records: list[tuple[str, str | None, str]], author_id: UUID) -> list[dict]:
        created = []
        with get_connection() as connection:
            for path, content_type, sha256 in records:
                row = connection.execute(
                    "INSERT INTO files (path, content_type, sha256, author_id) VALUES (%s, %s, %s, %s) "
                    "RETURNING id, path, content_type, sha256, author_id, access_level, created_at",
                    (path, content_type, sha256, author_id),
                ).fetchone()
                if row is None:
                    raise RuntimeError("Unable to create file record")
                record = cast(dict[str, Any], row)
                connection.execute("INSERT INTO okf_jobs (file_id) VALUES (%s)", (record["id"],))
                record.update(okf_status="queued", okf_attempts=0, okf_error=None)
                created.append(record)
        return created

    def list_all(self) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT files.id, files.path, files.content_type, files.sha256, files.author_id, "
                "files.access_level, files.created_at, jobs.status AS okf_status, "
                "jobs.attempts AS okf_attempts, jobs.last_error AS okf_error FROM files "
                "JOIN okf_jobs jobs ON jobs.file_id = files.id ORDER BY files.created_at DESC"
            ).fetchall()
            return cast(list[dict[str, Any]], rows)

    def exists_by_sha256(self, sha256: str) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM files WHERE sha256 = %s)",
                (sha256,),
            ).fetchone()
            return bool(cast(dict[str, Any], row)["exists"])

    def find_by_id(self, file_id: UUID) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT files.id, files.path, files.content_type, files.sha256, files.author_id, "
                "files.access_level, files.created_at, jobs.status AS okf_status, "
                "jobs.attempts AS okf_attempts, jobs.last_error AS okf_error FROM files "
                "JOIN okf_jobs jobs ON jobs.file_id = files.id WHERE files.id = %s",
                (file_id,),
            ).fetchone()
            return cast(dict[str, Any] | None, row)

    def update_access_level(self, file_id: UUID, access_level: str) -> bool:
        with get_connection() as connection:
            updated = connection.execute(
                "UPDATE files SET access_level = %s WHERE id = %s",
                (access_level, file_id),
            ).rowcount
            return updated > 0

    def delete(self, file_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM files WHERE id = %s", (file_id,))


files_repository = FilesRepository()
