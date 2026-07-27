import logging
from uuid import UUID

import psycopg

from app.database import get_connection

logger = logging.getLogger(__name__)


class AuthRepository:
    def find_by_email(self, email: str) -> dict | None:
        with get_connection() as connection:
            return connection.execute("SELECT * FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone()

    def find_by_id(self, user_id: UUID) -> dict | None:
        with get_connection() as connection:
            return connection.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()

    def create(self, email: str, password_hash: str, role: str) -> dict:
        try:
            with get_connection() as connection:
                return connection.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) "
                    "RETURNING id, email, role", (email, password_hash, role),
                ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise ValueError("duplicate email") from None

    def revoke(self, user_id: UUID) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = %s", (user_id,)
            )

    def bootstrap_admin(self, email: str, password_hash: str) -> None:
        try:
            with get_connection() as connection:
                connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('peka-admin-bootstrap', 0))")
                if connection.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone() is None:
                    connection.execute(
                        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, 'admin')",
                        (email, password_hash),
                    )
        except psycopg.errors.UniqueViolation:
            logger.warning("Admin bootstrap skipped: ADMIN_EMAIL already belongs to an existing user")


auth_repository = AuthRepository()
