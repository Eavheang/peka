from uuid import UUID

from app.database import get_connection


class FilesRepository:
    def create_many(self, records: list[tuple[str, str | None]], author_id: UUID) -> list[dict]:
        created = []
        with get_connection() as connection:
            for path, content_type in records:
                created.append(connection.execute(
                    "INSERT INTO files (path, content_type, author_id) VALUES (%s, %s, %s) "
                    "RETURNING id, path, content_type, author_id, created_at",
                    (path, content_type, author_id),
                ).fetchone())
        return created

    def list_all(self) -> list[dict]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, path, content_type, author_id, created_at "
                "FROM files ORDER BY created_at DESC"
            ).fetchall()

    def find_by_id(self, file_id: UUID) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, path, content_type, author_id, created_at FROM files WHERE id = %s",
                (file_id,),
            ).fetchone()

    def delete(self, file_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM files WHERE id = %s", (file_id,))


files_repository = FilesRepository()
