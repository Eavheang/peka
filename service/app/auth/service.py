import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID

from app.auth.mailer import send_invitation
from app.auth.repository import auth_repository, invitation_repository
from app.auth.security import dummy_password_hash, hash_password, verify_password
from app.auth.schemas import UserCreate
from app.config import settings


class UserNotFoundError(Exception):
    pass


class UserMustBeInactiveError(Exception):
    pass


class UserHasRelatedRecordsError(Exception):
    pass


class IncorrectCurrentPasswordError(Exception):
    pass


class CannotChangeOwnAdminRoleError(Exception):
    pass


class EmailAlreadyRegisteredError(Exception):
    pass


class InvitationPendingError(Exception):
    pass


class InvitationNotFoundError(Exception):
    pass


def _hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _new_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, _hash_token(token)


def _expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.invitation_expire_days)


def _deliver(invitation: dict, token: str) -> dict:
    invite_url = f"{settings.app_base_url.rstrip('/')}/accept-invite?token={token}"
    email_sent = send_invitation(
        invitation["email"], invite_url, settings.invitation_expire_days, invitation["role"]
    )
    return {**invitation, "invite_url": invite_url, "email_sent": email_sent}


def invite_user(email: str, role: str, invited_by: UUID) -> dict:
    if auth_repository.find_by_email(email) is not None:
        raise EmailAlreadyRegisteredError
    token, token_hash = _new_token()
    try:
        invitation = invitation_repository.create(email, role, token_hash, invited_by, _expires_at())
    except ValueError:
        raise InvitationPendingError from None
    return _deliver(invitation, token)


def list_invitations() -> list[dict]:
    return invitation_repository.list_pending()


def resend_invitation(invitation_id: UUID) -> dict:
    token, token_hash = _new_token()
    invitation = invitation_repository.replace_token(invitation_id, token_hash, _expires_at())
    if invitation is None:
        raise InvitationNotFoundError
    return _deliver(invitation, token)


def revoke_invitation(invitation_id: UUID) -> None:
    if not invitation_repository.delete_pending(invitation_id):
        raise InvitationNotFoundError


def lookup_invitation(token: str) -> dict:
    invitation = invitation_repository.find_valid(_hash_token(token))
    if invitation is None:
        raise InvitationNotFoundError
    return invitation


def accept_invitation(token: str, display_name: str, password: str) -> dict:
    user = invitation_repository.accept(_hash_token(token), display_name, hash_password(password))
    if user is None:
        raise InvitationNotFoundError
    return user


def authenticate(email: str, password: str) -> dict | None:
    user = auth_repository.find_by_email(email)
    # Keep unknown-email login timing comparable to a password verification.
    if user is None:
        verify_password(password, dummy_password_hash)
        return None
    password_valid = verify_password(password, user["password_hash"])
    return user if user["is_active"] and password_valid else None


def create_user(data: UserCreate) -> dict:
    return auth_repository.create(
        data.email, data.display_name, hash_password(data.password), data.role
    )


def current_user(user_id: UUID) -> dict | None:
    return auth_repository.find_by_id(user_id)

def list_users() -> list[dict]:
    return auth_repository.list()


def set_user_active(user_id: UUID, is_active: bool) -> dict:
    user = auth_repository.set_active(user_id, is_active)
    if user is None:
        raise UserNotFoundError
    return user


def set_user_role(user_id: UUID, role: str, actor_id: UUID) -> dict:
    if user_id == actor_id and role != "admin":
        raise CannotChangeOwnAdminRoleError
    user = auth_repository.set_role(user_id, role)
    if user is None:
        raise UserNotFoundError
    return user


def set_display_name(user_id: UUID, display_name: str) -> dict:
    user = auth_repository.set_display_name(user_id, display_name.strip())
    if user is None:
        raise UserNotFoundError
    return user


def change_password(user_id: UUID, current_password: str, new_password: str) -> None:
    existing_hash = auth_repository.password_hash(user_id)
    if existing_hash is None or not verify_password(current_password, existing_hash):
        raise IncorrectCurrentPasswordError
    auth_repository.update_password(user_id, hash_password(new_password))


def delete_user(user_id: UUID) -> None:
    result = auth_repository.delete_deactivated(user_id)
    if result == "not_found":
        raise UserNotFoundError
    if result == "active":
        raise UserMustBeInactiveError
    if result == "related":
        raise UserHasRelatedRecordsError
