from urllib.parse import urlparse
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.repository import auth_repository
from app.auth.schemas import (
    InvitationAccept, InvitationCreate, InvitationPreview, InvitationResponse, InvitationSummary,
    InvitationToken, LoginRequest, PasswordChange, RefreshRequest, TokenResponse,
    UserActivationUpdate, UserProfileUpdate, UserResponse, UserRoleUpdate,
)
from app.auth.security import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token
from app.auth.service import (
    UserHasRelatedRecordsError,
    CannotChangeOwnAdminRoleError,
    EmailAlreadyRegisteredError,
    IncorrectCurrentPasswordError,
    InvitationNotFoundError,
    InvitationPendingError,
    UserMustBeInactiveError,
    UserNotFoundError,
    accept_invitation,
    authenticate,
    change_password,
    current_user,
    delete_user,
    invite_user,
    list_invitations,
    list_users,
    lookup_invitation,
    resend_invitation,
    revoke_invitation,
    set_user_active,
    set_user_role,
    set_display_name,
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid authentication credentials",
                         headers={"WWW-Authenticate": "Bearer"})


def authenticated(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    try:
        claims = decode_access_token(credentials.credentials)
        user = current_user(UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise unauthorized() from None
    if (user is None or not user["is_active"] or user["token_version"] != claims["ver"]
            or user["role"] != claims["role"]):
        raise unauthorized()
    return user


def admin_only(request: Request, user: dict = Depends(authenticated)) -> dict:
    if user["role"] != "admin":
        from app.audit.writer import record

        record("system", "Admin gate deny", actor_id=user["id"], metadata={"path": request.url.path})
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _token_response(user: dict) -> dict:
    return {
        "access_token": create_access_token(str(user["id"]), user["role"], user["token_version"]),
        "refresh_token": create_refresh_token(str(user["id"]), user["role"], user["token_version"]),
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest) -> dict:
    user = authenticate(data.email, data.password)
    if user is None:
        raise unauthorized()
    from app.audit.writer import record

    record("system", "Login success", actor_id=user["id"])
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest) -> dict:
    try:
        claims = decode_refresh_token(data.refresh_token)
        user = current_user(UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise unauthorized() from None
    if user is None or not user["is_active"] or user["token_version"] != claims["ver"] or user["role"] != claims["role"]:
        raise unauthorized()
    return _token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: dict = Depends(authenticated)) -> Response:
    auth_repository.revoke(user["id"])
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(authenticated)) -> dict:
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(data: UserProfileUpdate, user: dict = Depends(authenticated)) -> dict:
    try:
        return set_display_name(user["id"], data.display_name)
    except UserNotFoundError:
        raise unauthorized() from None


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(data: PasswordChange, user: dict = Depends(authenticated)) -> Response:
    try:
        change_password(user["id"], data.current_password, data.new_password)
    except IncorrectCurrentPasswordError:
        raise HTTPException(status_code=400, detail="Current password is incorrect") from None
    return Response(status_code=204)


@router.get("/users", response_model=list[UserResponse])
def get_users(_: dict = Depends(admin_only)) -> list[dict]:
    return list_users()


@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(
    data: InvitationCreate, request: Request, admin: dict = Depends(admin_only)
) -> dict:
    try:
        return invite_user(data.email, data.role, admin["id"], _browser_origin(request))
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=409, detail="A user with this email already exists") from None
    except InvitationPendingError:
        raise HTTPException(status_code=409, detail="This email already has a pending invitation") from None


@router.get("/invitations", response_model=list[InvitationSummary])
def get_invitations(_: dict = Depends(admin_only)) -> list[dict]:
    return list_invitations()


@router.post("/invitations/lookup", response_model=InvitationPreview)
def lookup_invitation_token(data: InvitationToken) -> dict:
    # POST keeps the token out of URLs and access logs.
    try:
        return lookup_invitation(data.token)
    except InvitationNotFoundError:
        raise _invalid_invitation() from None


@router.post("/invitations/accept", response_model=TokenResponse)
def accept_invitation_token(data: InvitationAccept) -> dict:
    try:
        user = accept_invitation(data.token, data.display_name, data.password)
    except InvitationNotFoundError:
        raise _invalid_invitation() from None
    except ValueError:
        raise HTTPException(status_code=409, detail="A user with this email already exists") from None
    return _token_response(user)


@router.post("/invitations/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation_email(
    invitation_id: UUID, request: Request, _: dict = Depends(admin_only)
) -> dict:
    try:
        return resend_invitation(invitation_id, _browser_origin(request))
    except InvitationNotFoundError:
        raise HTTPException(status_code=404, detail="Invitation not found") from None


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_pending_invitation(invitation_id: UUID, _: dict = Depends(admin_only)) -> Response:
    try:
        revoke_invitation(invitation_id)
    except InvitationNotFoundError:
        raise HTTPException(status_code=404, detail="Invitation not found") from None
    return Response(status_code=204)


def _browser_origin(request: Request) -> str | None:
    """The address the admin's browser is using, so invite links match however the app is reached
    (localhost, LAN, tunnel). None when absent or malformed; APP_BASE_URL is the fallback."""
    origin = request.headers.get("origin", "")
    parsed = urlparse(origin)
    if parsed.scheme in {"http", "https"} and parsed.netloc and origin == f"{parsed.scheme}://{parsed.netloc}":
        return origin
    return None


def _invalid_invitation() -> HTTPException:
    return HTTPException(status_code=404, detail="This invitation is invalid or has expired")


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID, data: UserRoleUpdate, admin: dict = Depends(admin_only)
) -> dict:
    try:
        return set_user_role(user_id, data.role, admin["id"])
    except CannotChangeOwnAdminRoleError:
        raise HTTPException(status_code=409, detail="You cannot remove your own admin role") from None
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found") from None


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user_activation(
    user_id: UUID, data: UserActivationUpdate, _: dict = Depends(admin_only)
) -> dict:
    try:
        return set_user_active(user_id, data.is_active)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found") from None


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_account(user_id: UUID, _: dict = Depends(admin_only)) -> Response:
    try:
        delete_user(user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found") from None
    except UserMustBeInactiveError:
        raise HTTPException(status_code=409, detail="User must be deactivated before deletion") from None
    except UserHasRelatedRecordsError:
        raise HTTPException(status_code=409, detail="User has related records") from None
    return Response(status_code=204)
