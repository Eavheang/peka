from uuid import UUID

from app.auth.repository import auth_repository
from app.auth.security import dummy_password_hash, hash_password, verify_password
from app.auth.schemas import UserCreate


class UserNotFoundError(Exception):
    pass


class UserMustBeInactiveError(Exception):
    pass


class UserHasRelatedRecordsError(Exception):
    pass


def authenticate(email: str, password: str) -> dict | None:
    user = auth_repository.find_by_email(email)
    # Keep unknown-email login timing comparable to a password verification.
    if user is None:
        verify_password(password, dummy_password_hash)
        return None
    password_valid = verify_password(password, user["password_hash"])
    return user if user["is_active"] and password_valid else None


def create_user(data: UserCreate) -> dict:
    return auth_repository.create(data.email, hash_password(data.password), data.role)


def current_user(user_id: UUID) -> dict | None:
    return auth_repository.find_by_id(user_id)

def list_users() -> list[dict]:
    return auth_repository.list()


def set_user_active(user_id: UUID, is_active: bool) -> dict:
    user = auth_repository.set_active(user_id, is_active)
    if user is None:
        raise UserNotFoundError
    return user


def delete_user(user_id: UUID) -> None:
    result = auth_repository.delete_deactivated(user_id)
    if result == "not_found":
        raise UserNotFoundError
    if result == "active":
        raise UserMustBeInactiveError
    if result == "related":
        raise UserHasRelatedRecordsError
