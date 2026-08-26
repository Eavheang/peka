from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.repository import auth_repository
from app.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserActivationUpdate, UserCreate, UserResponse
from app.auth.security import create_access_token, create_refresh_token, decode_access_token, decode_refresh_token
from app.auth.service import (
    UserHasRelatedRecordsError,
    UserMustBeInactiveError,
    UserNotFoundError,
    authenticate,
    create_user,
    current_user,
    delete_user,
    list_users,
    set_user_active,
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


def admin_only(user: dict = Depends(authenticated)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest) -> dict:
    user = authenticate(data.email, data.password)
    if user is None:
        raise unauthorized()
    return {"access_token": create_access_token(str(user["id"]), user["role"], user["token_version"]),
            "refresh_token": create_refresh_token(str(user["id"]), user["role"], user["token_version"]),
            "token_type": "bearer", "expires_in": settings.jwt_access_token_expire_minutes * 60}


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest) -> dict:
    try:
        claims = decode_refresh_token(data.refresh_token)
        user = current_user(UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise unauthorized() from None
    if user is None or not user["is_active"] or user["token_version"] != claims["ver"] or user["role"] != claims["role"]:
        raise unauthorized()
    return {"access_token": create_access_token(str(user["id"]), user["role"], user["token_version"]),
            "refresh_token": create_refresh_token(str(user["id"]), user["role"], user["token_version"]),
            "token_type": "bearer", "expires_in": settings.jwt_access_token_expire_minutes * 60}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: dict = Depends(authenticated)) -> Response:
    auth_repository.revoke(user["id"])
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(authenticated)) -> dict:
    return user
@router.get("/users", response_model=list[UserResponse])
def get_users(_: dict = Depends(admin_only)) -> list[dict]:
    return list_users()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def users(data: UserCreate, _: dict = Depends(admin_only)) -> dict:
    try:
        return create_user(data)
    except ValueError:
        raise HTTPException(status_code=409, detail="Email already exists") from None


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
