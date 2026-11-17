from base64 import urlsafe_b64encode
from datetime import time
from hashlib import sha256
from typing import Any, cast
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.database import get_connection


# The sync with whether its scheduled run is due: the folder's local time has reached sync_time and that
# local date has not run yet.
_DUE = (
    "SELECT s.id, s.run_requested, (now() AT TIME ZONE s.timezone)::date AS local_date,"
    " (now() AT TIME ZONE s.timezone)::time >= s.sync_time"
    " AND s.last_run_on IS DISTINCT FROM (now() AT TIME ZONE s.timezone)::date AS scheduled"
    " FROM google_drive_sync s"
)


def _fernet() -> Fernet:
    # Derived from JWT_SECRET_KEY: rotating it signs everyone out and asks them to reconnect Drive too.
    secret = settings.jwt_secret_key.get_secret_value().encode()
    return Fernet(urlsafe_b64encode(sha256(b"google-drive-token:" + secret).digest()))


class GoogleDriveRepository:
    def save_refresh_token(self, user_id: UUID, refresh_token: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO google_drive_connections (user_id, refresh_token) VALUES (%s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET refresh_token = EXCLUDED.refresh_token, "
                "updated_at = CURRENT_TIMESTAMP",
                (user_id, _fernet().encrypt(refresh_token.encode()).decode()),
            )

    def find_refresh_token(self, user_id: UUID) -> str | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT refresh_token FROM google_drive_connections WHERE user_id = %s", (user_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            return _fernet().decrypt(cast(dict[str, Any], row)["refresh_token"].encode()).decode()
        except InvalidToken:
            return None  # encrypted under an old secret: the user reconnects

    def delete(self, user_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM google_drive_connections WHERE user_id = %s", (user_id,))

    def find_sync(self) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT s.folder_id, s.folder_name, s.access_level, s.timezone, s.sync_time, s.run_requested, "
                "s.last_synced_at, s.last_result, u.email AS owner_email "
                "FROM google_drive_sync s JOIN users u ON u.id = s.user_id WHERE s.id = 1"
            ).fetchone()
            return cast(dict[str, Any] | None, row)

    def save_sync(
        self, user_id: UUID, folder_id: str, folder_name: str, access_level: str, timezone: str, sync_time: time
    ) -> None:
        with get_connection() as connection:
            row = connection.execute("SELECT folder_id FROM google_drive_sync FOR UPDATE").fetchone()
            if row and cast(dict[str, Any], row)["folder_id"] == folder_id:
                # A changed time or time zone applies today; other edits keep today's run done.
                connection.execute(
                    "UPDATE google_drive_sync SET last_run_on = CASE WHEN sync_time = %s AND timezone = %s "
                    "THEN last_run_on END, user_id = %s, folder_name = %s, access_level = %s, timezone = %s, "
                    "sync_time = %s",
                    (sync_time, timezone, user_id, folder_name, access_level, timezone, sync_time),
                )
                return
            # A new folder starts over. The cascade forgets the old folder's files, which stay in PEKA as
            # ordinary files, and the first run imports every file already in the new folder.
            connection.execute("DELETE FROM google_drive_sync")
            connection.execute(
                "INSERT INTO google_drive_sync (user_id, folder_id, folder_name, access_level, timezone, "
                "sync_time, run_requested) VALUES (%s, %s, %s, %s, %s, %s, true)",
                (user_id, folder_id, folder_name, access_level, timezone, sync_time),
            )

    def delete_sync(self) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM google_drive_sync")

    def request_run(self) -> bool:
        with get_connection() as connection:
            return connection.execute("UPDATE google_drive_sync SET run_requested = true").rowcount > 0

    def is_due(self) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                f"SELECT EXISTS (SELECT 1 FROM ({_DUE}) due WHERE due.run_requested OR due.scheduled)"
            ).fetchone()
            return bool(cast(dict[str, Any], row)["exists"])

    def claim_due(self) -> dict | None:
        """Claim a requested run, or the day's scheduled run. finish_run clears the request."""
        with get_connection() as connection:
            row = connection.execute(
                f"WITH due AS ({_DUE} FOR UPDATE OF s) UPDATE google_drive_sync s"
                " SET last_run_on = CASE WHEN due.scheduled THEN due.local_date ELSE s.last_run_on END"
                " FROM due WHERE s.id = due.id AND (due.run_requested OR due.scheduled)"
                " RETURNING s.user_id, s.folder_id, s.access_level,"
                " EXISTS (SELECT 1 FROM users u WHERE u.id = s.user_id AND u.role = 'admin' AND u.is_active)"
                " AS owner_is_admin"
            ).fetchone()
            return cast(dict[str, Any] | None, row)

    def finish_run(self, folder_id: str, result: str) -> None:
        # Matched on the folder: if an admin picked another one mid-run, its pending first run stays queued.
        with get_connection() as connection:
            connection.execute(
                "UPDATE google_drive_sync SET last_result = %s, last_synced_at = CURRENT_TIMESTAMP, "
                "run_requested = false WHERE folder_id = %s",
                (result, folder_id),
            )

    def synced_files(self) -> dict[str, dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT drive_file_id, file_id, modified_time FROM google_drive_synced_files"
            ).fetchall()
            return {row["drive_file_id"]: row for row in cast(list[dict[str, Any]], rows)}

    def record_synced(self, drive_file_id: str, file_id: UUID | None, modified_time: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO google_drive_synced_files (drive_file_id, file_id, modified_time) VALUES (%s, %s, %s) "
                "ON CONFLICT (drive_file_id) DO UPDATE SET file_id = EXCLUDED.file_id, "
                "modified_time = EXCLUDED.modified_time",
                (drive_file_id, file_id, modified_time),
            )

    def forget_synced(self, drive_file_id: str) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM google_drive_synced_files WHERE drive_file_id = %s", (drive_file_id,))


google_drive_repository = GoogleDriveRepository()
