from uuid import UUID

from app.auth.repository import auth_repository
from app.auth.security import dummy_password_hash, hash_password, verify_password
from app.auth.schemas import UserCreate


def authenticate(email: str, password: str) -> dict | None:
    user = auth_repository.find_by_email(email)
    # Keep unknown-email login timing comparable to a password verification.
    if user is None:
        verify_password(password, dummy_password_hash)
        return None
    return user if verify_password(password, user["password_hash"]) else None


def create_user(data: UserCreate) -> dict:
    return auth_repository.create(data.email, hash_password(data.password), data.role)


def current_user(user_id: UUID) -> dict | None:
    return auth_repository.find_by_id(user_id)
