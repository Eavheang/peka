from datetime import datetime
from typing import Literal

from uuid import UUID

import psycopg

from app.database import get_connection


class AuthRepository:
    def find_by_email(self, email: str) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, email, display_name, role, password_hash, token_version, is_active FROM users WHERE email = %s",
                (email,),
            ).fetchone()

    def find_by_id(self, user_id: UUID) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, email, display_name, role, token_version, is_active FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
    def list(self) -> list[dict]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, email, display_name, role, is_active FROM users ORDER BY created_at",
            ).fetchall()

    def revoke(self, user_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = %s", (user_id,)
            )

    def set_active(self, user_id: UUID, is_active: bool) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "UPDATE users SET is_active = %s, "
                "token_version = token_version + "
                "CASE WHEN is_active IS DISTINCT FROM %s THEN 1 ELSE 0 END, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s "
                "RETURNING id, email, display_name, role, token_version, is_active",
                (is_active, is_active, user_id),
            ).fetchone()

    def set_role(self, user_id: UUID, role: str) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "UPDATE users SET role = %s, token_version = token_version + "
                "CASE WHEN role IS DISTINCT FROM %s THEN 1 ELSE 0 END, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s "
                "RETURNING id, email, display_name, role, token_version, is_active",
                (role, role, user_id),
            ).fetchone()

    def set_display_name(self, user_id: UUID, display_name: str) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "UPDATE users SET display_name = %s, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = %s RETURNING id, email, display_name, role, is_active",
                (display_name, user_id),
            ).fetchone()

    def password_hash(self, user_id: UUID) -> str | None:
        with get_connection() as connection:
            user = connection.execute(
                "SELECT password_hash FROM users WHERE id = %s", (user_id,)
            ).fetchone()
            return user["password_hash"] if user else None

    def update_password(self, user_id: UUID, password_hash: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET password_hash = %s, token_version = token_version + 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (password_hash, user_id),
            )

    def delete_deactivated(
        self, user_id: UUID
    ) -> Literal["deleted", "active", "not_found", "related"]:
        try:
            with get_connection() as connection:
                user = connection.execute(
                    "SELECT is_active FROM users WHERE id = %s FOR UPDATE", (user_id,)
                ).fetchone()
                if user is None:
                    return "not_found"
                if user["is_active"]:
                    return "active"
                connection.execute("DELETE FROM users WHERE id = %s", (user_id,))
                return "deleted"
        except psycopg.errors.ForeignKeyViolation:
            return "related"

    def bootstrap_admin(self, email: str, password_hash: str) -> None:
        with get_connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('peka-admin-bootstrap', 0))")
            if connection.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone() is None:
                connection.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, 'admin')",
                    (email, password_hash),
                )


INVITATION_COLUMNS = "id, email, role, expires_at, created_at"


class InvitationRepository:
    def create(self, email: str, role: str, token_hash: str, invited_by: UUID, expires_at: datetime) -> dict:
        try:
            with get_connection() as connection:
                return connection.execute(
                    "INSERT INTO invitations (email, role, token_hash, invited_by, expires_at) "
                    f"VALUES (%s, %s, %s, %s, %s) RETURNING {INVITATION_COLUMNS}",
                    (email, role, token_hash, invited_by, expires_at),
                ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise ValueError("pending invitation exists") from None

    def list_pending(self) -> list[dict]:
        with get_connection() as connection:
            return connection.execute(
                f"SELECT {INVITATION_COLUMNS} FROM invitations WHERE accepted_at IS NULL "
                "ORDER BY created_at DESC"
            ).fetchall()

    def replace_token(self, invitation_id: UUID, token_hash: str, expires_at: datetime) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "UPDATE invitations SET token_hash = %s, expires_at = %s "
                f"WHERE id = %s AND accepted_at IS NULL RETURNING {INVITATION_COLUMNS}",
                (token_hash, expires_at, invitation_id),
            ).fetchone()

    def delete_pending(self, invitation_id: UUID) -> bool:
        with get_connection() as connection:
            return connection.execute(
                "DELETE FROM invitations WHERE id = %s AND accepted_at IS NULL", (invitation_id,)
            ).rowcount > 0

    def find_valid(self, token_hash: str) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT email, role FROM invitations "
                "WHERE token_hash = %s AND accepted_at IS NULL AND expires_at > CURRENT_TIMESTAMP",
                (token_hash,),
            ).fetchone()

    def accept(self, token_hash: str, display_name: str, password_hash: str) -> dict | None:
        """Create the invited user and consume the invitation in one transaction."""
        try:
            with get_connection() as connection:
                invitation = connection.execute(
                    "SELECT id, email, role FROM invitations "
                    "WHERE token_hash = %s AND accepted_at IS NULL AND expires_at > CURRENT_TIMESTAMP "
                    "FOR UPDATE",
                    (token_hash,),
                ).fetchone()
                if invitation is None:
                    return None
                user = connection.execute(
                    "INSERT INTO users (email, display_name, password_hash, role) VALUES (%s, %s, %s, %s) "
                    "RETURNING id, email, display_name, role, token_version, is_active",
                    (invitation["email"], display_name, password_hash, invitation["role"]),
                ).fetchone()
                connection.execute(
                    "UPDATE invitations SET accepted_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (invitation["id"],),
                )
                return user
        except psycopg.errors.UniqueViolation:
            raise ValueError("email already registered") from None


auth_repository = AuthRepository()
invitation_repository = InvitationRepository()
