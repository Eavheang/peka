from typing import Any, cast
from uuid import UUID

from app.database import get_connection


class GoogleDriveRepository:
    def save_refresh_token(self, user_id: UUID, refresh_token: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO google_drive_connections (user_id, refresh_token) VALUES (%s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET refresh_token = EXCLUDED.refresh_token, "
                "updated_at = CURRENT_TIMESTAMP",
                (user_id, refresh_token),
            )

    def find_refresh_token(self, user_id: UUID) -> str | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT refresh_token FROM google_drive_connections WHERE user_id = %s", (user_id,)
            ).fetchone()
            return cast(dict[str, Any], row)["refresh_token"] if row else None

    def delete(self, user_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM google_drive_connections WHERE user_id = %s", (user_id,))


google_drive_repository = GoogleDriveRepository()
