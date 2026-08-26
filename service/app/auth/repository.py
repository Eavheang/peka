from typing import Literal

from uuid import UUID

import psycopg

from app.database import get_connection


class AuthRepository:
    def find_by_email(self, email: str) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, email, role, password_hash, token_version, is_active FROM users WHERE email = %s",
                (email,),
            ).fetchone()

    def find_by_id(self, user_id: UUID) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, email, role, token_version, is_active FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
    def list(self) -> list[dict]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, email, role, is_active FROM users ORDER BY created_at",
            ).fetchall()

    def create(self, email: str, password_hash: str, role: str) -> dict:
        try:
            with get_connection() as connection:
                return connection.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) "
                    "RETURNING id, email, role, is_active", (email, password_hash, role),
                ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise ValueError("duplicate email") from None

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
                "RETURNING id, email, role, token_version, is_active",
                (is_active, is_active, user_id),
            ).fetchone()

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


auth_repository = AuthRepository()
