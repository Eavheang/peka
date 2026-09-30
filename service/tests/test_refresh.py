from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from app.auth import routes
from app.auth.security import create_access_token, create_refresh_token, decode_access_token
from app.config import settings


def account(role="staff", version=0, active=True):
    return {"id": uuid4(), "email": "user@example.com", "role": role,
            "token_version": version, "is_active": active}


def refresh(client, token):
    return client.post("/auth/refresh", json={"refresh_token": token})


def refresh_token_for(user, **overrides):
    return create_refresh_token(
        str(user["id"]), overrides.get("role", user["role"]), overrides.get("version", user["token_version"])
    )


def test_refresh_issues_a_new_working_token_pair(client, monkeypatch):
    user = account("senior", version=3)
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)

    response = refresh(client, refresh_token_for(user))

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_access_token_expire_minutes * 60
    claims = decode_access_token(body["access_token"])
    assert (claims["sub"], claims["role"], claims["ver"]) == (str(user["id"]), "senior", 3)
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert refresh(client, body["refresh_token"]).status_code == 200, "the new refresh token also works"


def test_refresh_picks_up_the_current_version_and_role(client, monkeypatch):
    user = account("staff", version=5)
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)

    claims = decode_access_token(refresh(client, refresh_token_for(user)).json()["access_token"])

    assert claims["ver"] == 5 and claims["role"] == "staff"


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_refresh_rejects_malformed_tokens(client, token):
    response = refresh(client, token)

    assert response.status_code in {401, 422}


def test_refresh_rejects_an_access_token(client, monkeypatch):
    user = account()
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)
    access = create_access_token(str(user["id"]), user["role"], user["token_version"])

    response = refresh(client, access)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}


def test_refresh_rejects_an_expired_token(client, monkeypatch):
    user = account()
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": str(user["id"]), "role": user["role"], "ver": 0, "typ": "refresh",
         "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "iat": now - timedelta(days=2),
         "nbf": now - timedelta(days=2), "exp": now - timedelta(days=1), "jti": "x"},
        settings.jwt_secret_key.get_secret_value(), algorithm="HS256",
    )

    assert refresh(client, expired).status_code == 401


def test_refresh_rejects_a_token_signed_with_another_secret(client, monkeypatch):
    user = account()
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": str(user["id"]), "role": user["role"], "ver": 0, "typ": "refresh",
         "iss": settings.jwt_issuer, "aud": settings.jwt_audience, "iat": now, "nbf": now,
         "exp": now + timedelta(days=1), "jti": "x"},
        "a-different-secret-of-at-least-32-characters", algorithm="HS256",
    )

    assert refresh(client, forged).status_code == 401


def test_refresh_rejects_a_revoked_token_after_logout_or_password_change(client, monkeypatch):
    user = account(version=0)
    token = refresh_token_for(user)
    user["token_version"] = 1  # logout, a password change or an admin action bumped the version
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)

    assert refresh(client, token).status_code == 401


def test_refresh_rejects_a_deactivated_user(client, monkeypatch):
    user = account(active=True)
    token = refresh_token_for(user)
    user["is_active"] = False
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)

    assert refresh(client, token).status_code == 401


def test_refresh_rejects_a_token_issued_for_a_previous_role(client, monkeypatch):
    user = account("admin")
    token = refresh_token_for(user)
    user["role"] = "staff"
    monkeypatch.setattr(routes, "current_user", lambda user_id: user)

    assert refresh(client, token).status_code == 401


def test_refresh_rejects_a_deleted_user(client, monkeypatch):
    user = account()
    token = refresh_token_for(user)
    monkeypatch.setattr(routes, "current_user", lambda user_id: None)

    assert refresh(client, token).status_code == 401
